"""
Outils (Tools) pour les agents CrewAI.
Ces outils permettent aux agents d'interagir avec les systèmes backend.
"""

from tools.product_search import SearchProductsTool
from tools.cart_manager import AddToCartTool, RemoveFromCartTool, ViewCartTool
from tools.whatsapp_sender import SendWhatsAppMessageTool
from tools.session_manager import SessionManager

__all__ = [
    "SearchProductsTool",
    "AddToCartTool", "RemoveFromCartTool", "ViewCartTool",
    "SendWhatsAppMessageTool",
    "SessionManager",
]
