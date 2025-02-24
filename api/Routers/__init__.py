from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.websockets import WebSocket, WebSocketDisconnect
from twilio.twiml.voice_response import Connect, VoiceResponse
from twilio.rest import Client
from api.config import (
    DOMAIN,
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_PHONE_NUMBER,
)
from api.config import logger
from api.Logic.Orchestration.orchestration import orchestrate_audio_streams
from api.Logic.AI.setup import connect_to_openai, send_session_update
from api.Logic.AI.tool_helpers import post_call_actions
from api.Models.Calls import CallRequest, ActiveCall
import uuid
import asyncio

active_calls = {}
sid_id_map = {}
websocket_map = {}

router = APIRouter()


@router.post("/call", response_model=ActiveCall)
async def make_call(call_request: CallRequest):
    """API to trigger an outgoing call via Twilio."""
    try:
        call_id = str(uuid.uuid4())

        # initialize Twilio Client
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        call = twilio_client.calls.create(
            to=call_request.phone_number,
            from_=TWILIO_PHONE_NUMBER,
            url=f"https://{DOMAIN}/twilio/call-initiate/{call_id}",
            status_callback=f"https://{DOMAIN}/twilio/call-completed",
            status_callback_event=["completed"],
            status_callback_method="POST",
        )
        logger.info(f"Call initiated successfully: {call_id}")

        call_metadata = {
            "call_id": call_id,
            "twilio_call_sid": call.sid,
            "call_status": call.status,
            "twilio_call_sid": call.sid,
            **call_request.model_dump(),
        }
        active_calls[call_id] = call_metadata
        sid_id_map[call.sid] = call_id
        logger.info(f"Call metadata stored: {call_metadata}")

        return ActiveCall(**call_metadata)
    except Exception as e:
        logger.error(f"Error making call: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error making call: {str(e)}")


@router.post("/twilio/call-initiate/{call_id}")
async def twilio_call_initiate(call_id: str):
    """
    Twilio calls this webhook when an outgoing call is initiated.
    This response instructs Twilio to connect to the AI WebSocket.
    """
    print("CALL ID in callback", call_id)

    try:
        logger.info("Received Twilio call webhook")
        twiml_response = VoiceResponse()
        connect = Connect()
        connect.stream(
            url=f"wss://{DOMAIN}/call-stream/{call_id}"
        )  # AI handles conversation

        twiml_response.append(connect)
        logger.debug(f"Twilio call webhook response: {str(twiml_response)}")

        return HTMLResponse(content=str(twiml_response), media_type="application/xml")
    except Exception as e:
        logger.error(f"Error in Twilio call webhook: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error in Twilio call webhook: {str(e)}"
        )


@router.websocket("/call-stream/{call_id}")
async def handle_call_stream(twilio_ws: WebSocket, call_id: str):
    """Handles WebSocket connections between Twilio and AI."""
    print("CALL ID in Websocket", call_id)

    try:
        await twilio_ws.accept()
        logger.info(f"Twilio WebSocket connection accepted")

        openai_ws = None
        for attempt in range(3):
            openai_ws = await connect_to_openai()
            logger.info(f"OpenAI WebSocket connection attempt {attempt+1}")
            if openai_ws:
                break
            logger.warning(f"Retrying OpenAI connection ({attempt+1}/3)...")
            await asyncio.sleep(1)
        websocket_map[call_id] = openai_ws

        if not openai_ws:
            logger.error("Failed to connect to AI. Closing Twilio WebSocket.")
            await twilio_ws.close()
            return

        call_metadata = active_calls.get(call_id)
        if not call_metadata:
            logger.error(f"Call ID {call_id} not found in active calls.")
            await twilio_ws.close()
            return
        await send_session_update(openai_ws, call_metadata)

        logger.debug("Starting audio streaming...")
        try:
            await orchestrate_audio_streams(twilio_ws, openai_ws, call_metadata)
        except Exception as e:
            logger.error(f"Error during audio streaming: {str(e)}")
        finally:
            logger.info("Closing both WebSockets.")
            await twilio_ws.close()
            if openai_ws and openai_ws.close_code is None:
                await openai_ws.close()
        logger.info("WebSocket connections closed.")
    except WebSocketDisconnect as e:
        logger.warning(f"WebSocket disconnected: {str(e)}")
        return
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")


@router.post("/twilio/call-completed")
async def twilio_call_completed(request: Request):
    """Webhook for detecting when a call ends."""
    logger.info(f"Received Twilio call completed webhook")
    try:
        twilio_data = await request.form()
        twilio_data = dict(twilio_data)
        logger.info(f"Form data: {twilio_data}")
    except Exception as e:
        logger.error(f"Error parsing form data: {str(e)}")

    call_status = twilio_data.get("CallStatus")
    logger.info(f"Call status: {call_status}")
    call_sid = twilio_data.get("CallSid")
    logger.info(f"Call SID: {call_sid}")
    call_id = sid_id_map.get(call_sid)
    logger.info(f"Call ID: {call_id}")
    if not call_id:
        logger.error(f"Call SID {call_sid} not found in active calls.")
        return {"status": "error", "message": "Call not found."}

    if call_status == "completed":
        openai_ws = websocket_map.get(call_id)
        logger.info(f"Websocket: {openai_ws}")

        call_metadata = active_calls.get(call_id)
        call_metadata["call_status"] = call_status

        logger.info(f"Call {call_id} ended. Processing post-call actions...")
        asyncio.create_task(
            post_call_actions(call_id, openai_ws, twilio_data, call_metadata)
        )  # Process asynchronously
    return {"status": "received"}
