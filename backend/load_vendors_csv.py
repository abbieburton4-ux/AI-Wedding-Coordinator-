"""Bulk-load wedding venues + suppliers from CSV into the database.

Lets a non-coder (e.g. Alan) crowd-source real vendors from public directories
(One Fab Day, WeddingsOnline.ie, Bridebook, Google Maps) into a spreadsheet, then
import them with one command. Idempotent: existing vendors (matched by name +
region/location) are skipped, so re-running after adding rows only inserts the new ones.

Usage (from backend/, venv active):
    python load_vendors_csv.py

Edit the templates first:
    backend/data/venues.csv
    backend/data/suppliers.csv
"""
import csv
import os
import logging
from sqlmodel import Session, select
from app.db.session import sync_engine
from app.db.models import Venue, Supplier

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("load_vendors")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _int(v, default=None):
    v = (v or "").strip()
    return int(float(v)) if v else default


def _pricing(row) -> dict:
    ps = {"currency": "EUR"}
    if (row.get("price_from") or "").strip():
        ps["price_from"] = _int(row.get("price_from"))
    if (row.get("price_to") or "").strip():
        ps["price_to"] = _int(row.get("price_to"))
    if (row.get("style") or "").strip():
        ps["style"] = row["style"].strip()
    return ps


def load_venues(session: Session, path: str) -> tuple[int, int]:
    if not os.path.exists(path):
        log.warning("No venues CSV at %s — skipping.", path)
        return (0, 0)
    existing = {(v.name.strip().lower(), (v.region or "").strip().lower())
                for v in session.exec(select(Venue)).all()}
    added = skipped = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = (row.get("name") or "").strip()
            region = (row.get("region") or "").strip()
            if not name or not region:
                continue
            key = (name.lower(), region.lower())
            if key in existing:
                skipped += 1
                continue
            session.add(Venue(
                name=name,
                region=region,
                address=(row.get("address") or "").strip() or region,
                venue_type=(row.get("venue_type") or "venue").strip(),
                capacity_min=_int(row.get("capacity_min")),
                capacity_max=_int(row.get("capacity_max")),
                indoor_outdoor=_int(row.get("indoor_outdoor"), 1),
                on_site_accommodation=_int(row.get("on_site_accommodation"), 0),
                pricing_summary=_pricing(row),
                eircode=(row.get("eircode") or "").strip() or None,
                source=(row.get("source") or "csv_import").strip(),
            ))
            existing.add(key)
            added += 1
    return (added, skipped)


def load_suppliers(session: Session, path: str) -> tuple[int, int]:
    if not os.path.exists(path):
        log.warning("No suppliers CSV at %s — skipping.", path)
        return (0, 0)
    existing = {(s.name.strip().lower(), (s.location or "").strip().lower())
                for s in session.exec(select(Supplier)).all()}
    added = skipped = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = (row.get("name") or "").strip()
            category = (row.get("category") or "").strip()
            location = (row.get("location") or "").strip()
            if not name or not category or not location:
                continue
            key = (name.lower(), location.lower())
            if key in existing:
                skipped += 1
                continue
            ps = _pricing(row)
            style = ps.pop("style", None)
            session.add(Supplier(
                name=name,
                category=category,
                location=location,
                pricing_summary=ps,
                attributes={"style": style} if style else {},
                source=(row.get("source") or "csv_import").strip(),
            ))
            existing.add(key)
            added += 1
    return (added, skipped)


def main():
    with Session(sync_engine) as session:
        va, vs = load_venues(session, os.path.join(DATA_DIR, "venues.csv"))
        sa, ss = load_suppliers(session, os.path.join(DATA_DIR, "suppliers.csv"))
        session.commit()
    print(f"Venues:    +{va} added, {vs} skipped (already present)")
    print(f"Suppliers: +{sa} added, {ss} skipped (already present)")


if __name__ == "__main__":
    main()
