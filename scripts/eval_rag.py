"""RAG evaluation script for DarPilot (M3).

Runs a fixed set of 30 questions against the listing index for two chunk
sizes and reports the hit rate:

- Mapping question (expected_id set): hit if the expected listing id is in
  the top-5 search results.
- Refusal question (expected_id None): hit if the answer is refused
  (no relevant chunks above threshold).

Usage:
    PYTHONPATH=C:\DarPilot .venv\Scripts\python.exe scripts/eval_rag.py
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai import rag  # noqa: E402


# ── Controlled listings (insertion order => stable ids 1..12) ──────────────

LISTINGS: List[Dict[str, Any]] = [
    {"id": 1, "title": "Modern Apartment in Maarif",
     "description": "Bright modern 2-bedroom apartment with sea view in Maarif, Casablanca.",
     "price_mad": 1200000, "city": "Casablanca", "neighborhood": "Maarif",
     "property_type": "Apartment", "status": "available"},
    {"id": 2, "title": "Luxury Villa with Pool in Palmeraie",
     "description": "Spacious luxury villa with private pool and garden in Palmeraie, Marrakech.",
     "price_mad": 4500000, "city": "Marrakech", "neighborhood": "Palmeraie",
     "property_type": "Villa", "status": "available"},
    {"id": 3, "title": "Compact Studio in Gueliz",
     "description": "Compact studio apartment in Gueliz district, Marrakech, close to shops and cafes.",
     "price_mad": 700000, "city": "Marrakech", "neighborhood": "Gueliz",
     "property_type": "Studio", "status": "sold"},
    {"id": 4, "title": "Traditional Riad in Medina",
     "description": "Authentic traditional riad with central patio in the Medina of Marrakech.",
     "price_mad": 3000000, "city": "Marrakech", "neighborhood": "Medina",
     "property_type": "Riad", "status": "available"},
    {"id": 5, "title": "Sea-view Apartment in Anfa",
     "description": "Elegant apartment with ocean view in Anfa, Casablanca.",
     "price_mad": 2500000, "city": "Casablanca", "neighborhood": "Anfa",
     "property_type": "Apartment", "status": "available"},
    {"id": 6, "title": "Luxury Villa in Hivernage",
     "description": "High-end villa in Hivernage, Marrakech, near the palace and spa district.",
     "price_mad": 6000000, "city": "Marrakech", "neighborhood": "Hivernage",
     "property_type": "Villa", "status": "available"},
    {"id": 7, "title": "Renovated Apartment in Gauthier",
     "description": "Recently renovated 3-bedroom apartment in Gauthier, Casablanca.",
     "price_mad": 1500000, "city": "Casablanca", "neighborhood": "Gauthier",
     "property_type": "Apartment", "status": "available"},
    {"id": 8, "title": "Modern Studio in Sidi Maarouf",
     "description": "Modern studio near business district in Sidi Maarouf, Casablanca.",
     "price_mad": 900000, "city": "Casablanca", "neighborhood": "Sidi Maarouf",
     "property_type": "Studio", "status": "available"},
    {"id": 9, "title": "Family Villa in Gueliz",
     "description": "Family-sized villa with 4 bedrooms in Gueliz, Marrakech.",
     "price_mad": 3800000, "city": "Marrakech", "neighborhood": "Gueliz",
     "property_type": "Villa", "status": "available"},
    {"id": 10, "title": "Penthouse in Marina",
     "description": "Luxury penthouse with terrace in Casablanca Marina.",
     "price_mad": 5500000, "city": "Casablanca", "neighborhood": "Marina",
     "property_type": "Apartment", "status": "available"},
    {"id": 11, "title": "Riad in Kasbah",
     "description": "Historic riad in the Kasbah district of Marrakech.",
     "price_mad": 2200000, "city": "Marrakech", "neighborhood": "Kasbah",
     "property_type": "Riad", "status": "available"},
    {"id": 12, "title": "Apartment in Agdal",
     "description": "Quiet apartment in Agdal, Rabat.",
     "price_mad": 1800000, "city": "Rabat", "neighborhood": "Agdal",
     "property_type": "Apartment", "status": "available"},
]

# (question, expected_listing_id_or_None, language)
QUESTIONS: List[tuple] = [
    ("villa with pool in Marrakech", 2, "en"),
    ("sea view apartment in Anfa Casablanca", 5, "en"),
    ("compact studio Marrakech", 3, "en"),
    ("traditional riad central patio Medina", 4, "en"),
    ("luxury villa Hivernage Marrakech", 6, "en"),
    ("renovated apartment Gauthier Casablanca", 7, "en"),
    ("modern studio Sidi Maarouf Casablanca business", 8, "en"),
    ("family villa four bedrooms Gueliz Marrakech", 9, "en"),
    ("luxury penthouse terrace Casablanca Marina", 10, "en"),
    ("historic riad Kasbah Marrakech", 11, "en"),
    ("quiet apartment Agdal Rabat", 12, "en"),
    ("modern apartment with sea view Maarif", 1, "en"),
    ("villa with garden and pool Palmeraie", 2, "en"),
    ("studio near shops Gueliz", 3, "en"),
    ("traditional riad with patio", 4, "en"),
    ("ocean view apartment Anfa", 5, "en"),
    ("high end villa near palace Hivernage", 6, "en"),
    ("renovated three bedroom Gauthier", 7, "en"),
    ("penthouse with terrace Marina Casablanca", 10, "en"),
    ("villa avec piscine Palmeraie Marrakech", 2, "fr"),
    ("studio compact Gueliz Marrakech", 3, "fr"),
    ("riad traditionnel patio Medina", 4, "fr"),
    ("appartement vue ocean Anfa Casablanca", 5, "fr"),
    ("villa de luxe Hivernage Marrakech", 6, "fr"),
    ("xqzpl qwer unrelated nonsense", None, "en"),
    ("buy a car in paris", None, "en"),
    ("weather forecast tomorrow", None, "en"),
    ("qwerty uiop asdfgh jklm", None, "en"),
    ("pizza restaurant delivery", None, "en"),
    ("university enrollment Morocco", None, "en"),
    ("flight ticket to london", None, "en"),
    ("smartphone latest model", None, "en"),
    ("hotel booking Agadir", None, "en"),
    ("xyz foo bar baz qux", None, "en"),
]


def _seed_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "backend", "schema.sql"), encoding="utf-8").read())
    for l in LISTINGS:
        conn.execute(
            """INSERT INTO listings
               (title, description, price_mad, city, neighborhood,
                property_type, status, agent_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (l["title"], l["description"], l["price_mad"], l["city"],
             l["neighborhood"], l["property_type"], l["status"], None),
        )
    conn.commit()
    conn.close()


