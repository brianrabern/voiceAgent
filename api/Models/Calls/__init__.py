from pydantic import BaseModel
from typing import List


class CallRequest(BaseModel):
    issue_id: str
    phone_number: str
    first_name: str
    company: str
    company_description: str
    availability: List[dict]
    issue: str
    language: str


class ActiveCall(BaseModel):
    call_id: str
    issue_id: str
    phone_number: str  # validate phone numbers?
    first_name: str
    company: str
    company_description: str
    availability: List[dict]
    issue: str
    language: str = "en"
    twilio_call_sid: str
    call_status: str
