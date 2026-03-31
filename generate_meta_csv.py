"""
Génère un fichier CSV au format Meta Commerce Manager
pour importer les produits dans le catalogue WhatsApp.

Usage: python generate_meta_csv.py
Résultat: meta_catalog_products.csv (prêt à uploader)
"""

import csv
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "database", "catalog.db")
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), "meta_catalog_products.csv")


def generate():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            p.code,
            p.nom,
            p.description,
            p.prix_unite,
            p.disponible,
            p.contenance,
            p.format,
            p.unite_vente,
            p.nb_par_unite,
            m.nom AS marque,
            c.nom AS categorie
        FROM produits p
        JOIN marques m ON p.marque_id = m.id
        JOIN categories c ON p.categorie_id = c.id
        ORDER BY m.nom, p.nom
    """)

    products = cursor.fetchall()
    conn.close()

    # Meta Commerce CSV required columns:
    # id, title, description, availability, condition, price, link, image_link, brand
    # Optional: product_type, google_product_category
    
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        
        # Header row (Meta Commerce Manager required fields)
        writer.writerow([
            "id",
            "title",
            "description",
            "availability",
            "condition",
            "price",
            "link",
            "image_link",
            "brand",
            "product_type",
        ])
        
        for p in products:
            # id = product code (will be used as product_retailer_id in WhatsApp API)
            product_id = p["code"]
            
            # title (max 150 chars)
            title = p["nom"]
            
            # description
            desc = p["description"] or f"{p['marque']} - {p['nom']} ({p['contenance']}, {p['format']})"
            # Add unit info
            desc += f" | Vendu par {p['unite_vente']} de {p['nb_par_unite']}"
            
            # availability
            availability = "in stock" if p["disponible"] else "out of stock"
            
            # price (format: "27.00 MAD")
            price = f"{p['prix_unite']:.2f} MAD"
            
            # link (required - use a placeholder URL, can be updated later)
            link = f"https://oulmes.ma/produit/{product_id}"
            
            # image_link (required - placeholder, update with real product images)
            image_link = f"https://oulmes.ma/images/{product_id}.jpg"
            
            # brand
            brand = p["marque"]
            
            # product_type (category)
            product_type = f"{p['categorie']} > {p['marque']}"
            
            writer.writerow([
                product_id,
                title,
                desc,
                availability,
                "new",
                price,
                link,
                image_link,
                brand,
                product_type,
            ])
    
    print(f"✅ CSV généré : {OUTPUT_CSV}")
    print(f"📦 {len(products)} produits exportés")
    print(f"\n📋 Colonnes : id, title, description, availability, condition, price, link, image_link, brand, product_type")
    print(f"\n⚠️  IMPORTANT :")
    print(f"   - Les URLs 'link' et 'image_link' sont des placeholders")
    print(f"   - Meta accepte les placeholders pour WhatsApp Commerce")
    print(f"   - Le champ 'id' correspond au product_retailer_id utilisé dans l'API WhatsApp")


if __name__ == "__main__":
    generate()
