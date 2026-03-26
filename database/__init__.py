"""
Couche base de données - Connexion et modèles SQLAlchemy pour Selfcare.
"""

from database.connection import get_db, engine, SessionLocal
from database.models import Base, ProductModel, ClientModel, OrderModel, OrderItemModel

__all__ = [
    "get_db", "engine", "SessionLocal",
    "Base", "ProductModel", "ClientModel", "OrderModel", "OrderItemModel",
]
