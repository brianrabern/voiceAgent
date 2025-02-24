import json
import asyncio
import os
from config import logger


async def scheduled_appointment(
    issue_id: str = None,
    phone_number: str = None,
    customer_name: str = None,
    company: str = None,
    issue: str = None,
    date: str = None,
    time: str = None,
    call_id: str = None,
):
    """Record appointment if scheduled."""

    # Check if date and time are missing or empty strings
    if not date or not time:
        logger.debug("No appointment was scheduled.")
        return {
            "status": "success",
            "message": "No appointment was scheduled.",
        }

    file_name = "appointments.json"

    # Prepare appointment data
    new_appointment = {
        "issue_id": issue_id,
        "date": date,
        "time": time,
        "customer_name": customer_name,
        "phone_number": phone_number,
        "company": company,
        "issue": issue,
        "call_id": call_id,
    }

    try:
        # Read existing data if the file exists
        if os.path.exists(file_name):
            try:
                with open(file_name, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                    if not isinstance(existing_data, list):
                        existing_data = []
            except json.JSONDecodeError:
                existing_data = []
        else:
            existing_data = []

        # Append new appointment
        existing_data.append(new_appointment)

        # Write back to file
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=4)

        logger.info(
            f"Appointment scheduled for {customer_name} on {date} at {time} for issue: {issue}."
        )
        return {
            "status": "success",
            "message": "Appointment scheduled successfully.",
            "appointment": new_appointment,
        }

    except Exception as e:
        logger.error(f"Error saving appointment: {e}")
        return {"status": "error", "message": f"Failed to save appointment: {e}"}


async def write_call_summary(call_id: str, summary: str = None):
    """Generates a summary of the call based on customer responses and saves it to a Markdown file."""

    # Ensure call_id and summary are valid
    if not call_id:
        return {"status": "error", "message": "Invalid call ID."}
    summary = summary if summary else "No summary provided."

    file_name = f"{call_id}.md"
    try:
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(summary)

        logger.info(f"Summary successfully written to {file_name}")

        return {
            "status": "success",
            "message": f"Call summary saved to {file_name}",
            "file": file_name,
        }
    except Exception as e:
        logger.error(f"Error writing call summary: {e}")
        return {"status": "error", "message": f"Failed to save call summary: {e}"}


async def end_call(twilio_ws, stream_context):
    """Ends the call by notifying Twilio and closing both WebSocket connections."""
    try:
        stream_context["call_active"] = False
        # Notify Twilio to stop media streaming and end the call

        if twilio_ws.client_state == 1:
            stop_event = {"event": "stop"}
            await twilio_ws.send_json(stop_event)
            await asyncio.sleep(0.1)
            await twilio_ws.close()
        return {"status": "success", "message": "AI ended call successfully."}

    except Exception as e:
        logger.error(f"Error while ending call: {e}")
