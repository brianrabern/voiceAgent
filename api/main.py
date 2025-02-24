from fastapi import FastAPI, HTTPException, WebSocket, Request
from fastapi.websockets import WebSocketDisconnect
from fastapi.responses import HTMLResponse
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect
from api.Logic.AI.setup import connect_to_openai, send_session_update
import asyncio
import websockets
import json
import base64
from config import (
    logger,
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_PHONE_NUMBER,
    OPENAI_API_KEY,
    DOMAIN,
    MODEL,
    VOICE,
    get_system_message,
)

import time
import uuid
from api.Tools.inventory import SYSTEM_TOOLS
from api.Tools.tools import scheduled_appointment, write_call_summary, end_call
from api.Models.Calls import CallRequest, ActiveCall
from api.Routers import router as api_router

app = FastAPI()
app.include_router(api_router)

# active_calls = {}
# sid_id_map = {}
# websocket_map = {}


# @app.post("/call", response_model=ActiveCall)
# async def make_call(call_request: CallRequest):
#     """API to trigger an outgoing call via Twilio."""
#     try:
#         call_id = str(uuid.uuid4())

#         # initialize Twilio Client
#         twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
#         call = twilio_client.calls.create(
#             to=call_request.phone_number,
#             from_=TWILIO_PHONE_NUMBER,
#             url=f"https://{DOMAIN}/twilio/call-initiate/{call_id}",
#             status_callback=f"https://{DOMAIN}/twilio/call-completed",
#             status_callback_event=["completed"],
#             status_callback_method="POST",
#         )
#         logger.info(f"Call initiated successfully: {call_id}")

#         call_metadata = {
#             "call_id": call_id,
#             "twilio_call_sid": call.sid,
#             "call_status": call.status,
#             **call_request.model_dump(),
#         }

#         active_calls[call_id] = call_metadata
#         sid_id_map[call.sid] = call_id
#         logger.info(f"Call metadata stored: {call_metadata}")

#         return ActiveCall(**call_metadata)
#     except Exception as e:
#         logger.error(f"Error making call: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Error making call: {str(e)}")


# @app.post("/twilio/call-initiate/{call_id}")
# async def twilio_call_initiate(call_id: str):
#     """
#     Twilio calls this webhook when an outgoing call is initiated.
#     This response instructs Twilio to connect to the AI WebSocket.
#     """
#     print("CALL ID in callback", call_id)

#     try:
#         logger.info("Received Twilio call webhook")
#         twiml_response = VoiceResponse()
#         connect = Connect()
#         connect.stream(
#             url=f"wss://{DOMAIN}/call-stream/{call_id}"
#         )  # AI handles conversation

#         twiml_response.append(connect)
#         logger.debug(f"Twilio call webhook response: {str(twiml_response)}")

#         return HTMLResponse(content=str(twiml_response), media_type="application/xml")
#     except Exception as e:
#         logger.error(f"Error in Twilio call webhook: {str(e)}")
#         raise HTTPException(
#             status_code=500, detail=f"Error in Twilio call webhook: {str(e)}"
#         )


# @app.websocket("/call-stream/{call_id}")
# async def handle_call_stream(twilio_ws: WebSocket, call_id: str):
#     """Handles WebSocket connections between Twilio and AI."""
#     print("CALL ID in Websocket", call_id)

#     try:
#         await twilio_ws.accept()
#         logger.info(f"Twilio WebSocket connection accepted")

#         openai_ws = None
#         for attempt in range(3):
#             openai_ws = await connect_to_openai()
#             logger.info(f"OpenAI WebSocket connection attempt {attempt+1}")
#             if openai_ws:
#                 break
#             logger.warning(f"Retrying OpenAI connection ({attempt+1}/3)...")
#             await asyncio.sleep(1)
#         websocket_map[call_id] = openai_ws

#         if not openai_ws:
#             logger.error("Failed to connect to AI. Closing Twilio WebSocket.")
#             await twilio_ws.close()
#             return

