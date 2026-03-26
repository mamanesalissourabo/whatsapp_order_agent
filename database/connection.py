"""
Configuration de la connexion à la base de données Selfcare.
Utilise SQLAlchemy pour l'ORM et la gestion des sessions.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from contextlib import contextmanager
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

# Création du moteur SQLAlchemy
engine = create_engine(
    settings.selfcare_db_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Vérifie la connexion avant utilisation
    echo=settings.debug,
)

# Factory de sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """
    Fournit une session de base de données.
    À utiliser comme dépendance FastAPI ou dans un context manager.
    
    Yields:
        Session SQLAlchemy
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Session:
    """
    Context manager pour obtenir une session DB.
    Utilisé dans les outils CrewAI (hors contexte FastAPI).
    
    Usage:
        with get_db_session() as db:
            products = db.query(ProductModel).all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_db_connection() -> bool:
    """Vérifie la connexion à la base de données."""
    try:
        with get_db_session() as db:
            db.execute("SELECT 1")
        logger.info("✅ Connexion à la base de données Selfcare OK")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur de connexion à la base de données: {e}")
        return False
