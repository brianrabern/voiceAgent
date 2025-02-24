SYSTEM_TOOLS = [
    {
        "type": "function",
        "name": "scheduled_appointment",
        "description": "This function should only be used when you are prompted to in the post-call proceess. It records a scheduled an appointment for the customer if an appointment was agreed upon. If 'date' and 'time' are None, no appointment was scheduled.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": ["string", "null"],
                    "description": "The appointment date (YYYY-MM-DD) or None if no appointment was scheduled.",
                },
                "time": {
                    "type": ["string", "null"],
                    "description": "The appointment time (e.g., '3:00 PM') or None if no appointment was scheduled.",
                },
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "write_call_summary",
        "description": "Part of the in the post-call proceess this function generates and saves a summary of the call based on customer responses .",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "A textual summary of the call, capturing key details discussed with the customer. Include any important notes or follow-up actions. This will be written to a markdown file.",
                }
            },
            "required": ["summary"],
        },
    },
    {
        "type": "function",
        "name": "end_call",
        "description": "Ends the twilio websocket when the call is complete.",
        "parameters": {"type": "object", "properties": {}},
    },
]
