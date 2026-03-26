"""
Modèles SQLAlchemy pour la base de données Selfcare.
Représente les tables existantes de la base Selfcare (lecture seule pour la plupart).
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey,
    Numeric, func
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()


class ClientModel(Base):
    """Modèle client Selfcare."""
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), index=True)
    email = Column(String(255))
    address = Column(Text)
    city = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relations
    orders = relationship("OrderModel", back_populates="client")

    def __repr__(self):
        return f"<Client {self.code} - {self.name}>"


class ProductModel(Base):
    """Modèle produit du catalogue Selfcare."""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    unit_price = Column(Numeric(10, 2), nullable=False)
    unit_type = Column(String(50), default="caisse")
    category = Column(String(100))
    is_available = Column(Boolean, default=True)
    min_quantity = Column(Integer, default=1)
    image_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Product {self.code} - {self.name}>"

    def to_dict(self) -> dict:
        """Convertit le modèle en dictionnaire."""
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "unit_price": float(self.unit_price),
            "unit_type": self.unit_type,
            "category": self.category,
            "is_available": self.is_available,
            "min_quantity": self.min_quantity,
            "image_url": self.image_url,
        }


class OrderModel(Base):
    """Modèle commande."""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(50), unique=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    total_amount = Column(Numeric(12, 2), default=0)
    status = Column(String(50), default="draft")
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relations
    client = relationship("ClientModel", back_populates="orders")
    items = relationship("OrderItemModel", back_populates="order", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Order {self.order_number} - {self.status}>"

    def to_dict(self) -> dict:
        """Convertit le modèle en dictionnaire."""
        return {
            "id": self.id,
            "order_number": self.order_number,
            "client_id": self.client_id,
            "total_amount": float(self.total_amount) if self.total_amount else 0,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [item.to_dict() for item in self.items] if self.items else [],
        }


class OrderItemModel(Base):
    """Modèle ligne de commande."""
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    product_name = Column(String(255))
    product_code = Column(String(50))
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    unit_type = Column(String(50), default="caisse")
    total_price = Column(Numeric(12, 2))

    # Relations
    order = relationship("OrderModel", back_populates="items")

    def __repr__(self):
        return f"<OrderItem {self.product_name} x{self.quantity}>"

    def to_dict(self) -> dict:
        """Convertit le modèle en dictionnaire."""
        return {
            "id": self.id,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "product_code": self.product_code,
            "quantity": self.quantity,
            "unit_price": float(self.unit_price),
            "unit_type": self.unit_type,
            "total_price": float(self.total_price) if self.total_price else 0,
        }
