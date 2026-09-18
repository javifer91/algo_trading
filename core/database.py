from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.config import settings
from models.base import Base
from core.logger import get_logger

logger = get_logger(__name__)

engine = create_engine(
    settings.database_url, 
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    logger.info(f"Initializing database at {settings.database_url}")
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
