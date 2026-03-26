"""
Outil CrewAI pour la recherche de produits dans la base de données Selfcare.
"""

from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
from sqlalchemy import or_
from database.connection import get_db_session
from database.models import ProductModel
import logging
import json

logger = logging.getLogger(__name__)


class SearchProductsInput(BaseModel):
    """Schéma d'entrée pour la recherche de produits."""
    query: str = Field(
        ...,
        description="Terme de recherche (nom de produit, catégorie, code). Ex: 'oulmes', 'eau', 'boisson'"
    )


class SearchProductsTool(BaseTool):
    """
    Outil pour rechercher des produits dans le catalogue Selfcare.
    Recherche par nom, code ou catégorie.
    """
    name: str = "search_products"
    description: str = (
        "Recherche des produits dans le catalogue Selfcare par nom, code ou catégorie. "
        "Retourne la liste des produits correspondants avec leurs prix et disponibilités. "
        "Utilise cette outil quand l'utilisateur cherche un produit ou veut connaître les produits disponibles."
    )
    args_schema: Type[BaseModel] = SearchProductsInput

    def _run(self, query: str) -> str:
        """Exécute la recherche de produits."""
        logger.info(f"🔍 Recherche de produits: '{query}'")

        try:
            with get_db_session() as db:
                search_term = f"%{query.strip()}%"
                products = (
                    db.query(ProductModel)
                    .filter(
                        ProductModel.is_available == True,
                        or_(
                            ProductModel.name.ilike(search_term),
                            ProductModel.code.ilike(search_term),
                            ProductModel.category.ilike(search_term),
                            ProductModel.description.ilike(search_term),
                        )
                    )
                    .limit(10)
                    .all()
                )

                if not products:
                    return json.dumps({
                        "success": True,
                        "count": 0,
                        "products": [],
                        "message": f"Aucun produit trouvé pour '{query}'"
                    }, ensure_ascii=False)

                results = [p.to_dict() for p in products]
                logger.info(f"✅ {len(results)} produit(s) trouvé(s) pour '{query}'")

                return json.dumps({
                    "success": True,
                    "count": len(results),
                    "products": results,
                    "message": f"{len(results)} produit(s) trouvé(s)"
                }, ensure_ascii=False)

        except Exception as e:
            logger.error(f"❌ Erreur lors de la recherche: {e}")
            return json.dumps({
                "success": False,
                "error": str(e),
                "message": "Erreur lors de la recherche de produits"
            }, ensure_ascii=False)


class GetProductByIdInput(BaseModel):
    """Schéma d'entrée pour récupérer un produit par ID."""
    product_id: int = Field(..., description="ID du produit à récupérer")


class GetProductByIdTool(BaseTool):
    """Outil pour récupérer un produit par son ID."""
    name: str = "get_product_by_id"
    description: str = "Récupère les détails d'un produit spécifique par son ID."
    args_schema: Type[BaseModel] = GetProductByIdInput

    def _run(self, product_id: int) -> str:
        """Récupère un produit par ID."""
        try:
            with get_db_session() as db:
                product = db.query(ProductModel).filter(ProductModel.id == product_id).first()
                if not product:
                    return json.dumps({
                        "success": False,
                        "message": f"Produit #{product_id} non trouvé"
                    }, ensure_ascii=False)

                return json.dumps({
                    "success": True,
                    "product": product.to_dict()
                }, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)
