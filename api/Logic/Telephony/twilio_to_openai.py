import json
from api.config import logger


async def twilio_to_openai_stream(twilio_ws, openai_ws, stream_context):
    """
    Handles real-time streaming of Twilio audio directly to OpenAI.
    Ensures OpenAI receives audio as soon as it arrives from Twilio.
    """
    logger.debug("Waiting for Twilio events...")
    initialized = False
    try:
        async for message in twilio_ws.iter_text():
            data = json.loads(message)
            event_type = data.get("event", "UNKNOWN")
            logger.debug(f"Received Twilio event: {event_type}")

            if event_type == "start" and not initialized:
                initialized = True
                stream_context["stream_sid"] = data["start"]["streamSid"]
                stream_context["stream_ready"].set()
                logger.info(
                    f"Twilio audio stream started: {stream_context['stream_sid']}"
                )

            elif event_type == "media":
                audio_payload = data["media"]["payload"]
                logger.debug(
                    f"Received {len(audio_payload)} bytes of audio from Twilio."
                )

                # Directly forward audio to OpenAI in real-time
                if openai_ws and openai_ws.close_code is None:
                    openai_audio_packet = {
                        "type": "input_audio_buffer.append",
                        "audio": audio_payload,
                    }
                    await openai_ws.send(json.dumps(openai_audio_packet))
                    logger.debug(
                        f"Forwarded {len(audio_payload)} bytes of audio to OpenAI."
                    )
                else:
                    logger.debug("OpenAI WebSocket is closed. Dropping audio packet.")

            elif event_type == "stop":
                await twilio_ws.close()
                logger.info("Twilio call ended.")
                break
            else:
                logger.warning(f"Unexpected Twilio event type received: {event_type}")

    except Exception as e:
        logger.error(f"Error in twilio_to_openai_stream: {e}")
    finally:
        logger.debug("Twilio WebSocket disconnected.")
