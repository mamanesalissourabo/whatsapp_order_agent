"""
Base de données SQLite pour le catalogue produits Oulmès.
Indépendante de PostgreSQL - fonctionne en local sans config externe.
"""

import sqlite3
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "catalog.db")


def get_connection() -> sqlite3.Connection:
    """Retourne une connexion SQLite avec row_factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_catalog_db():
    """Crée les tables du catalogue si elles n'existent pas."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS marques (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL UNIQUE,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS produits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            nom TEXT NOT NULL,
            marque_id INTEGER NOT NULL,
            categorie_id INTEGER NOT NULL,
            format TEXT NOT NULL,
            contenance TEXT NOT NULL,
            unite_vente TEXT NOT NULL DEFAULT 'caisse',
            nb_par_unite INTEGER NOT NULL DEFAULT 12,
            prix_unite REAL NOT NULL,
            disponible INTEGER NOT NULL DEFAULT 1,
            description TEXT,
            FOREIGN KEY (marque_id) REFERENCES marques(id),
            FOREIGN KEY (categorie_id) REFERENCES categories(id)
        );
    """)

    conn.commit()
    conn.close()
    logger.info("✅ Tables catalogue créées/vérifiées")


def seed_catalog():
    """Peuple le catalogue avec les produits Oulmès."""
    conn = get_connection()
    cursor = conn.cursor()

    # Vérifier si déjà peuplé
    cursor.execute("SELECT COUNT(*) FROM produits")
    if cursor.fetchone()[0] > 0:
        conn.close()
        logger.info("📦 Catalogue déjà peuplé")
        return

    # --- Marques --- (IDs attribués par AUTOINCREMENT)
    # Eaux : Sidi Ali (1), Aïn Atlas (3), Bahia (4), Vitalya (5)
    # Eau gazeuse + Boissons : Oulmès (2) — seule marque dans les deux catégories
    # Boissons : Orangina (6), GLASS' (7), Banga (8)
    marques = [
        ("Sidi Ali", "Eau minérale naturelle plate"),                # id=1
        ("Oulmès", "Eau minérale naturelle gazeuse et boissons"),    # id=2
        ("Aïn Atlas", "Eau de source naturelle"),                    # id=3
        ("Bahia", "Eau plate naturelle"),                            # id=4
        ("Vitalya", "Eau minérale enrichie"),                        # id=5
        ("Orangina", "Boisson gazeuse à l'orange"),                  # id=6
        ("GLASS'", "Boisson gazeuse aux fruits"),                    # id=7
        ("Banga", "Boisson fruitée"),                                # id=8
    ]
    cursor.executemany("INSERT INTO marques (nom, description) VALUES (?, ?)", marques)

    # --- Catégories ---
    categories = [
        ("Eau plate",),             # id=1
        ("Eau gazeuse",),           # id=2
        ("Boisson gazeuse",),       # id=3
        ("Boisson fruitée",),       # id=4
        ("Eau fonctionnelle",),     # id=5
        ("Bonbonne & Fontaine",),   # id=6
        ("Enfants",),               # id=7
    ]
    cursor.executemany("INSERT INTO categories (nom) VALUES (?)", categories)

    # --- Produits ---
    # (code, nom, marque_id, categorie_id, format, contenance, unite_vente, nb_par_unite, prix_unite, disponible, description)
    produits = [
        # ==================== SIDI ALI (marque_id=1) ====================
        # Eau plate
        ("SA-6x1L", "Sidi Ali pack 6x1L", 1, 1, "PET", "1L", "pack", 6, 27.00, 1, "Eau minérale naturelle plate 6x1L"),
        ("SA-6x150", "Sidi Ali pack 6x1,5L", 1, 1, "PET", "1.5L", "pack", 6, 33.00, 1, "Eau minérale naturelle plate 6x1,5L"),
        ("SA-12x50", "Sidi Ali pack 12x50cl", 1, 1, "PET", "50cl", "pack", 12, 42.00, 1, "Eau minérale naturelle plate 12x50cl"),
        ("SA-12x33", "Sidi Ali pack 12x33cl", 1, 1, "PET", "33cl", "pack", 12, 24.00, 1, "Eau minérale naturelle plate 12x33cl"),
        ("SA-4x2L", "Sidi Ali pack 4x2L", 1, 1, "PET", "2L", "pack", 4, 24.00, 1, "Eau minérale naturelle plate 4x2L"),
        ("SA-VER-12x50", "Sidi Ali bouteille verre pack 12x50cl", 1, 1, "Verre", "50cl", "pack", 12, 96.00, 1, "Eau minérale naturelle plate verre 12x50cl"),
        ("SA-VER-12x75", "Sidi Ali bouteille verre pack 12x75cl", 1, 1, "Verre", "75cl", "pack", 12, 144.00, 1, "Eau minérale naturelle plate verre 12x75cl"),
        ("SA-VER-12x33", "Sidi Ali bouteille verre pack 12x33cl", 1, 1, "Verre", "33cl", "pack", 12, 72.00, 1, "Eau minérale naturelle plate verre 12x33cl"),
        ("SA-SPORT-6x75", "Sidi Ali Bouchon sport pack 6x75cl", 1, 1, "PET Sport", "75cl", "pack", 6, 24.00, 1, "Eau minérale plate bouchon sport 6x75cl"),
        ("SA-NAISS-12x50", "Sidi Ali naissance pack 12x50cl", 1, 1, "PET", "50cl", "pack", 12, 42.00, 1, "Eau minérale spéciale naissance 12x50cl"),
        # Sidi Ali Kids — catégorie Enfants
        ("SA-KIDS-NACHET", "Sidi Ali Kids NACHET orange pack 6x33cl", 1, 7, "PET", "33cl", "pack", 6, 15.00, 1, "Eau pour enfants NACHET orange 6x33cl"),
        ("SA-KIDS-BATALA", "Sidi Ali Kids BATALA vert pack 6x33cl", 1, 7, "PET", "33cl", "pack", 6, 15.00, 1, "Eau pour enfants BATALA vert 6x33cl"),
        ("SA-KIDS-ZINA", "Sidi Ali Kids ZINA Rose pack 6x33cl", 1, 7, "PET", "33cl", "pack", 6, 15.00, 1, "Eau pour enfants ZINA Rose 6x33cl"),
        ("SA-KIDS-RIYADI", "Sidi Ali Kids RIYADI bleu ciel pack 6x33cl", 1, 7, "PET", "33cl", "pack", 6, 15.00, 1, "Eau pour enfants RIYADI bleu ciel 6x33cl"),
        ("SA-KIDS-MTEWRA", "Sidi Ali Kids MTEWRA rouge pack 6x33cl", 1, 7, "PET", "33cl", "pack", 6, 15.00, 1, "Eau pour enfants MTEWRA rouge 6x33cl"),

        # ==================== OULMÈS (marque_id=2) ====================
        # Eau gazeuse
        ("OUL-12x33", "Oulmès pack 12x33cl", 2, 2, "PET", "33cl", "pack", 12, 48.00, 1, "Eau minérale gazeuse 12x33cl"),
        ("OUL-VER-12x75", "Oulmès Easy Open verre pack 12x75cl", 2, 2, "Verre", "75cl", "pack", 12, 156.00, 1, "Eau minérale gazeuse Easy Open verre 12x75cl"),
        ("OUL-VER-12x25", "Oulmès classique verre pack 12x25cl", 2, 2, "Verre", "25cl", "pack", 12, 60.00, 1, "Eau minérale gazeuse classique verre 12x25cl"),
        ("OUL-VER-12x33", "Oulmès verre pack 12x33cl", 2, 2, "Verre", "33cl", "pack", 12, 84.00, 1, "Eau minérale gazeuse verre 12x33cl"),
        # Oulmès Bulles Fruitées — catégorie Boisson gazeuse
        ("OUL-BF-MOJITO", "Oulmès Bulles Fruitées Mojito verre pack 12x25cl", 2, 3, "Verre", "25cl", "pack", 12, 96.00, 1, "Bulles Fruitées Mojito verre 12x25cl"),
        ("OUL-BF-TROPIC", "Oulmès Bulles Fruitées Tropic verre pack 12x25cl", 2, 3, "Verre", "25cl", "pack", 12, 96.00, 1, "Bulles Fruitées Tropic verre 12x25cl"),
        ("OUL-BF-ORANGE", "Oulmès Bulles Fruitées Orange verre pack 12x25cl", 2, 3, "Verre", "25cl", "pack", 12, 96.00, 1, "Bulles Fruitées Orange verre 12x25cl"),
        ("OUL-BF-ROUGE", "Oulmès Bulles Fruitées rouges verre pack 12x25cl", 2, 3, "Verre", "25cl", "pack", 12, 96.00, 1, "Bulles Fruitées rouges verre 12x25cl"),
        ("OUL-BF-PINA", "Oulmès Bulles Piña Colada verre pack 12x25cl", 2, 3, "Verre", "25cl", "pack", 12, 96.00, 1, "Bulles Piña Colada verre 12x25cl"),

        # ==================== AÏN ATLAS (marque_id=3) ====================
        ("AA-6x150", "Aïn Atlas pack 6x1,5L", 3, 1, "PET", "1.5L", "pack", 6, 33.00, 1, "Eau de source naturelle 6x1,5L"),
        ("AA-2x5L", "Aïn Atlas pack 2x5L", 3, 1, "PET", "5L", "pack", 2, 23.80, 1, "Eau de source naturelle 2x5L"),
        ("AA-12x50", "Aïn Atlas pack 12x50cl", 3, 1, "PET", "50cl", "pack", 12, 36.00, 1, "Eau de source naturelle 12x50cl"),
        ("AA-12x33", "Aïn Atlas pack 12x33cl", 3, 1, "PET", "33cl", "pack", 12, 24.00, 1, "Eau de source naturelle 12x33cl"),
        ("AA-SPORT-12x50", "Aïn Atlas bouchons sport pack 12x50cl", 3, 1, "PET Sport", "50cl", "pack", 12, 42.00, 1, "Eau de source bouchon sport 12x50cl"),

        # ==================== BAHIA (marque_id=4) ====================
        # Eau plate
        ("BAH-2x5L", "Bahia pack 2x5L", 4, 1, "PET", "5L", "pack", 2, 22.00, 1, "Eau plate naturelle 2x5L"),
        ("BAH-6x150", "Bahia pack 6x1,5L", 4, 1, "PET", "1.5L", "pack", 6, 24.00, 1, "Eau plate naturelle 6x1,5L"),
        # Bonbonne & Fontaine
        ("BAH-BON-AC", "Bahia bonbonne 18,9L avec consignation", 4, 6, "Bonbonne", "18.9L", "unité", 1, 59.00, 1, "Bonbonne Bahia 18,9L avec consignation"),
        ("BAH-BON-SC", "Bahia bonbonne 18,9L sans consignation", 4, 6, "Bonbonne", "18.9L", "unité", 1, 39.00, 1, "Bonbonne Bahia 18,9L sans consignation"),
        ("BAH-FONTAINE", "Fontaine à eau Bahia", 4, 6, "Fontaine", "N/A", "unité", 1, 1150.00, 1, "Fontaine à eau Bahia"),

        # ==================== VITALYA (marque_id=5) ====================
        # Eau plate
        ("VIT-6x150", "Vitalya pack 6x1,5L", 5, 1, "PET", "1.5L", "pack", 6, 30.00, 1, "Eau minérale enrichie 6x1,5L"),
        ("VIT-2x5L", "Vitalya pack 2x5L", 5, 1, "PET", "5L", "pack", 2, 26.00, 1, "Eau minérale enrichie 2x5L"),
        ("VIT-12x33", "Vitalya pack 12x33cl", 5, 1, "PET", "33cl", "pack", 12, 24.00, 1, "Eau minérale enrichie 12x33cl"),
        ("VIT-12x50", "Vitalya pack 12x50cl", 5, 1, "PET", "50cl", "pack", 12, 36.00, 1, "Eau minérale enrichie 12x50cl"),
        ("VIT-4x2L", "Vitalya pack 4x2L", 5, 1, "PET", "2L", "pack", 4, 24.00, 1, "Eau minérale enrichie 4x2L"),
        # Eau fonctionnelle
        ("VIT-ALC-12x50", "Vitalya alcaline pack 12x50cl", 5, 5, "PET", "50cl", "pack", 12, 48.00, 1, "Eau alcaline enrichie 12x50cl"),
        ("VIT-BOOST-12x50", "Vitalya boost pack 12x50cl", 5, 5, "PET", "50cl", "pack", 12, 48.00, 1, "Eau boost enrichie 12x50cl"),
        # Bonbonne & Fontaine
        ("VIT-BON-SC", "Vitalya bonbonne 18,9L sans consignation", 5, 6, "Bonbonne", "18.9L", "unité", 1, 45.00, 1, "Bonbonne Vitalya 18,9L sans consignation"),
        ("VIT-BON-AC", "Vitalya bonbonne 18,9L avec consignation", 5, 6, "Bonbonne", "18.9L", "unité", 1, 65.00, 1, "Bonbonne Vitalya 18,9L avec consignation"),
        ("VIT-FONTAINE", "Fontaine à eau Vitalya", 5, 6, "Fontaine", "N/A", "unité", 1, 1390.00, 1, "Fontaine à eau Vitalya"),

        # ==================== ORANGINA (marque_id=6) ====================
        ("ORA-6x1L", "Orangina pack 6x1L", 6, 3, "PET", "1L", "pack", 6, 66.00, 1, "Boisson gazeuse à l'orange 6x1L"),
        ("ORA-Z-6x1L", "Orangina Zero pack 6x1L", 6, 3, "PET", "1L", "pack", 6, 66.00, 1, "Boisson gazeuse à l'orange zero 6x1L"),
        ("ORA-8x50", "Orangina pack 8x50cl", 6, 3, "PET", "50cl", "pack", 8, 56.00, 1, "Boisson gazeuse à l'orange 8x50cl"),
        ("ORA-Z-8x50", "Orangina Zero pack 8x50cl", 6, 3, "PET", "50cl", "pack", 8, 56.00, 1, "Boisson gazeuse à l'orange zero 8x50cl"),
        ("ORA-CAN-12x25", "Orangina pack canettes 12x25cl", 6, 3, "Canette", "25cl", "pack", 12, 46.80, 1, "Boisson gazeuse à l'orange canettes 12x25cl"),

        # ==================== GLASS' (marque_id=7) ====================
        # Cola
        ("GLS-COLA-12x33", "Glass' Cola pack 12x33cl", 7, 3, "PET", "33cl", "pack", 12, 42.00, 1, "Glass' Cola 12x33cl"),
        ("GLS-COLA-6x150", "Glass' Cola pack 6x1.5L", 7, 3, "PET", "1.5L", "pack", 6, 42.00, 1, "Glass' Cola 6x1.5L"),
        ("GLS-COLA-6x1L", "Glass' Cola pack 6x1L", 7, 3, "PET", "1L", "pack", 6, 30.00, 1, "Glass' Cola 6x1L"),
        ("GLS-COLA-CAN", "Glass' Cola Canette 12x25cl", 7, 3, "Canette", "25cl", "pack", 12, 36.00, 1, "Glass' Cola canette 12x25cl"),
        ("GLS-COLA0-CAN", "Glass' Cola Zéro Canette 12x25cl", 7, 3, "Canette", "25cl", "pack", 12, 36.00, 1, "Glass' Cola Zéro canette 12x25cl"),
        # Tropical
        ("GLS-TROP-12x33", "Glass' Tropical pack 12x33cl", 7, 3, "PET", "33cl", "pack", 12, 42.00, 1, "Glass' Tropical 12x33cl"),
        ("GLS-TROP-6x150", "Glass' Tropical pack 6x1.5L", 7, 3, "PET", "1.5L", "pack", 6, 42.00, 1, "Glass' Tropical 6x1.5L"),
        ("GLS-TROP-6x1L", "Glass' Tropical pack 6x1L", 7, 3, "PET", "1L", "pack", 6, 30.00, 1, "Glass' Tropical 6x1L"),
        ("GLS-TROP-CAN", "Glass' Tropical Canette 12x25cl", 7, 3, "Canette", "25cl", "pack", 12, 36.00, 1, "Glass' Tropical canette 12x25cl"),
        # Pomme
        ("GLS-POM-12x33", "Glass' Pomme pack 12x33cl", 7, 3, "PET", "33cl", "pack", 12, 42.00, 1, "Glass' Pomme 12x33cl"),
        ("GLS-POM-6x150", "Glass' Pomme pack 6x1.5L", 7, 3, "PET", "1.5L", "pack", 6, 42.00, 1, "Glass' Pomme 6x1.5L"),
        ("GLS-POM-6x1L", "Glass' Pomme pack 6x1L", 7, 3, "PET", "1L", "pack", 6, 30.00, 1, "Glass' Pomme 6x1L"),
        ("GLS-POM-CAN", "Glass' Pomme Canette 12x25cl", 7, 3, "Canette", "25cl", "pack", 12, 36.00, 1, "Glass' Pomme canette 12x25cl"),
        # Lime
        ("GLS-LIME-6x1L", "Glass' Lime pack 6x1L", 7, 3, "PET", "1L", "pack", 6, 30.00, 1, "Glass' Lime 6x1L"),
        ("GLS-LIME-CAN", "Glass' Lime Canette 12x25cl", 7, 3, "Canette", "25cl", "pack", 12, 36.00, 1, "Glass' Lime canette 12x25cl"),
        # Tonic
        ("GLS-TONIC-6x1L", "Glass' Tonic pack 6x1L", 7, 3, "PET", "1L", "pack", 6, 30.00, 1, "Glass' Tonic 6x1L"),
        ("GLS-TONIC-CAN", "Glass' Tonic Canette 12x25cl", 7, 3, "Canette", "25cl", "pack", 12, 36.00, 1, "Glass' Tonic canette 12x25cl"),
        # Ananas
        ("GLS-ANAN-6x150", "Glass' Ananas pack 6x1.5L", 7, 3, "PET", "1.5L", "pack", 6, 42.00, 1, "Glass' Ananas 6x1.5L"),

        # ==================== BANGA (marque_id=8) ====================
        ("BNG-AGR-8x1L", "Banga Agrumes pack 8x1L", 8, 4, "PET", "1L", "pack", 8, 52.00, 1, "Boisson fruitée Agrumes 8x1L"),
        ("BNG-LEM-8x1L", "Banga Lemon pack 8x1L", 8, 4, "PET", "1L", "pack", 8, 52.00, 1, "Boisson fruitée Lemon 8x1L"),
        ("BNG-POM-8x1L", "Banga Pomme pack 8x1L", 8, 4, "PET", "1L", "pack", 8, 52.00, 1, "Boisson fruitée Pomme 8x1L"),
        ("BNG-TRP-8x1L", "Banga Tropical pack 8x1L", 8, 4, "PET", "1L", "pack", 8, 52.00, 1, "Boisson fruitée Tropical 8x1L"),
        ("BNG-AGR-12x25", "Banga Agrumes pack 12x25cl", 8, 4, "PET", "25cl", "pack", 12, 45.00, 1, "Boisson fruitée Agrumes 12x25cl"),
        ("BNG-LEM-12x25", "Banga Lemon pack 12x25cl", 8, 4, "PET", "25cl", "pack", 12, 45.00, 1, "Boisson fruitée Lemon 12x25cl"),
        ("BNG-POM-12x25", "Banga Pomme pack 12x25cl", 8, 4, "PET", "25cl", "pack", 12, 45.00, 1, "Boisson fruitée Pomme 12x25cl"),
        ("BNG-TRP-12x25", "Banga Tropical pack 12x25cl", 8, 4, "PET", "25cl", "pack", 12, 45.00, 1, "Boisson fruitée Tropical 12x25cl"),
    ]

    cursor.executemany(
        """INSERT INTO produits 
           (code, nom, marque_id, categorie_id, format, contenance, unite_vente, nb_par_unite, prix_unite, disponible, description) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        produits,
    )

    conn.commit()
    conn.close()
    logger.info(f"✅ Catalogue peuplé : {len(produits)} produits, {len(marques)} marques")
