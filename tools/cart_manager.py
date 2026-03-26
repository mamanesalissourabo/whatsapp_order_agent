"""
Outil CrewAI pour la gestion du panier d'achat via Redis.
"""

from crewai.tools import BaseTool
from typing import Type, Optional
from pydantic import BaseModel, Field
from tools.session_manager import SessionManager
from schemas.orders import CartItem
import logging
import json

logger = logging.getLogger(__name__)

# Instance partagée du gestionnaire de sessions
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Récupère ou crée l'instance du SessionManager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


class AddToCartInput(BaseModel):
    """Schéma d'entrée pour ajouter un produit au panier."""
    phone_number: str = Field(..., description="Numéro WhatsApp du client")
    product_id: int = Field(..., description="ID du produit à ajouter")
    product_name: str = Field(..., description="Nom du produit")
    product_code: str = Field(default="", description="Code produit")
    quantity: int = Field(..., ge=1, description="Quantité à ajouter")
    unit_price: float = Field(..., description="Prix unitaire en MAD")
    unit_type: str = Field(default="caisse", description="Unité de mesure")


class AddToCartTool(BaseTool):
    """Outil pour ajouter un produit au panier du client."""
    name: str = "add_to_cart"
    description: str = (
        "Ajoute un produit au panier du client. "
        "Nécessite l'ID du produit, son nom, la quantité et le prix unitaire. "
        "Si le produit est déjà dans le panier, la quantité est cumulée."
    )
    args_schema: Type[BaseModel] = AddToCartInput

    def _run(
        self,
        phone_number: str,
        product_id: int,
        product_name: str,
        quantity: int,
        unit_price: float,
        product_code: str = "",
        unit_type: str = "caisse",
    ) -> str:
        """Ajoute un produit au panier."""
        logger.info(f"🛒 Ajout au panier: {product_name} x{quantity} pour {phone_number}")

        try:
            sm = get_session_manager()
            session = sm.get_session(phone_number)

            # Reconstruire le panier depuis la session
            cart_items = session.cart.get("items", [])

            # Vérifier si le produit existe déjà
            found = False
            for item in cart_items:
                if item["product_id"] == product_id:
                    item["quantity"] += quantity
                    found = True
                    break

            if not found:
                cart_items.append({
                    "product_id": product_id,
                    "product_name": product_name,
                    "product_code": product_code,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "unit_type": unit_type,
                })

            # Calculer le total
            total = sum(i["quantity"] * i["unit_price"] for i in cart_items)

            # Mettre à jour la session
            session.cart = {"items": cart_items, "total": total}
            sm.save_session(session)

            logger.info(f"✅ Panier mis à jour: {len(cart_items)} article(s), total {total:.2f} MAD")

            return json.dumps({
                "success": True,
                "message": f"{product_name} x{quantity} ajouté au panier",
                "cart": {"items": cart_items, "total": total, "item_count": len(cart_items)},
            }, ensure_ascii=False)

        except Exception as e:
            logger.error(f"❌ Erreur ajout panier: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


class RemoveFromCartInput(BaseModel):
    """Schéma d'entrée pour retirer un produit du panier."""
    phone_number: str = Field(..., description="Numéro WhatsApp du client")
    product_id: int = Field(..., description="ID du produit à retirer")


class RemoveFromCartTool(BaseTool):
    """Outil pour retirer un produit du panier."""
    name: str = "remove_from_cart"
    description: str = "Retire un produit du panier du client en utilisant l'ID du produit."
    args_schema: Type[BaseModel] = RemoveFromCartInput

    def _run(self, phone_number: str, product_id: int) -> str:
        """Retire un produit du panier."""
        logger.info(f"🗑️ Retrait du produit #{product_id} du panier de {phone_number}")

        try:
            sm = get_session_manager()
            session = sm.get_session(phone_number)
            cart_items = session.cart.get("items", [])

            original_count = len(cart_items)
            cart_items = [i for i in cart_items if i["product_id"] != product_id]

            if len(cart_items) == original_count:
                return json.dumps({
                    "success": False,
                    "message": f"Produit #{product_id} non trouvé dans le panier"
                }, ensure_ascii=False)

            total = sum(i["quantity"] * i["unit_price"] for i in cart_items)
            session.cart = {"items": cart_items, "total": total}
            sm.save_session(session)

            return json.dumps({
                "success": True,
                "message": "Produit retiré du panier",
                "cart": {"items": cart_items, "total": total, "item_count": len(cart_items)},
            }, ensure_ascii=False)

        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


class ViewCartInput(BaseModel):
    """Schéma d'entrée pour consulter le panier."""
    phone_number: str = Field(..., description="Numéro WhatsApp du client")


class ViewCartTool(BaseTool):
    """Outil pour consulter le contenu du panier."""
    name: str = "view_cart"
    description: str = "Affiche le contenu actuel du panier du client avec le total."
    args_schema: Type[BaseModel] = ViewCartInput

    def _run(self, phone_number: str) -> str:
        """Affiche le panier."""
        try:
            sm = get_session_manager()
            session = sm.get_session(phone_number)
            cart_items = session.cart.get("items", [])
            total = session.cart.get("total", 0)

            return json.dumps({
                "success": True,
                "cart": {"items": cart_items, "total": total, "item_count": len(cart_items)},
            }, ensure_ascii=False)

        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