def _evaluate(chunk_size: int, db_path: str) -> Dict[str, Any]:
    rag.build_index(LISTINGS, chunk_size=chunk_size)
    hits = 0
    details = []
    for question, expected_id, lang in QUESTIONS:
        results = rag.search(question, top_k=5, chunk_size=chunk_size)
        top_ids = [r["listing_id"] for r in results]
        refused = len(results) == 0 or all(r["score"] < 0.60 for r in results)

        if expected_id is None:
            hit = refused
        else:
            hit = expected_id in top_ids
        hits += 1 if hit else 0
        details.append({
            "question": question,
            "expected": expected_id,
            "top_ids": top_ids,
            "top_score": round(results[0]["score"], 3) if results else None,
            "refused": refused,
            "hit": hit,
        })

    return {"chunk_size": chunk_size, "questions": len(QUESTIONS),
            "hits": hits, "hit_rate": hits / len(QUESTIONS), "details": details}


def main() -> None:
    os.environ["DARPILOT_DB_PATH"] = tempfile.mkstemp(suffix=".db")[1]
    _seed_db(os.environ["DARPILOT_DB_PATH"])

    results = []
    for chunk_size in (60, 120):
        res = _evaluate(chunk_size, os.environ["DARPILOT_DB_PATH"])
        results.append(res)
        print(f"chunk_size={chunk_size}: {res['hits']}/{res['questions']} "
              f"= {res['hit_rate']*100:.1f}% hit rate")
        for d in res["details"]:
            mark = "OK " if d["hit"] else "FAIL"
            print(f"  [{mark}] {d['question'][:55]:57s} expected={d['expected']} "
                  f"top={d['top_ids']} score={d['top_score']} refused={d['refused']}")

    # Persist question set for the record.
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "eval_questions.json"), "w", encoding="utf-8") as f:
        json.dump([{"question": q, "expected_id": e, "lang": lang}
                   for q, e, lang in QUESTIONS], f, indent=2, ensure_ascii=False)
    print(f"\nWrote {len(QUESTIONS)} questions to data/eval_questions.json")


if __name__ == "__main__":
    main()
