from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import create_sync_engine_with_pool

sync_engine = create_sync_engine_with_pool(settings.DATABASE_URL_SYNC)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)
