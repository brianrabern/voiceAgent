from api.config import logger
import asyncio
from api.Logic.AI.openai_to_twilio import openai_to_twilio_stream
from api.Logic.Telephony.twilio_to_openai import twilio_to_openai_stream


# orchestration
async def orchestrate_audio_streams(twilio_ws, openai_ws, call_metadata):
    """Orchestrates real-time audio streaming between Twilio and OpenAI."""

    # Initialize shared state and event for synchronization
    stream_ready = asyncio.Event()
    stream_context = {"stream_sid": None, "stream_ready": stream_ready}
    stream_context["call_metadata"] = call_metadata

    logger.info("Starting audio streaming...")
    try:
        await asyncio.gather(
            twilio_to_openai_stream(
                twilio_ws, openai_ws, stream_context
            ),  # Twilio → OpenAI
            openai_to_twilio_stream(
                twilio_ws, openai_ws, stream_context
            ),  # OpenAI → Twilio
        )
    except Exception as e:
        logger.error(f"Error in orchestrate_audio_streams: {e}")
    finally:
        logger.debug("Cleaning up audio streams...")
        await cleanup_audio_streams(twilio_ws, openai_ws)
        logger.info("Audio streaming cleanup completed.")


# Cleanup function
async def cleanup_audio_streams(twilio_ws, openai_ws):
    """Closes all active WebSocket connections when the call ends."""

    logger.info("Initiating cleanup of WebSocket connections...")

    # Close OpenAI WebSocket
    if openai_ws:
        try:
            if openai_ws.close_code is None:
                logger.debug("Closing OpenAI WebSocket...")
                await openai_ws.close()
                logger.debug("OpenAI WebSocket closed.")
            else:
                logger.debug("OpenAI WebSocket was already closed.")
        except Exception as e:
            logger.error(f"Error closing OpenAI WebSocket: {e}")

    # Close Twilio WebSocket
    if twilio_ws:
        try:
            if twilio_ws.client_state == 1:
                logger.debug("Closing Twilio WebSocket...")
                await twilio_ws.close()
                logger.debug("Twilio WebSocket closed.")
            else:
                logger.debug("Twilio WebSocket was already closed.")
        except Exception as e:
            logger.error(f"Error closing Twilio WebSocket: {e}")

    logger.info("Cleanup completed. All connections closed.")
