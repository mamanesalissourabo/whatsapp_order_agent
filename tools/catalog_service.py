"""
Service MCP (Model Context Protocol) pour le catalogue produits.

Architecture MCP : sépare les données (ressources) des actions (outils)
et fournit un contexte structuré au modèle IA.

Ressources : données injectées dans le contexte du modèle
Outils : actions que le modèle peut déclencher
"""

import sqlite3
import logging
from typing import Optional
from database.catalog_db import get_connection

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# RESSOURCES MCP — Données contextuelles
# ─────────────────────────────────────────────

def get_catalog_context() -> str:
    """
    Ressource MCP : retourne le catalogue complet formaté pour injection
    dans le system prompt du modèle.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            p.code, p.nom, m.nom AS marque, c.nom AS categorie,
            p.contenance, p.format, p.unite_vente, p.nb_par_unite,
            p.prix_unite, p.disponible
        FROM produits p
        JOIN marques m ON p.marque_id = m.id
        JOIN categories c ON p.categorie_id = c.id
        ORDER BY m.nom, p.contenance DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return "⚠️ Catalogue vide."

    # Grouper par marque
    catalog_lines = ["# 📦 CATALOGUE PRODUITS OULMÈS (PRIX RÉELS)\n"]
    current_brand = None

    for row in rows:
        if row["marque"] != current_brand:
            current_brand = row["marque"]
            catalog_lines.append(f"\n## {current_brand}")

        dispo = "✅" if row["disponible"] else "❌ RUPTURE"
        catalog_lines.append(
            f"- **{row['nom']}** ({row['contenance']}, {row['format']}) | "
            f"{row['prix_unite']:.2f} DH/{row['unite_vente']} "
            f"({row['nb_par_unite']} unités) | {dispo} | Code: {row['code']}"
        )

    return "\n".join(catalog_lines)


def get_available_products_summary() -> str:
    """
    Ressource MCP : résumé court des produits disponibles
    pour le message de bienvenue.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT m.nom AS marque, COUNT(*) AS nb_produits
        FROM produits p
        JOIN marques m ON p.marque_id = m.id
        WHERE p.disponible = 1
        GROUP BY m.nom
        ORDER BY m.nom
    """)

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return "Catalogue indisponible."

    lines = []
    for row in rows:
        lines.append(f"• {row['marque']}")

    return "\n".join(lines)


# ─────────────────────────────────────────────
# OUTILS MCP — Actions du modèle
# ─────────────────────────────────────────────

def search_products(query: str) -> str:
    """
    Outil MCP : recherche de produits par nom, marque ou catégorie.
    """
    conn = get_connection()
    cursor = conn.cursor()

    search_term = f"%{query}%"
    cursor.execute("""
        SELECT 
            p.code, p.nom, m.nom AS marque, c.nom AS categorie,
            p.contenance, p.format, p.unite_vente, p.nb_par_unite,
            p.prix_unite, p.disponible
        FROM produits p
        JOIN marques m ON p.marque_id = m.id
        JOIN categories c ON p.categorie_id = c.id
        WHERE p.nom LIKE ? OR m.nom LIKE ? OR c.nom LIKE ? OR p.code LIKE ?
        ORDER BY m.nom, p.nom
    """, (search_term, search_term, search_term, search_term))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return f"Aucun produit trouvé pour '{query}'."

    lines = []
    for row in rows:
        dispo = "Disponible" if row["disponible"] else "RUPTURE"
        lines.append(
            f"• {row['nom']} | {row['prix_unite']:.2f} DH/{row['unite_vente']} "
            f"({row['nb_par_unite']} unités) | {dispo}"
        )

    return "\n".join(lines)


def get_product_by_code(code: str) -> Optional[dict]:
    """
    Outil MCP : récupère un produit par son code.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            p.code, p.nom, m.nom AS marque, c.nom AS categorie,
            p.contenance, p.format, p.unite_vente, p.nb_par_unite,
            p.prix_unite, p.disponible, p.description
        FROM produits p
        JOIN marques m ON p.marque_id = m.id
        JOIN categories c ON p.categorie_id = c.id
        WHERE p.code = ?
    """, (code,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return dict(row)


def get_brands() -> str:
    """
    Outil MCP : liste les marques disponibles.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT m.nom, m.description, COUNT(p.id) AS nb_produits
        FROM marques m
        LEFT JOIN produits p ON p.marque_id = m.id AND p.disponible = 1
        GROUP BY m.id
        ORDER BY m.nom
    """)

    rows = cursor.fetchall()
    conn.close()

    lines = []
    for row in rows:
        lines.append(f"• **{row['nom']}** — {row['description']} ({row['nb_produits']} produits)")

    return "\n".join(lines)


def get_products_by_brand(brand: str) -> str:
    """
    Outil MCP : liste les produits d'une marque.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            p.nom, p.contenance, p.format, p.unite_vente, 
            p.nb_par_unite, p.prix_unite, p.disponible
        FROM produits p
        JOIN marques m ON p.marque_id = m.id
        WHERE m.nom LIKE ?
        ORDER BY p.contenance DESC
    """, (f"%{brand}%",))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return f"Aucun produit trouvé pour la marque '{brand}'."

    lines = []
    for row in rows:
        dispo = "✅" if row["disponible"] else "❌"
        lines.append(
            f"• {row['nom']} ({row['contenance']}, {row['format']}) — "
            f"{row['prix_unite']:.2f} DH/{row['unite_vente']} "
            f"({row['nb_par_unite']} unités) {dispo}"
        )

    return "\n".join(lines)
