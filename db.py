# db.py
from sqlmodel import create_engine, SQLModel, Session
from pathlib import Path

DB_FILE = Path("data/aeroclean.db")
DB_FILE.parent.mkdir(exist_ok=True)
DATABASE_URL = f"sqlite:///{DB_FILE}"

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    return Session(engine)
