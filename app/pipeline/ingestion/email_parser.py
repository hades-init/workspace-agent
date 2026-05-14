from typing import List, Dict
import base64
import logging
from datetime import timezone
from email.utils import parsedate_to_datetime

from app.utils import html_to_markdown


logger = logging.getLogger(__name__)

DOCUMENT_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/calendar",
}


def _parse_headers(headers: List[Dict], extra_headers: List | None = None):
    """
    Parse the Message headers and return as a dict.

    By default returns: `from`, `subject` and `date` headers only.
    You can optionally pass `extra_headers` to include additional 
    headers
    """

    required_headers = {'from', 'subject', 'date'}

    if extra_headers:
        for h in extra_headers:
            required_headers.add(h.lower())

        
    # filter by the required headers
    parsed_headers = {header['name'].lower(): header['value'] 
                      for header in headers
                      if header['name'].lower() in required_headers}

    # convert `date` string to `datetime` object
    if 'date' in parsed_headers:
        parsed_headers['date'] = parsedate_to_datetime(parsed_headers['date'])    # parse RFC 2822 format to `datetime`
    
    # rename keys to match sqlalchemy model
    parsed_headers['from_address'] = parsed_headers.pop('from', '')
    parsed_headers['received_date'] = parsed_headers.pop('date', '')

    return parsed_headers



def _parse_message_part(message_part: Dict) -> Dict:
    """Parse the MessagePart according to mimeType.
    """
    
    def walk_message_part(message_part: Dict, output: Dict):
        """Recursive walk the message parts
        """

        mimeType = message_part['mimeType']
        body = message_part['body']

        if mimeType.startswith("multipart/"):
            # parse the child MIME message parts of this part
            for child in message_part.get('parts', []):
                walk_message_part(child, output)

        elif mimeType == "text/html":
            if not output.get('body_html'):
                data = body.get('data', '')
                html_text = base64.urlsafe_b64decode(data + "===").decode("utf-8")
                output['body_html'] = html_text

        elif mimeType == "text/plain":
            if not output.get('body_text'):
                data = body.get('data', '')
                plain_text = base64.urlsafe_b64decode(data + "===").decode("utf-8")
                output['body_text'] = plain_text
        
        elif mimeType in DOCUMENT_MIME_TYPES:
            if body.get('attachmentId'):
                # if this message part is an attachment 
                attachment = {
                    'attachment_id': body['attachmentId'],
                    'filename': message_part['filename'],
                    'mime_type': mimeType,
                    'size_bytes': body['size']
                }

                if not output.get('attachments'):
                    output['attachments'] = []
                output['attachments'].append(attachment)
    
    parsed_parts = {}
    walk_message_part(message_part, parsed_parts)
    return parsed_parts



def parse_message(email: Dict) -> Dict:
    """
    Parse the the email message - extract fields like id, thread_id, 
    parse headers, walk MIME message parts, extract HTML or plain body, 
    parse attachments (pdf/doc/docx).

    Args
        email: an email dict representing `users.messages.Messages` object of Gmail API

    https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages#Message 
    """

    logger.debug("Parsing email with id=%s", email['id'])
    
    parsed_message = dict()
    parsed_message['id'] = email['id']
    parsed_message['thread_id'] = email['threadId']

    # MessagePart - A single MIME message part
    message_part = email['payload']

    headers = _parse_headers(message_part['headers'])	# parse the headers on this message part
    parsed_message.update(headers)

    # parse the child MIME message parts on the parent MessagePart
    parts = _parse_message_part(message_part)
    parsed_message.update(parts)

    # Convert HTML to markdown
    html = parsed_message.get('body_html') or parsed_message.get('body_text', '')
    parsed_message['body_markdown'] = html_to_markdown.convert(html)

    return parsed_message