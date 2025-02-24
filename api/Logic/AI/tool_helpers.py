from api.config import logger
import asyncio
import json
from api.Tools.tools import scheduled_appointment, write_call_summary, end_call


def extract_tool_calls(response):
    """
    Extracts function calls from OpenAI's response.
    """
    function_calls = [
        output
        for output in response.get("response", {}).get("output", [])
        if output.get("type") == "function_call"
    ]
    logger.debug(f"Function calls detected: {function_calls}")
    return function_calls


async def execute_tool_function(
    function_name, function_args, function_call_id, twilio_ws, stream_context
):
    """
    Executes a tool function dynamically based on its name and returns the output.
    Handles both real-time (during call) and post-call tool execution.
    """
    output = {"status": "error", "message": "Unknown tool execution context."}
    post_call = (
        True if stream_context["call_metadata"]["call_status"] == "completed" else False
    )
    logger.info(f"Post-call: {post_call}")

    if function_name == "scheduled_appointment":
        logger.info(f"TOOL CALLED: Scheduling appointment with args {function_args}")

        # Ensure post-call execution is possible
        if post_call:
            output = await scheduled_appointment(
                stream_context["call_metadata"]["issue_id"],
                stream_context["call_metadata"]["phone_number"],
                stream_context["call_metadata"]["first_name"],
                stream_context["call_metadata"]["company"],
                stream_context["call_metadata"]["issue"],
                function_args["date"],
                function_args["time"],
                stream_context["call_metadata"]["call_id"],
            )
            stream_context["appointment_scheduled"] = True
        else:
            output = {
                "status": "failure",
                "message": "This should only be called in the post-call processing.",
            }
        await asyncio.sleep(1)
    elif function_name == "write_call_summary":
        logger.info(f"TOOL CALLED: Writing call summary with args {function_args}")

        if post_call:
            output = await write_call_summary(
                stream_context["call_metadata"]["call_id"],
                function_args["summary"],
            )
        else:
            output = {
                "status": "failure",
                "message": "This should only be called in the post-call processing.",
            }
        await asyncio.sleep(1)  # Simulating delay for call summary

    elif function_name == "end_call":
        logger.info("TOOL CALLED: Hanging up call")

        # Only execute `end_call` if Twilio is still connected
        if twilio_ws and twilio_ws.client_state == 1:
            output = await end_call(twilio_ws, stream_context)
        else:
            output = {
                "status": "failure",
                "message": "Twilio WebSocket is already closed.",
            }
    else:
        logger.warning(f"Unknown tool call: {function_name}")
        output = {"status": "error", "message": f"Unknown tool: {function_name}"}

    # Return the formatted tool response to OpenAI
    return {
        "type": "conversation.item.create",
        "item": {
            "type": "function_call_output",
            "call_id": function_call_id,
            "output": json.dumps(output),
        },
    }


async def handle_tool_call(response, twilio_ws, stream_context):
    """
    Orchestrates tool execution when OpenAI requests them.
    Handles both real-time (during call) and post-call execution.
    """
    function_calls = extract_tool_calls(response)
    tool_responses = []

    for function_call in function_calls:
        function_call_id = function_call.get("call_id")
        function_name = function_call.get("name")
        function_args = json.loads(function_call.get("arguments", "{}"))

        # If `twilio_ws` is required but unavailable, log a warning
        if function_name == "end_call" and (
            twilio_ws is None or twilio_ws.client_state != 1
        ):
            logger.warning(
                "Attempted to call 'end_call' but Twilio WebSocket is unavailable."
            )
            continue  # Skip execution if Twilio is not available

        tool_response = await execute_tool_function(
            function_name,
            function_args,
            function_call_id,
            twilio_ws,
            stream_context,
        )

        if tool_response:
            tool_responses.append(tool_response)

    return tool_responses


async def post_call_actions(call_id, openai_ws, twilio_data, call_metadata):
    """
    Handles post-call actions such as scheduling an appointment and writing a call summary.
    Ensures OpenAI WebSocket is open before sending tool requests.
    Processes tools sequentially to prevent multiple recv() calls.
    """

    logger.info(f"Processing post-call actions for call {call_id}...")

    # Ensure OpenAI WebSocket is still open
    if openai_ws is None or openai_ws.close_code is not None:
        logger.error("OpenAI WebSocket is closed. Cannot perform post-call actions.")
        return
    stringified_call_metadata = json.dumps(call_metadata)
    # Extract Twilio data
    called_city = twilio_data.get("CalledCity", "Unknown")
    called_state = twilio_data.get("CalledState", "Unknown")
    call_status = twilio_data.get("CallStatus", "Unknown")
    call_duration = twilio_data.get("CallDuration", "Unknown")
    twilio_call_sid = twilio_data.get("CallSid", "Unknown")

    try:
        # Ensure OpenAI WebSocket is still open before sending

        scheduled_appointment_request = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "The call has ended. Please use the tool *scheduled_appointment*. The arguments should be the date and time of the appointment if scheduled.",
                    }
                ],
            },
        }
        await openai_ws.send(json.dumps(scheduled_appointment_request))
        logger.info(f"Sent tool request to OpenAI: {scheduled_appointment_request}")

        # Request OpenAI to use the tool
        model_response_request = {
            "type": "response.create",
            "response": {
                "modalities": ["text"],
                "instructions": "Please respond to the message about using tool *scheduled_appointment*.",
            },
        }
        await openai_ws.send(json.dumps(model_response_request))
        print(f"Requested response: {model_response_request}")

    except Exception as e:
        logger.error(f"Error during post-call processing: {e}")

    # wait a bit
    await asyncio.sleep(5)

    try:
        write_summary_request = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"""
							Please call the function *write_call_summary* with the summary of call {call_id} = {stringified_call_metadata}.
							Also include the following information:
							- Called City: {called_city}
							- Called State: {called_state}
							- Call Status: {call_status}
							- Call Duration: {call_duration} seconds
							- Twilio Call SID: {twilio_call_sid}
						""".strip(),
                    }
                ],
            },
        }
        await openai_ws.send(json.dumps(write_summary_request))
        logger.info(f"Sent tool request to OpenAI: {write_summary_request}")
        # Request OpenAI to use the tool
        model_response_request = {
            "type": "response.create",
            "response": {
                "modalities": ["text"],
                "instructions": "Please respond to the message about using tool *write_call_summary*.",
            },
        }
        await openai_ws.send(json.dumps(model_response_request))
        logger.info(f"Requested response: {model_response_request}")
    except Exception as e:
        logger.error(f"Error during post-call processing: {e}")

    logger.info("Post-call actions completed.")
    # wait a bit
    await asyncio.sleep(5)
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
