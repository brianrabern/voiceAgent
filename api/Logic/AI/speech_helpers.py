from api.config import logger
import asyncio
import json


async def detect_speech_interruption(
    last_assistant_item, latest_media_timestamp, response_start_timestamp_twilio
):
    """
    Checks if the user has started speaking and determines if AI should be interrupted.
    Returns whether truncation should occur and the adjusted elapsed time.
    """
    logger.debug(
        f"User speech detected. Checking if AI should be interrupted... {latest_media_timestamp}, {response_start_timestamp_twilio}"
    )

    await asyncio.sleep(0.01)  # Prevents over-sensitivity

    if last_assistant_item and response_start_timestamp_twilio is not None:
        elapsed_time = latest_media_timestamp - response_start_timestamp_twilio
        logger.debug(
            f"Truncating AI response at {elapsed_time}ms due to user interruption."
        )

        if elapsed_time < 0:
            logger.debug("Warning: elapsed_time is negative. Adjusting to 0ms.")
            elapsed_time = 0

        return True, elapsed_time
    else:
        logger.debug("No active AI response to truncate.")
        return False, None


async def truncate_openai_response(openai_ws, last_assistant_item, elapsed_time):
    """
    Sends a truncation event to OpenAI and waits for confirmation.
    """
    truncate_event = {
        "type": "conversation.item.truncate",
        "item_id": last_assistant_item,
        "content_index": 0,
        "audio_end_ms": elapsed_time,
    }

    try:
        await openai_ws.send(json.dumps(truncate_event))
        logger.debug("Truncation event successfully sent to OpenAI.")

        openai_response = await openai_ws.recv()
        logger.debug(f"OpenAI response to truncation: {openai_response}")

        return "conversation.item.truncated" in openai_response

    except Exception as e:
        logger.error(f"Error sending truncation event to OpenAI: {str(e)}")
        return False


async def clear_twilio_audio_buffer(twilio_ws, stream_context):
    """
    Sends a 'clear' event to Twilio to stop AI speech playback.
    """
    stream_sid = stream_context.get("stream_sid")
    if stream_sid:
        logger.debug("Clearing Twilio's audio buffer to stop playback.")
        await twilio_ws.send_json({"event": "clear", "streamSid": stream_sid})
    else:
        logger.debug("Warning: stream_sid is missing, cannot clear Twilio buffer.")


async def handle_speech_started_event(
    openai_ws,
    twilio_ws,
    last_assistant_item,
    latest_media_timestamp,
    response_start_timestamp_twilio,
    stream_context,
):
    """
    Handles AI speech truncation when the user starts speaking.
    """
    should_truncate, elapsed_time = await detect_speech_interruption(
        last_assistant_item, latest_media_timestamp, response_start_timestamp_twilio
    )

    if should_truncate:
        success = await truncate_openai_response(
            openai_ws, last_assistant_item, elapsed_time
        )
        if success:
            # Ensure Twilio WebSocket is still active before clearing buffer
            if twilio_ws and twilio_ws.client_state == 1:
                await clear_twilio_audio_buffer(twilio_ws, stream_context)
            else:
                logger.warning("Twilio WebSocket is closed. Cannot clear audio buffer.")

        return None, None

    return last_assistant_item, response_start_timestamp_twilio
