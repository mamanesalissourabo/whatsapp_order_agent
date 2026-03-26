"""
Schémas Pydantic pour les produits du catalogue Selfcare.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal


class Product(BaseModel):
    """Produit du catalogue Selfcare."""
    id: int = Field(..., description="ID du produit")
    code: str = Field(..., description="Code produit")
    name: str = Field(..., description="Nom du produit")
    description: Optional[str] = Field(None, description="Description du produit")
    unit_price: float = Field(..., description="Prix unitaire en MAD")
    unit_type: str = Field(default="caisse", description="Unité de mesure (caisse, pack, unité)")
    category: Optional[str] = Field(None, description="Catégorie de produit")
    is_available: bool = Field(default=True, description="Disponibilité du produit")
    min_quantity: int = Field(default=1, description="Quantité minimale de commande")
    image_url: Optional[str] = Field(None, description="URL de l'image du produit")

    def format_display(self) -> str:
        """Formate le produit pour affichage WhatsApp."""
        return f"{self.name} - {self.unit_price:.2f} MAD/{self.unit_type}"


class ProductSearchResult(BaseModel):
    """Résultat de recherche de produits."""
    products: List[Product] = Field(default_factory=list)
    total_count: int = Field(default=0)
    query: str = Field(default="", description="Requête de recherche utilisée")

    def format_list(self) -> str:
        """Formate la liste de produits pour affichage."""
        if not self.products:
            return "Aucun produit trouvé."
        lines = [f"{i+1}. {p.format_display()}" for i, p in enumerate(self.products)]
        return "\n".join(lines)
