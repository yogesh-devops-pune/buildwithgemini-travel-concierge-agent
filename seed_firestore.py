import sys
from google.cloud import firestore

# Hardcoded project ID as required to prevent project number resolution issues on Agent Platform
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-01-580706c5bcf8"

SEED_DESTINATIONS = [
    {
        "id": "kyoto-japan",
        "name": "Kyoto Ancient Temples & Gardens",
        "city": "Kyoto",
        "country": "Japan",
        "category": "Culture",
        "description": "Historic city famed for classical Buddhist temples, shrines, traditional wooden houses, and cherry blossom gardens.",
        "best_season": "Spring / Autumn",
        "average_cost_per_day_usd": 180.0,
        "tags": ["temples", "culture", "nature", "food"]
    },
    {
        "id": "san-francisco-usa",
        "name": "San Francisco Bay & Golden Gate",
        "city": "San Francisco",
        "country": "USA",
        "category": "Landmarks",
        "description": "Iconic city featuring the Golden Gate Bridge, cable cars, vibrant food scene, and historic waterfront piers.",
        "best_season": "Autumn",
        "average_cost_per_day_usd": 250.0,
        "tags": ["city", "ocean", "food", "tech"]
    },
    {
        "id": "paris-france",
        "name": "Paris Art & Culinary Discovery",
        "city": "Paris",
        "country": "France",
        "category": "Food & Art",
        "description": "Global center for art, fashion, gastronomy and culture with world-class museums and cafe culture.",
        "best_season": "Spring / Summer",
        "average_cost_per_day_usd": 220.0,
        "tags": ["art", "museums", "dining", "romance"]
    },
    {
        "id": "banff-canada",
        "name": "Banff National Park & Rockies",
        "city": "Banff",
        "country": "Canada",
        "category": "Nature",
        "description": "Breathtaking turquoise glacial lakes, mountain peaks, hiking trails, and abundant wildlife.",
        "best_season": "Summer / Winter",
        "average_cost_per_day_usd": 200.0,
        "tags": ["mountains", "hiking", "lakes", "outdoors"]
    },
    {
        "id": "rio-de-janeiro-brazil",
        "name": "Rio Coastal Wonders & Carnival",
        "city": "Rio de Janeiro",
        "country": "Brazil",
        "category": "Beach & Culture",
        "description": "Famous for Copacabana and Ipanema beaches, Christ the Redeemer statue, and vibrant Samba culture.",
        "best_season": "Summer",
        "average_cost_per_day_usd": 140.0,
        "tags": ["beach", "music", "landmarks", "festivals"]
    }
]

def seed_database():
    print(f"Connecting to Firestore with Project ID: {FIRESTORE_PROJECT_ID}...")
    db = firestore.Client(project=FIRESTORE_PROJECT_ID)
    collection_ref = db.collection("destinations")

    for dest in SEED_DESTINATIONS:
        doc_id = dest["id"]
        doc_ref = collection_ref.document(doc_id)
        doc_ref.set(dest)
        print(f"  ✓ Seeded destination: {doc_id} ({dest['name']})")

    print("\n✅ Firestore seeding complete!")

if __name__ == "__main__":
    seed_database()