#         call_metadata = active_calls.get(call_id)
#         if not call_metadata:
#             logger.error(f"Call ID {call_id} not found in active calls.")
#             await twilio_ws.close()
#             return
#         await send_session_update(openai_ws, call_metadata)

#         logger.debug("Starting audio streaming...")
#         try:
#             await orchestrate_audio_streams(twilio_ws, openai_ws, call_metadata)
#         except Exception as e:
#             logger.error(f"Error during audio streaming: {str(e)}")
#         finally:
#             logger.info("Closing both WebSockets.")
#             await twilio_ws.close()
#             if openai_ws and openai_ws.close_code is None:
#                 await openai_ws.close()
#         logger.info("WebSocket connections closed.")
#     except WebSocketDisconnect as e:
#         logger.warning(f"WebSocket disconnected: {str(e)}")
#         return
#     except Exception as e:
#         logger.error(f"Unexpected error: {str(e)}")


# @app.post("/twilio/call-completed")
# async def twilio_call_completed(request: Request):
#     """Webhook for detecting when a call ends."""
#     logger.info(f"Received Twilio call completed webhook")
#     try:
#         twilio_data = await request.form()
#         twilio_data = dict(twilio_data)
#         logger.info(f"Form data: {twilio_data}")
#     except Exception as e:
#         logger.error(f"Error parsing form data: {str(e)}")

#     # what else might it be

#     call_status = twilio_data.get("CallStatus")
#     logger.info(f"Call status: {call_status}")
#     call_sid = twilio_data.get("CallSid")
#     logger.info(f"Call SID: {call_sid}")
#     call_id = sid_id_map.get(call_sid)
#     logger.info(f"Call ID: {call_id}")
#     if not call_id:
#         logger.error(f"Call SID {call_sid} not found in active calls.")
#         return {"status": "error", "message": "Call not found."}

#     if call_status == "completed":
#         openai_ws = websocket_map.get(call_id)
#         logger.info(f"Websocket: {openai_ws}")

#         call_metadata = active_calls.get(call_id)

#         logger.info(f"Call {call_id} ended. Processing post-call actions...")
#         asyncio.create_task(
#             post_call_actions(call_id, openai_ws, twilio_data, call_metadata)
#         )  # Process asynchronously

#     # sid_id_map.pop(call_sid, None)
#     # active_calls.pop(call_id, None)
#     # websocket_map.pop(call_id, None)
#     return {"status": "received"}


############################################################################################################


# # AI
# async def connect_to_openai(retries=5, backoff_factor=1.5):
#     """Retries connection with exponential backoff."""
#     url = f"wss://api.openai.com/v1/realtime?model={MODEL}"
#     headers = [
#         ("Authorization", f"Bearer {OPENAI_API_KEY}"),
#         ("OpenAI-Beta", "realtime=v1"),
#     ]

#     for attempt in range(retries):
#         try:
#             openai_ws = await websockets.connect(url, additional_headers=headers)
#             logger.debug("Connected to OpenAI Realtime API")
#             return openai_ws
#         except Exception as e:
#             logger.warning(
#                 f"OpenAI connection failed (attempt {attempt+1}/{retries}): {str(e)}"
#             )
#             await asyncio.sleep(backoff_factor**attempt)

#     logger.error("Failed to connect to OpenAI after retries.")
#     return None


# # AI
# async def send_session_update(openai_ws, call_metadata):
#     """Sends a session update to OpenAI's real-time API."""

#     if openai_ws is None or openai_ws.close_code is not None:
#         logger.error("OpenAI WebSocket is closed. Cannot send session update.")
#         return None

#     system_message = get_system_message(call_metadata)
#     session_update = {
#         "type": "session.update",
#         "session": {
#             "turn_detection": {
#                 "type": "server_vad",
#                 "threshold": 0.3,
#                 "prefix_padding_ms": 1000,
#                 "silence_duration_ms": 700,
#                 "create_response": True,
#             },
#             "input_audio_format": "g711_ulaw",  # Matches Twilio's format
#             "output_audio_format": "g711_ulaw",  # Ensures AI responds in compatible format
#             "voice": VOICE,
#             "instructions": system_message,
#             "modalities": ["text", "audio"],  # Allow both text and audio responses
#             "temperature": 0.8,
#             "tools": SYSTEM_TOOLS,
#             "tool_choice": "auto",
#         },
#     }

