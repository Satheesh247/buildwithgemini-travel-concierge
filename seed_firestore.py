"""Seed script for Travel Concierge Firestore collection."""

import google.auth
from google.cloud import firestore

# Hardcoded project ID as required to prevent Agent Platform project number issues
PROJECT_ID = "qwiklabs-gcp-02-2112d6d9642e"

DESTINATIONS = [
    {
        "destination_id": "kyoto-japan",
        "name": "Kyoto, Japan",
        "category": "Culture & History",
        "description": "Ancient temples, traditional tea houses, and stunning cherry blossoms.",
        "best_season": "Spring",
        "avg_daily_cost_usd": 180,
        "popular_activities": [
            "Visit Fushimi Inari Shrine",
            "Explore Arashiyama Bamboo Grove",
            "Tea Ceremony in Gion",
        ],
    },
    {
        "destination_id": "amalfi-coast-italy",
        "name": "Amalfi Coast, Italy",
        "category": "Coastal & Luxury",
        "description": "Dramatic cliffside villages, turquoise waters, and Mediterranean cuisine.",
        "best_season": "Summer",
        "avg_daily_cost_usd": 250,
        "popular_activities": [
            "Hike Path of the Gods",
            "Boat tour to Capri",
            "Limoncello tasting in Positano",
        ],
    },
    {
        "destination_id": "banff-canada",
        "name": "Banff National Park, Canada",
        "category": "Nature & Adventure",
        "description": "Glacial turquoise lakes, majestic Rocky Mountain peaks, and abundant wildlife.",
        "best_season": "Summer / Winter",
        "avg_daily_cost_usd": 200,
        "popular_activities": [
            "Canoe on Lake Louise",
            "Hike Johnston Canyon",
            "Relax in Banff Upper Hot Springs",
        ],
    },
    {
        "destination_id": "reykjavik-iceland",
        "name": "Reykjavik & Golden Circle, Iceland",
        "category": "Adventure & Wonders",
        "description": "Northern Lights, geothermal springs, volcanic landscapes, and thundering waterfalls.",
        "best_season": "Winter / Summer",
        "avg_daily_cost_usd": 220,
        "popular_activities": [
            "Bathe in Blue Lagoon",
            "Golden Circle tour",
            "Northern Lights hunt",
        ],
    },
]


def seed_database():
    credentials, _ = google.auth.default()
    db = firestore.Client(project=PROJECT_ID, credentials=credentials)
    print(f"Connecting to Firestore for project: {PROJECT_ID}")
    collection_ref = db.collection("destinations")

    for dest in DESTINATIONS:
        doc_id = dest["destination_id"]
        collection_ref.document(doc_id).set(dest)
        print(f"Seeded destination: {dest['name']} ({doc_id})")

    print("Firestore seeding complete!")


if __name__ == "__main__":
    seed_database()
