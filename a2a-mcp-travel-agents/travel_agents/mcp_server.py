"""MCP server exposing the travel tools, built with the official `mcp` SDK (FastMCP).

Run standalone over stdio (e.g. for Claude Desktop, Cursor or the MCP Inspector):

    python -m travel_agents.mcp_server
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import data

mcp = FastMCP("travel-tools")


@mcp.tool()
def search_flights(origin: str, destination: str, date: str, travelers: int = 1) -> dict:
    """Search one-way flights between two cities on an ISO date (YYYY-MM-DD), cheapest first."""
    options = data.flights(origin, destination, date)
    for f in options:
        f["total_usd"] = f["price_usd"] * travelers
    return {"origin": origin, "destination": destination, "date": date, "travelers": travelers, "options": options}


@mcp.tool()
def search_hotels(city: str, nights: int = 1, guests: int = 1, max_price_per_night: float | None = None) -> dict:
    """Search hotels in a city, best rated first, optionally under a nightly price cap (USD)."""
    options = [h for h in data.hotels(city) if max_price_per_night is None or h["price_per_night_usd"] <= max_price_per_night]
    rooms = max(1, (guests + 1) // 2)
    for h in options:
        h["total_usd"] = h["price_per_night_usd"] * nights * rooms
    options.sort(key=lambda h: (-h["rating"], h["price_per_night_usd"]))
    return {"city": city, "nights": nights, "guests": guests, "rooms": rooms, "options": options}


@mcp.tool()
def create_booking(traveler_name: str, flight_id: str, hotel_id: str, nights: int, travelers: int = 1) -> dict:
    """Book a flight and hotel together. Returns a booking confirmation."""
    flight, hotel = data.find_flight(flight_id), data.find_hotel(hotel_id)
    if not flight:
        return {"ok": False, "error": f"unknown flight {flight_id}"}
    if not hotel:
        return {"ok": False, "error": f"unknown hotel {hotel_id}"}
    rooms = max(1, (travelers + 1) // 2)
    total = flight["price_usd"] * travelers + hotel["price_per_night_usd"] * nights * rooms
    booking = {
        "ok": True, "booking_id": data.new_booking_id(), "traveler_name": traveler_name, "travelers": travelers,
        "flight": flight, "hotel": hotel, "nights": nights, "rooms": rooms, "total_usd": total, "status": "confirmed",
    }
    data.BOOKINGS[booking["booking_id"]] = booking
    return booking


@mcp.tool()
def get_booking(booking_id: str) -> dict:
    """Look up a booking by id."""
    return data.BOOKINGS.get(booking_id) or {"ok": False, "error": f"unknown booking {booking_id}"}


if __name__ == "__main__":
    mcp.run()  # stdio transport
