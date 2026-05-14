from functools import lru_cache
from typing import Dict, Optional
import yaml
from pprint import pprint

from pydantic import BaseModel

from app.core.config import settings


class UserProfile(BaseModel):
    """Static information about the user, used as context for the email drafter."""
    name: str
    current_role: Optional[str] = None
    years_experience: Optional[str] = None
    notice_period: Optional[str]
    current_location: Optional[str] = None
    timezone: Optional[str] = None
    availability: Optional[str] = None
    current_salary: Optional[str] = None
    expected_salary: Optional[str] = None
    tone: str = "friendly but professional"
    signature: str = ""
    # name -> file path
    attachments: Dict[str, str] = {}


@lru_cache(maxsize=1)
def get_profile() -> UserProfile:
    """Load profile YAML once per process and cache it."""
    with open(settings.PROFILE_PATH) as f:
        data = yaml.safe_load(f)
    return UserProfile(**data)


if __name__ == "__main__":
    profile = get_profile()
    pprint(profile.model_dump())
