"""Database engine and session factory."""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

load_dotenv()


class Base(DeclarativeBase):
    pass


def get_engine():
    url = os.environ["DATABASE_URL"]
    return create_engine(url, pool_pre_ping=True)


def get_session_factory(engine=None):
    if engine is None:
        engine = get_engine()
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)
