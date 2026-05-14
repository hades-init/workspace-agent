from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

class ApplyDetails(BaseModel):
    """Structured details extracted from an job apply email."""

    company: str = Field(
        description="The name of the company that is hiring"
    )
    role: str = Field(
        description="The job title exactly as stated in the email."
    )
    location: Optional[str] = Field(
        default=None,
        description="Work location as stated (city, country, 'Remote', 'Hybrid', etc.).",
    )
    apply_link: Optional[str] = Field(
        default=None,
        description="The direct URL to apply for this role. `None` if no apply link is present.",
    )
    source_platform: Optional[str] = Field(
        default=None,
        description="Where the posting originated (e.g., LinkedIn, Wellfound, Indeed, direct recruiter outreach).",
    )
    notes: Optional[str] = Field(
        default=None,
        description=(
            "Brief free-form notes for anything useful that didn't fit other fields. "
            "Keep under 500 characters. `None` if no useful information is present."
        ),
    )


class InterviewDetails(BaseModel):
    """Structured details extracted from an interview-invite email."""

    title: str = Field(
        description=(
            "Title of the calendar event. "
            "Must be short but descriptive of the event" 
            "(e.g. JP Morgan Interview (Round 1) - ML Engineer)."
        )
    )
    start_datetime: datetime = Field(
        description=(
            "Interview START time in ISO 8601 datetime format (e.g. '2026-05-12T14:00:00')."
            "Do not include 'Z', or any other timezone suffix."
        )
    )
    end_datetime: datetime = Field(
        description=(
            "Interview END time in ISO 8601 datetime format (e.g. '2026-05-06T16:00:00')."
            "Do NOT include 'Z', or any other timezone suffix."
        )
    )
    meeting_link: Optional[str] = Field(
        description=(
            "The meeting link (e.g Google meet url, Zoom meeting url, Teams meeting url, etc.) "
            "`None` if no meeting link found or if the email says one will be sent later."
        )
    )
    description: Optional[str] = Field(
        description="A brief description about the calendar event. "
        "Any agenda, prep instructions, meeting info, or notes from the email that "
        "would be useful in a calendar event description. "
        "Keep under 500 characters. `None` if no useful information is present."
    )


class ReplyRequirements(BaseModel):
    """Structured details extracted from a reply-needed email about the ask from recipient"""
    message_ask: List[str] = Field(
        description=(
            "A list of things (information) that the email is asking to share. "
            "For example, resume, current salary, expected salary, notice period, etc."
        )
    )
    suggested_attachments: Optional[List[str]] = Field(
        description="A list of suggested attachments to send with the reply email (e.g. 'resume', 'paylsip', etc.)"
    )
    message_summary: str = Field(
        description="A short and concise 1-2 lines summary of the message thread."
    )
    urgency: Literal['low', 'medium', 'high'] = Field(description="Urgency of the email")
    tone: Literal['formal', 'neutral', 'casual'] = Field(description="Tone of the email")


class EmailDraft(BaseModel):
    """Structured details to compose or draft email"""
    to_address: str = Field(
        description="Email address of the sender, taken verbatim from the <from_address> field of email."
    )
    subject: str = Field(
        description="The subject of email prefixed with 'RE: ', like this - 'RE: <subject>'"
    )
    reply_body: str = Field(
        description="Plain text body of the reply to send to this email."
    )
    attachments_to_include: Optional[List[str]] = Field(
        description="List of attachments to include"
    )
