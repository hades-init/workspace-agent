import logging
from typing import Dict
from functools import lru_cache

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.google_auth import get_credentials
from app.core.config import settings
from app.core.schemas import ApplyDetails
from app.pipeline.execution.handlers.base import HandlerError


logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def _get_resource():
    """Construct a Resource for interacting with Google Sheets API.
    """

    return build("sheets", "v4", credentials=get_credentials())



COLUMN_ORDER = list(ApplyDetails.model_fields.keys())


def append_data(data: Dict, **kwargs) -> Dict:
    """Append data as a new row to a google sheet.
    """

    values_ = [data.get(col, "") for col in COLUMN_ORDER]

    service = _get_resource()
    try:
        response = (
            service.spreadsheets()
            .values()
            .append(
                spreadsheetId=settings.SPREADSHEET_ID,
                range=settings.SPREADSHEET_RANGE,
                valueInputOption="USER_ENTERED",
                includeValuesInResponse=True,
                body={
                    "values": [values_]
                }
            )
            .execute()
        )

        action_id = kwargs.get('action_id')
        logger.info("Values appended to sheet action_id=%s", action_id)

    except HttpError as e:
        logger.exception("Google Sheets append failed")
        raise HandlerError(f"Google Sheets API error: {e}") from e
    
    return response.get('updates', {})