# database/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from pathlib import Path

# Base du projet (EcoENERGYhome21/)
BASE_DIR = Path(__file__).resolve().parent.parent

# Fichier SQLite (sera créé automatiquement)
DB_PATH = BASE_DIR / "ecoenergy.db"
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # important avec Streamlit
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
