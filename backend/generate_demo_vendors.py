"""Generate realistic *demo* wedding vendors via Gemini and load them into the DB.

Purpose: give the matcher a real pool to choose from so it stops suggesting the same
1–2 vendors. Generated rows are tagged `source="demo_generated"` and carry NO contact
info — so they're clearly distinguishable from founder-verified real vendors and are
never presented to judges as real businesses. Use for couple-facing demos / breadth.

Usage (from backend/, venv active, valid GEMINI_API_KEY in .env):
    python generate_demo_vendors.py

Idempotent: skips any vendor whose name already exists. Tune the counts/regions below.
"""
import asyncio
import logging
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from google.genai import types
from app.db.session import sync_engine
from app.db.models import Venue, Supplier
from app.agents.base import get_client, FAST_MODEL

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("gen_vendors")

# --- Tune here ---
REGIONS = ["Dublin", "Cork", "Galway", "Kildare", "Meath", "Wicklow", "Limerick", "Clare"]
SUPPLIER_CATEGORIES = [
    "photography", "videography", "florals", "music", "dj",
    "catering", "cake", "hair_makeup", "transport", "stationery", "officiant",
]
VENUES_PER_REGION = 5
SUPPLIERS_PER_CATEGORY = 6  # spread across the regions above


class GenVenue(BaseModel):
    name: str = Field(description="Fictional but plausible Irish wedding venue name (no real business).")
    venue_type: str = Field(description="hotel | country house | barn | castle | marquee | golf club | hall")
    capacity_min: int
    capacity_max: int
    price_from: int = Field(description="Hire price from, EUR")
    price_to: int = Field(description="Hire price to, EUR")
    style: str = Field(description="Short style tags, e.g. 'coastal, relaxed' or 'classic country estate'.")

class GenVenues(BaseModel):
    venues: list[GenVenue]


class GenSupplier(BaseModel):
    name: str = Field(description="Fictional but plausible Irish supplier name (no real business).")
    location: str = Field(description="An Irish town/county from the requested regions.")
    price_from: int = Field(description="Price from, EUR")
    price_to: int = Field(description="Price to, EUR")
    style: str = Field(description="Short style tags.")

class GenSuppliers(BaseModel):
    suppliers: list[GenSupplier]


VENUE_SYS = (
    "You generate realistic but FICTIONAL Irish wedding venues for a product demo. Use plausible "
    "names (not real businesses), realistic capacities, and realistic EUR hire prices for the Irish "
    "market. Vary venue_type and style across the list. Never include real business names, phone "
    "numbers, emails, or addresses. Return valid JSON for the schema."
)
SUPPLIER_SYS = (
    "You generate realistic but FICTIONAL Irish wedding suppliers for a product demo. Use plausible "
    "names (not real businesses), realistic EUR prices for the Irish market, and spread them across "
    "the requested regions. Vary style. Never include real business names or any contact details. "
    "Return valid JSON for the schema."
)


async def _generate(client, schema, prompt, system):
    for attempt in range(4):
        try:
            r = await client.aio.models.generate_content(
                model=FAST_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0.9,
                ),
            )
            return schema.model_validate_json(r.text)
        except Exception as e:
            if any(t in str(e) for t in ("503", "UNAVAILABLE", "429")) and attempt < 3:
                log.info("  transient (%s/4); retrying in 6s…", attempt + 1)
                await asyncio.sleep(6)
                continue
            raise


async def main():
    client = get_client()
    with Session(sync_engine) as session:
        existing_v = {v.name.strip().lower() for v in session.exec(select(Venue)).all()}
        existing_s = {s.name.strip().lower() for s in session.exec(select(Supplier)).all()}
        v_added = s_added = 0

        for region in REGIONS:
            try:
                res = await _generate(
                    client, GenVenues,
                    f"Generate {VENUES_PER_REGION} distinct wedding venues located in {region}, Ireland.",
                    VENUE_SYS,
                )
            except Exception as e:
                log.error("  venues %s failed: %s", region, e)
                continue
            for v in res.venues:
                if v.name.strip().lower() in existing_v:
                    continue
                session.add(Venue(
                    name=v.name.strip(), region=region, address=region,
                    venue_type=v.venue_type, capacity_min=v.capacity_min, capacity_max=v.capacity_max,
                    indoor_outdoor=1, on_site_accommodation=0,
                    pricing_summary={"price_from": v.price_from, "price_to": v.price_to,
                                     "currency": "EUR", "style": v.style},
                    source="demo_generated",
                ))
                existing_v.add(v.name.strip().lower())
                v_added += 1
            session.commit()
            log.info("  venues %s done (+%d total new)", region, v_added)

        for cat in SUPPLIER_CATEGORIES:
            try:
                res = await _generate(
                    client, GenSuppliers,
                    f"Generate {SUPPLIERS_PER_CATEGORY} '{cat}' wedding suppliers spread across these "
                    f"Irish regions: {', '.join(REGIONS)}.",
                    SUPPLIER_SYS,
                )
            except Exception as e:
                log.error("  suppliers %s failed: %s", cat, e)
                continue
            for s in res.suppliers:
                if s.name.strip().lower() in existing_s:
                    continue
                session.add(Supplier(
                    name=s.name.strip(), category=cat, location=s.location,
                    pricing_summary={"price_from": s.price_from, "price_to": s.price_to, "currency": "EUR"},
                    attributes={"style": s.style},
                    source="demo_generated",
                ))
                existing_s.add(s.name.strip().lower())
                s_added += 1
            session.commit()
            log.info("  suppliers %s done (+%d total new)", cat, s_added)

        print(f"\nDONE: +{v_added} venues, +{s_added} suppliers (source=demo_generated)")


if __name__ == "__main__":
    asyncio.run(main())
