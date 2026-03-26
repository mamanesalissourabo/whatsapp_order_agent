"""
Schémas Pydantic pour les commandes et le panier.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime


class OrderStatus(str, Enum):
    """Statuts possibles d'une commande."""
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class CartItem(BaseModel):
    """Article dans le panier."""
    product_id: int = Field(..., description="ID du produit")
    product_name: str = Field(..., description="Nom du produit")
    product_code: str = Field(default="", description="Code produit")
    quantity: int = Field(..., ge=1, description="Quantité commandée")
    unit_price: float = Field(..., description="Prix unitaire en MAD")
    unit_type: str = Field(default="caisse", description="Unité de mesure")

    @property
    def total_price(self) -> float:
        """Calcule le prix total de la ligne."""
        return self.quantity * self.unit_price

    def format_display(self) -> str:
        """Formate l'article pour affichage."""
        return f"{self.product_name} x{self.quantity} {self.unit_type}(s) = {self.total_price:.2f} MAD"


class Cart(BaseModel):
    """Panier d'achat."""
    items: List[CartItem] = Field(default_factory=list)
    client_id: Optional[int] = Field(None, description="ID du client")
    client_name: Optional[str] = Field(None, description="Nom du client")

    @property
    def total(self) -> float:
        """Calcule le total du panier."""
        return sum(item.total_price for item in self.items)

    @property
    def item_count(self) -> int:
        """Nombre d'articles dans le panier."""
        return len(self.items)

    def add_item(self, item: CartItem) -> None:
        """Ajoute un article ou met à jour la quantité si déjà présent."""
        for existing in self.items:
            if existing.product_id == item.product_id:
                existing.quantity += item.quantity
                return
        self.items.append(item)

    def remove_item(self, product_id: int) -> bool:
        """Supprime un article du panier. Retourne True si trouvé."""
        for i, item in enumerate(self.items):
            if item.product_id == product_id:
                self.items.pop(i)
                return True
        return False

    def update_quantity(self, product_id: int, quantity: int) -> bool:
        """Met à jour la quantité d'un article. Retourne True si trouvé."""
        for item in self.items:
            if item.product_id == product_id:
                item.quantity = quantity
                return True
        return False

    def clear(self) -> None:
        """Vide le panier."""
        self.items.clear()

    def format_display(self) -> str:
        """Formate le panier pour affichage WhatsApp."""
        if not self.items:
            return "🛒 Votre panier est vide."
        lines = ["🛒 Votre panier:"]
        for i, item in enumerate(self.items, 1):
            lines.append(f"  {i}. {item.format_display()}")
        lines.append(f"\n💰 Total: {self.total:.2f} MAD")
        return "\n".join(lines)


class Order(BaseModel):
    """Commande confirmée."""
    id: Optional[int] = Field(None, description="ID de la commande")
    order_number: Optional[str] = Field(None, description="Numéro de commande")
    client_id: int = Field(..., description="ID du client")
    client_name: str = Field(default="", description="Nom du client")
    items: List[CartItem] = Field(default_factory=list)
    total_amount: float = Field(default=0.0, description="Montant total")
    status: OrderStatus = Field(default=OrderStatus.DRAFT)
    created_at: Optional[datetime] = None
    notes: Optional[str] = None

    def format_confirmation(self) -> str:
        """Formate la confirmation de commande."""
        lines = [
            f"✅ Commande #{self.order_number or self.id} confirmée!",
            f"👤 Client: {self.client_name}",
            "",
            "📦 Articles:",
        ]
        for i, item in enumerate(self.items, 1):
            lines.append(f"  {i}. {item.format_display()}")
        lines.append(f"\n💰 Total: {self.total_amount:.2f} MAD")
        lines.append(f"📋 Statut: {self.status.value}")
        return "\n".join(lines)
