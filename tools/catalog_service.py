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


# ─────────────────────────────────────────────
# FONCTIONS INTERACTIVES — Données pour messages WhatsApp interactifs
# ─────────────────────────────────────────────

def get_brands_for_interactive() -> list[dict]:
    """
    Retourne les marques formatées pour un message interactif WhatsApp (list message).
    Seules les marques ayant au moins un produit disponible sont incluses.

    Returns:
        Liste de rows : [{"id": "brand_<nom>", "title": str, "description": str}]
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT m.nom, m.description, COUNT(p.id) AS nb_produits
        FROM marques m
        JOIN produits p ON p.marque_id = m.id AND p.disponible = 1
        GROUP BY m.id
        HAVING nb_produits > 0
        ORDER BY m.nom
    """)

    rows = cursor.fetchall()
    conn.close()

    result = []
    for row in rows:
        result.append({
            "id": f"brand_{row['nom']}",
            "title": row["nom"][:24],
            "description": f"{row['description'][:50]} ({row['nb_produits']} produits)"[:72],
        })
    return result


def get_products_by_brand_for_interactive(brand_name: str) -> list[dict]:
    """
    Retourne les produits disponibles d'une marque avec choix de quantité intégré.
    Chaque produit apparaît avec plusieurs options de quantité (1, 3, 5)
    pour que le client choisisse en un seul clic.

    Returns:
        Liste de sections WhatsApp.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            p.code, p.nom, c.nom AS categorie,
            p.contenance, p.format, p.unite_vente,
            p.nb_par_unite, p.prix_unite
        FROM produits p
        JOIN marques m ON p.marque_id = m.id
        JOIN categories c ON p.categorie_id = c.id
        WHERE m.nom = ? AND p.disponible = 1
        ORDER BY c.nom, p.prix_unite
    """, (brand_name,))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return []

    # WhatsApp limite à 10 rows total par message interactif
    # Si ≤5 produits : afficher quantités intégrées (2 options par produit)
    # Si >5 produits : 1 row par produit, quantité choisie après
    if len(rows) <= 5:
        QUANTITIES = [1, 5]
        sections = []
        total_rows = 0
        for row in rows:
            product_rows = []
            for qty in QUANTITIES:
                total = row["prix_unite"] * qty
                product_rows.append({
                    "id": f"add_{row['code']}_{qty}",
                    "title": f"{qty}x — {total:.2f} DH",
                    "description": f"{row['prix_unite']:.2f} DH/{row['unite_vente']}"[:72],
                })
            if total_rows + len(product_rows) > 10:
                break
            total_rows += len(product_rows)
            sections.append({
                "title": _truncate_product_title(row["nom"], row["contenance"]),
                "rows": product_rows,
            })
        return sections[:10]
    else:
        # Mode liste simple : 1 row par produit (max 10)
        sections_map: dict[str, list] = {}
        for row in rows:
            cat = row["categorie"]
            if cat not in sections_map:
                sections_map[cat] = []
            sections_map[cat].append({
                "id": f"product_{row['code']}",
                "title": _truncate_product_title(row["nom"], row["contenance"]),
                "description": f"{row['prix_unite']:.2f} DH/{row['unite_vente']} ({row['nb_par_unite']} unités)"[:72],
            })

        sections = []
        total_rows = 0
        for cat_name, products in sections_map.items():
            remaining = 10 - total_rows
            if remaining <= 0:
                break
            chunk = products[:remaining]
            total_rows += len(chunk)
            sections.append({
                "title": cat_name[:24],
                "rows": chunk,
            })
        return sections[:10]


def get_product_details_by_code(code: str) -> dict | None:
    """
    Retourne les détails complets d'un produit par son code.
    Utilisé quand un client sélectionne un produit dans la liste interactive.
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
        WHERE p.code = ? AND p.disponible = 1
    """, (code,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return dict(row)


def _truncate_product_title(nom: str, contenance: str) -> str:
    """Tronque le titre produit pour respecter la limite WhatsApp de 24 chars."""
    if len(nom) <= 24:
        return nom
    short = nom.replace("pack ", "")
    if len(short) <= 24:
        return short
    return short[:21] + "..."
