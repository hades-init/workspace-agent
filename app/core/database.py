from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

# Create a database engine
engine = create_engine(settings.SQLITE_DATABASE_URI)	# toggle echo=True

# Initialize a `Session` factory with specified configurations
SessionLocal = sessionmaker(bind=engine, autoflush=True, autocommit=False)

# Base class for sqlalchemy models
class Base(DeclarativeBase):
	pass