#     logger.debug(f"Sending session update: {json.dumps(session_update, indent=2)}")
#     await openai_ws.send(json.dumps(session_update))
#     logger.debug("Session update sent successfully.")
#     res = await openai_ws.recv()
#     logger.debug(f"OpenAI response to session update: {res}")


# Twilio → OpenAI
# async def twilio_to_openai_stream(twilio_ws, openai_ws, shared_state):
#     """
#     Receives audio data from Twilio and forwards it to OpenAI.
#     """
#     logger.debug("Waiting for Twilio events...")
#     initialized = False
#     try:
#         async for message in twilio_ws.iter_text():
#             data = json.loads(message)
#             event_type = data.get("event", "UNKNOWN")
#             logger.debug(f"Received Twilio event: {event_type}")

#             if event_type == "start" and not initialized:
#                 initialized = True
#                 shared_state["stream_sid"] = data["start"]["streamSid"]
#                 shared_state["stream_ready"].set()
#                 logger.info(
#                     f"Twilio audio stream started: {shared_state['stream_sid']}"
#                 )
#             elif event_type == "media":
#                 audio_length = len(data["media"]["payload"])

#                 logger.debug(f"Received {audio_length} bytes of audio from Twilio.")
#                 latest_media_timestamp = int(data["media"]["timestamp"])
#                 logger.debug(
#                     f"Updated latest_media_timestamp: {latest_media_timestamp}"
#                 )
#                 if openai_ws and openai_ws.close_code is None:
#                     audio_payload = {
#                         "type": "input_audio_buffer.append",
#                         "audio": data["media"]["payload"],
#                     }
#                     logger.debug(
#                         f"Forwarding {len(data['media']['payload'])} bytes of audio to OpenAI."
#                     )

#                     await openai_ws.send(json.dumps(audio_payload))
#                 else:
#                     logger.debug("OpenAI WebSocket is closed. Dropping audio packet.")
#             elif event_type == "stop":
#                 await twilio_ws.close()
#                 logger.info("Twilio call ended.")
#                 break
#             else:
#                 logger.warning(f"Unexpected Twilio event type received: {event_type}")
#     except Exception as e:
#         logger.error(f"Error in receive_from_twilio: {e}")
#     finally:
#         logger.debug("Twilio WebSocket disconnected.")


# # OpenAI → Twilio
# async def openai_to_twilio_stream(twilio_ws, openai_ws, shared_state):
#     """Receives AI-generated speech from OpenAI and sends it back to Twilio."""
#     try:
#         await shared_state["stream_ready"].wait()
#         stream_sid = shared_state["stream_sid"]
#         logger.debug(f"Twilio streamSid set: {stream_sid}")

#         # Initialize variables to track the conversation for interruptions
#         last_assistant_item = None
#         response_start_timestamp_twilio = None
#         latest_media_timestamp = None

#         logger.info("Listening for AI-generated responses from OpenAI...")

#         async for openai_message in openai_ws:
#             logger.debug(f"Received OpenAI message: {openai_message}")
#             response = json.loads(openai_message)

#             response_type = response.get("type", "UNKNOWN")
#             logger.debug(f"Received OpenAI event: {response_type}")

#             if response_type == "error":
#                 logger.error(f"OpenAI returned an error: {response}")
#                 continue  # Handle error appropriately

#             # handle tools
#             if response_type == "response.done":
#                 tool_responses = await handle_tool_call(
#                     response, twilio_ws, openai_ws, shared_state
#                 )  # Process tools when done
#                 if tool_responses:
#                     for tool_response in tool_responses:
#                         await openai_ws.send(json.dumps(tool_response))
#                         logger.debug(f"Tool response sent: {tool_response}")
#                     continue  # Skip further processing

