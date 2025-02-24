import json
import base64
import asyncio
from api.config import logger
from api.Logic.AI.speech_helpers import handle_speech_started_event
from api.Logic.AI.tool_helpers import handle_tool_call


async def openai_to_twilio_stream(twilio_ws, openai_ws, stream_context):
    """
    Handles real-time streaming of AI-generated speech directly from OpenAI to Twilio.
    Processes OpenAI tool calls and forwards AI-generated audio immediately to Twilio.
    """
    await stream_context["stream_ready"].wait()
    stream_sid = stream_context["stream_sid"]
    logger.debug(f"Twilio streamSid set: {stream_sid}")

    try:
        async for openai_message in openai_ws:
            logger.debug(f"Received OpenAI message: {openai_message}")
            response = json.loads(openai_message)
            response_type = response.get("type", "UNKNOWN")

            logger.debug(f"Received OpenAI event: {response_type}")

            if response_type == "error":
                logger.error(f"OpenAI returned an error: {response}")
                continue  # Handle error appropriately

            # Handle function calls (e.g., tools)
            if response_type == "response.done":
                active_twilio_ws = (
                    twilio_ws if twilio_ws and twilio_ws.client_state == 1 else None
                )
                tool_responses = await handle_tool_call(
                    response, active_twilio_ws, stream_context
                )
                for tool_response in tool_responses:
                    await openai_ws.send(json.dumps(tool_response))
                    res = await openai_ws.recv()
                    logger.debug(f"OpenAI response to tool call: {res}")
                    logger.debug(f"Tool response sent: {tool_response}")
                continue  # Skip further processing

            # Handle AI-generated audio and send it to Twilio immediately
            elif response_type == "response.audio.delta" and "delta" in response:
                logger.debug(f"Processing OpenAI response.audio.delta")

                # Convert AI-generated speech into Twilio's format
                audio_payload = base64.b64encode(
                    base64.b64decode(response["delta"])
                ).decode("utf-8")

                twilio_audio = {
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {"payload": audio_payload},
                }

                # Send directly to Twilio in real-time
                if twilio_ws:
                    await twilio_ws.send_json(twilio_audio)
                    logger.debug(
                        f"Sent {len(audio_payload)} bytes of AI-generated audio to Twilio."
                    )
                else:
                    logger.warning(
                        "Twilio WebSocket is closed. Skipping audio transmission."
                    )

            elif response_type == "input_audio_buffer.speech_started":
                logger.info("User started speaking. Interrupting AI response.")

                # Retrieve stored values from stream_context
                last_assistant_item = stream_context.get("last_assistant_item")
                latest_media_timestamp = stream_context.get("latest_media_timestamp")
                response_start_timestamp_twilio = stream_context.get(
                    "response_start_timestamp_twilio"
                )

                active_twilio_ws = (
                    twilio_ws if twilio_ws and twilio_ws.client_state == 1 else None
                )

                # Call function with correct parameters
                last_assistant_item, response_start_timestamp_twilio = (
                    await handle_speech_started_event(
                        openai_ws,
                        active_twilio_ws,
                        last_assistant_item,
                        latest_media_timestamp,
                        response_start_timestamp_twilio,
                        stream_context,
                    )
                )

                # Update stream_context with the latest state
                stream_context["last_assistant_item"] = last_assistant_item
                stream_context["response_start_timestamp_twilio"] = (
                    response_start_timestamp_twilio
                )

            elif response_type == "input_audio_buffer.speech_stopped":
                logger.info("🔇 OpenAI detected user speech stopped.")

            elif response_type == "input_audio_buffer.speech_too_quiet":
                logger.info("🔇 OpenAI detected user speech too quiet.")

    except Exception as e:
        logger.error(f"Error in openai_to_twilio_stream: {e}")
