import json
from app.core.models import Message


def to_xml_string(message: Message):
    """Format the input email message as an XML style string."""
    return (
        "<email>\n"
        f"  <from>{message.from_address}</from>\n"
        f"  <date>{message.received_date.isoformat() if message.received_date else None}</date>\n"
        f"  <subject>{message.subject}</subject>\n"
        f"  <body>{message.body_markdown}</body>\n"
        "</email>"
    )


def to_json_string(message: Message):
    """Format the input email message as a JSON string."""
    data = {
        "subject": message.subject,
        "from": message.from_address,
        "date": message.received_date.isoformat() if message.received_date else None,
        "body": message.body_markdown
    }
    return json.dumps(data, indent=2, ensure_ascii=False)