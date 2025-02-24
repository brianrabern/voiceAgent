from api.config import logger, OPENAI_API_KEY, MODEL, VOICE, get_system_message
from api.Tools.inventory import SYSTEM_TOOLS
import asyncio
import websockets
import json


async def connect_to_openai(retries=5, backoff_factor=1.5):
    """Retries connection with exponential backoff."""
    url = f"wss://api.openai.com/v1/realtime?model={MODEL}"
    headers = [
        ("Authorization", f"Bearer {OPENAI_API_KEY}"),
        ("OpenAI-Beta", "realtime=v1"),
    ]

    for attempt in range(retries):
        try:
            openai_ws = await websockets.connect(url, additional_headers=headers)
            logger.debug("Connected to OpenAI Realtime API")
            return openai_ws
        except Exception as e:
            logger.warning(
                f"OpenAI connection failed (attempt {attempt+1}/{retries}): {str(e)}"
            )
            await asyncio.sleep(backoff_factor**attempt)

    logger.error("Failed to connect to OpenAI after retries.")
    return None


def build_session_update(call_metadata):
    """
    Constructs the session update payload for OpenAI.
    """
    return {
        "type": "session.update",
        "session": {
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.3,
                "prefix_padding_ms": 1000,
                "silence_duration_ms": 700,
                "create_response": True,
            },
            "input_audio_format": "g711_ulaw",  # Matches Twilio's format
            "output_audio_format": "g711_ulaw",  # Ensures AI responds in compatible format
            "voice": VOICE,
            "instructions": get_system_message(call_metadata),  # Get AI instructions
            "modalities": ["text", "audio"],  # Allow both text and audio responses
            "temperature": 0.8,
            "tools": SYSTEM_TOOLS,
            "tool_choice": "auto",
        },
    }


async def send_session_update(openai_ws, call_metadata):
    """
    Sends a session update to OpenAI's real-time API.
    """

    if openai_ws is None or openai_ws.close_code is not None:
        logger.error("OpenAI WebSocket is closed. Cannot send session update.")
        return None

    session_update = build_session_update(call_metadata)

    try:
        logger.debug(f"Sending session update: {json.dumps(session_update, indent=2)}")
        await openai_ws.send(json.dumps(session_update))
        logger.debug("Session update sent successfully.")

        # Receive response from OpenAI
        res = await openai_ws.recv()
        logger.debug(f"OpenAI response to session update: {res}")
        return res

    except Exception as e:
        logger.error(f"Error sending session update to OpenAI: {e}")
        return None