#             # handle AI audio
#             elif response_type == "response.audio.delta" and "delta" in response:
#                 logger.debug(f"OpenAI response.audio.delta")
#                 latest_media_timestamp = int(time.time() * 1000)  # Current time in ms
#                 logger.debug(
#                     f"Updated latest_media_timestamp: {latest_media_timestamp}"
#                 )
#                 # Extract AI-generated audio
#                 audio_payload = base64.b64encode(
#                     base64.b64decode(response["delta"])
#                 ).decode("utf-8")

#                 # Package it in Twilio's format (using the correct streamSid)
#                 twilio_audio = {
#                     "event": "media",
#                     "streamSid": stream_sid,
#                     "media": {"payload": audio_payload},
#                 }

#                 logger.debug(
#                     f"Sending {len(audio_payload)} bytes of AI-generated audio to Twilio."
#                 )
#                 await twilio_ws.send_json(twilio_audio)

#                 if response_start_timestamp_twilio is None:
#                     response_start_timestamp_twilio = latest_media_timestamp
#                     logger.debug(
#                         f"AI response starts at timestamp: {response_start_timestamp_twilio}ms"
#                     )

#                 # track last spoken AI item for potential truncation
#                 if response.get("item_id"):
#                     last_assistant_item = response["item_id"]

#             elif response_type == "input_audio_buffer.speech_started":
#                 logger.info("User started speaking. Interrupting AI response.")
#                 last_assistant_item, response_start_timestamp_twilio = (
#                     await handle_speech_started_event(
#                         openai_ws,
#                         twilio_ws,
#                         last_assistant_item,
#                         latest_media_timestamp,
#                         response_start_timestamp_twilio,
#                         shared_state,
#                     )
#                 )
#             elif response_type == "input_audio_buffer.speech_stopped":
#                 logger.info("🔇 OpenAI detected user speech stopped.")
#             elif response_type == "input_audio_buffer.speech_too_quiet":
#                 logger.info("🔇 OpenAI detected user speech too quiet.")

#     except Exception as e:
#         logger.error(f"Error in send_to_twilio: {e}")
#     finally:
#         logger.info("WebSocket connection to Twilio closed.")


# # helper function
# async def handle_speech_started_event(
#     openai_ws,
#     twilio_ws,
#     last_assistant_item,
#     latest_media_timestamp,
#     response_start_timestamp_twilio,
#     shared_state,
# ):
#     """Handles AI speech truncation when the user starts speaking."""

#     logger.debug(
#         f"User speech detected. Checking if AI should be interrupted...{latest_media_timestamp},{response_start_timestamp_twilio}"
#     )

#     await asyncio.sleep(0.01)  # Prevents over-sensitivity

#     if last_assistant_item and response_start_timestamp_twilio is not None:
#         elapsed_time = latest_media_timestamp - response_start_timestamp_twilio
#         logger.debug(
#             f"Truncating AI response at {elapsed_time}ms due to user interruption."
#         )

#         if elapsed_time < 0:
#             logger.debug("Warning: elapsed_time is negative. Adjusting to 0ms.")
#             elapsed_time = 0

#         # send truncation event to OpenAI
#         truncate_event = {
#             "type": "conversation.item.truncate",
#             "item_id": last_assistant_item,
#             "content_index": 0,
#             "audio_end_ms": elapsed_time,
#         }

#         try:
#             await openai_ws.send(json.dumps(truncate_event))
#             logger.debug("Truncation event successfully sent to OpenAI.")
#             openai_response = await openai_ws.recv()
#             logger.debug(f"OpenAI response to truncation: {openai_response}")

