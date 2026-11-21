"""Generates synthetic data for DarPilot.

This script creates fictional real estate listings in Morocco (Casablanca/Marrakech)
to populate the database for development and testing.

Rules:
- No real names or contact details.
- Prices in MAD.
- Neighborhoods appropriate for the cities.
"""

import random
import sqlite3
from pathlib import Path

# Data for generation
CITIES = {
    "Casablanca": ["Anfa", "Maarif", "Gauthier", "Sidi Maarouf"],
    "Marrakech": ["Gueliz", "Hivernage", "Medina", "Palmeraie"]
}
TYPES = ["Apartment", "Villa", "Studio", "Riad"]
ADJECTIVES = ["Charming", "Modern", "Spacious", "Renovated", "Bright"]
NOUNS = ["apartment", "villa", "studio", "residence"]

def generate_listings(n=100):
    listings = []
    for _ in range(n):
        city = random.choice(list(CITIES.keys()))
        neighborhood = random.choice(CITIES[city])
        p_type = random.choice(TYPES)
        title = f"{random.choice(ADJECTIVES)} {p_type} in {neighborhood}"
        price = random.randint(500000, 5000000)
        
        listings.append((
            title,
            f"Beautiful {p_type.lower()} located in {neighborhood}, {city}.",
            price,
            city,
            neighborhood,
            p_type,
            "available",
            None  # agent_id
        ))
    return listings

def populate_db():
    db_path = Path(__file__).resolve().parent.parent / "darpilot.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Check if listings already exist
    cursor.execute("SELECT count(*) FROM listings")
    if cursor.fetchone()[0] > 0:
        print("Listings already exist. Skipping population.")
        conn.close()
        return

    data = generate_listings(100)
    cursor.executemany(
        """INSERT INTO listings (title, description, price_mad, city, neighborhood, property_type, status, agent_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        data
    )
    conn.commit()
    print(f"Inserted 100 synthetic listings.")
    conn.close()

if __name__ == "__main__":
    populate_db()
