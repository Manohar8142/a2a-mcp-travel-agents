"""Deterministic mock travel inventory (no external APIs)."""
from __future__ import annotations

import hashlib
import itertools

CITIES = {
    "hyderabad": "HYD", "goa": "GOI", "bengaluru": "BLR", "bangalore": "BLR",
    "delhi": "DEL", "mumbai": "BOM", "chennai": "MAA", "kochi": "COK",
}
AIRLINES = [("IndiGo", "6E"), ("Air India", "AI"), ("Akasa Air", "QP")]
DEPARTURES = ["06:10", "11:45", "19:30"]

HOTELS = {
    "GOI": [("Sea Breeze Resort", 4.5, 92), ("Panjim Heritage Inn", 4.1, 48), ("Baga Beach Hostel", 3.8, 18), ("Candolim Grand", 4.7, 165)],
    "BLR": [("Indiranagar Suites", 4.3, 70), ("Garden City Hotel", 4.0, 45), ("MG Road Residency", 4.6, 120)],
    "DEL": [("Connaught Place Hotel", 4.2, 85), ("Aerocity Stay", 4.4, 110), ("Paharganj Lodge", 3.6, 22)],
    "BOM": [("Marine Drive Towers", 4.6, 150), ("Bandra Boutique", 4.3, 95), ("Andheri Transit Inn", 3.9, 40)],
    "HYD": [("HITEC City Suites", 4.4, 75), ("Charminar View Hotel", 4.0, 40), ("Banjara Hills Palace", 4.7, 140)],
    "MAA": [("Marina Bay Hotel", 4.2, 65), ("T Nagar Comforts", 3.9, 35)],
    "COK": [("Fort Kochi Homestay", 4.5, 50), ("Marine Drive Kochi", 4.1, 80)],
}

BOOKINGS: dict[str, dict] = {}
_booking_ids = itertools.count(5001)


def city_code(city: str) -> str | None:
    city = city.strip().lower()
    if city.upper() in CITIES.values():
        return city.upper()
    return CITIES.get(city)


def _price(*parts: str, low: int, high: int) -> int:
    h = int(hashlib.sha256("|".join(parts).encode()).hexdigest(), 16)
    return low + h % (high - low)


def flights(origin: str, destination: str, date: str) -> list[dict]:
    o, d = city_code(origin), city_code(destination)
    if not o or not d or o == d:
        return []
    out = []
    for (airline, code), dep in zip(AIRLINES, DEPARTURES):
        out.append({
            "flight_id": f"{code}{_price(o, d, airline, low=100, high=999)}-{date}",
            "airline": airline, "origin": o, "destination": d, "date": date, "departure": dep,
            "duration_min": _price(o, d, low=70, high=170), "price_usd": _price(o, d, date, airline, low=45, high=180),
        })
    return sorted(out, key=lambda f: f["price_usd"])


def hotels(city: str) -> list[dict]:
    code = city_code(city)
    return [
        {"hotel_id": f"{code}-H{i + 1}", "name": n, "city": code, "rating": r, "price_per_night_usd": p}
        for i, (n, r, p) in enumerate(HOTELS.get(code or "", []))
    ]


def find_flight(flight_id: str) -> dict | None:
    code, _, date = flight_id.partition("-")
    for o in set(CITIES.values()):
        for d in set(CITIES.values()):
            for f in flights(o, d, date):
                if f["flight_id"] == flight_id:
                    return f
    return None


def find_hotel(hotel_id: str) -> dict | None:
    code = hotel_id.split("-")[0]
    return next((h for h in hotels(code) if h["hotel_id"] == hotel_id), None)


def new_booking_id() -> str:
    return f"TRV{next(_booking_ids)}"