#             if "conversation.item.truncated" in openai_response:
#                 stream_sid = shared_state.get("stream_sid")
#                 if stream_sid:
#                     logger.debug("Clearing Twilio's audio buffer to stop playback.")
#                     await twilio_ws.send_json(
#                         {"event": "clear", "streamSid": stream_sid}
#                     )
#                 else:
#                     logger.debug(
#                         "Warning: stream_sid is missing, cannot clear Twilio buffer."
#                     )
#         except Exception as e:
#             logger.error(f"Error handling AI interruption: {str(e)}")
#         return None, None
#     logger.debug("No active AI response to truncate.")
#     return last_assistant_item, response_start_timestamp_twilio


# Cleanup
# async def cleanup_audio_streams(twilio_ws, openai_ws):
#     """Closes all active WebSocket connections when the call ends."""

#     logger.info("Initiating cleanup of WebSocket connections...")
#     try:
#         # close OpenAI WebSocket if still open
#         if openai_ws and openai_ws.close_code is None:
#             logger.debug("Closing OpenAI WebSocket...")
#             await openai_ws.close()
#             logger.debug("OpenAI WebSocket closed.")
#         else:
#             logger.debug("OpenAI WebSocket was already closed.")

#         # close Twilio WebSocket if still open
#         if twilio_ws.client_state == 1:
#             logger.debug("Closing Twilio WebSocket...")
#             await twilio_ws.close()
#             logger.debug("Twilio WebSocket closed.")
#         else:
#             logger.debug("Twilio WebSocket was already closed.")
#     except Exception as e:
#         logger.error(f"Error during cleanup: {e}")
#     finally:
#         logger.info("Cleanup completed. All connections closed.")


# async def handle_tool_call(response, twilio_ws, openai_ws, shared_state):
#     """Executes tools when OpenAI requests them."""
#     function_calls = [
#         f
#         for f in response.get("response", {}).get("output", [])
#         if f.get("type") == "function_call"
#     ]
#     logger.debug(f"!!!Function calls detected: {function_calls}")
#     tool_responses = []
#     for function_call in function_calls:
#         function_call_id = function_call.get("call_id")
#         function_name = function_call.get("name")
#         function_args = json.loads(
#             function_call.get("arguments", "{}")
#         )  # Ensure safe parsing

#         # Call the appropriate function dynamically
#         if function_name == "scheduled_appointment":
#             print("TOOL CALLED!!! Scheduling appointment...but ignoring for now")
#             print(f"Scheduled for {function_args}")

#             # output = await scheduled_appointment(
#             #     shared_state["call_metadata"]["issue_id"],
#             #     shared_state["call_metadata"]["phone_number"],
#             #     shared_state["call_metadata"]["first_name"],
#             #     shared_state["call_metadata"]["company"],
#             #     shared_state["call_metadata"]["issue"],
#             #     function_args["date"],
#             #     function_args["time"],
#             #     shared_state["call_metadata"]["call_id"],
#             # )
#             output = {
#                 "status": "failure",
#                 "message": "This should only be called in the postcall processing.",
#             }
#             item = {
#                 "type": "conversation.item.create",
#                 "item": {
#                     "type": "function_call_output",
#                     "call_id": function_call_id,
#                     "output": json.dumps(output),
#                 },
#             }
#             shared_state["appointment_scheduled"] = True
#             tool_responses.append(item)
#         elif function_name == "write_call_summary":
#             print("TOOL CALLED!!! Writing call summary...")

#             # output = await write_call_summary(
#             #     shared_state["call_metadata"]["call_id"],
#             #     function_args["summary"],
#             # )
#             output = {
#                 "status": "failure",
#                 "message": "This should only be called in the postcall processing.",
#             }
#             logger.info(f"Call summary written: {output}")
#             # close OpenAI WebSocket after a delay
#             await asyncio.sleep(1)

#         elif function_name == "end_call":
#             print("TOOL CALLED!!! Hanging up...")

#             output = await end_call(twilio_ws, shared_state)
#             item = {
#                 "type": "conversation.item.create",
#                 "item": {
#                     "type": "function_call_output",
#                     "call_id": function_call_id,
#                     "output": json.dumps(output),
#                 },
#             }
#             tool_responses.append(item)

#     return tool_responses


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8855)
