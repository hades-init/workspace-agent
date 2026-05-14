from typing import Literal
from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_ignore_empty=True,
        extra='ignore',
    )

    # Environment
    ENVIRONMENT: Literal["local", "staging", "production"] = "local" 

    # Log level
    @computed_field
    @property
    def LOG_LEVEL(self) -> str:
        if self.ENVIRONMENT == "local":
            return "DEBUG"
        return "INFO"

    # Sqlite
    SQLITE_DATABASE_URI: str

    # Google Sheets
    SPREADSHEET_ID: str
    SPREADSHEET_RANGE: str = "A2:H"

    # Google Calendar
    DEFAULT_TIMEZONE: str

    # User profile path
    PROFILE_PATH: str


settings = Settings()   # type: ignore