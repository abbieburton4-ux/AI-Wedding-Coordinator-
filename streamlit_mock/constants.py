"""Shared constants for the VenueFlow pilot.

Single source of truth for:
- Budget category whitelist (used by intake_planner guardrail, supplier_matcher
  WHERE category = ?, quote_extractor category derivation, and the UI dropdown).
- Supplier-facing subset (excludes 'venue' and 'other', which have their own flows).
- Irish region hierarchy (province → counties) for matcher pre-filter.
- Eircode extraction (for the Google Maps geocoding field on venues).
"""

import re


ALLOWED_BUDGET_CATEGORIES = {
    "venue", "catering", "florals", "photography", "videography", "music",
    "dj", "officiant", "stationery", "hair_makeup", "transport", "cake", "other",
}

# Supplier-facing subset. Excludes 'venue' (matched separately by venue_matcher)
# and 'other' (catch-all budget bucket with no sourcing flow). Sorted tuple for
# stable iteration in UI dropdowns.
SUPPLIER_CATEGORIES = tuple(sorted(ALLOWED_BUDGET_CATEGORIES - {"venue", "other"}))


def normalize_category(raw):
    """Lowercase + strip a category label so 'Venue', ' venue ', 'VENUE' all
    match the lowercase whitelist. Returns '' for None/missing, which never
    matches ALLOWED_BUDGET_CATEGORIES and gets blocked downstream."""
    return (raw or "").strip().lower()


# Irish administrative geography. Map of province → set of constituent counties
# (Republic of Ireland only). Used by region_matches() to let a couple select
# a province (e.g. "Leinster") and match venues seeded with constituent county
# labels (e.g. Millhouse Slane in "Meath"), or vice versa.
IRISH_REGION_HIERARCHY = {
    "Connacht": frozenset({"Sligo", "Galway", "Mayo", "Leitrim", "Roscommon"}),
    "Leinster": frozenset({
        "Dublin", "Meath", "Offaly", "Kildare", "Wexford", "Wicklow",
        "Westmeath", "Louth", "Carlow", "Laois", "Longford", "Kilkenny",
    }),
    "Munster": frozenset({"Kerry", "Clare", "Cork", "Limerick", "Tipperary", "Waterford"}),
    "Ulster": frozenset({"Monaghan", "Donegal", "Cavan"}),  # ROI counties only
}


def expand_region(region):
    """Return the set of region labels that should match a given selection.

    A county label returns just itself: {"Meath"}.
    A province label returns the province plus all its constituent counties:
        expand_region("Leinster") -> {"Leinster", "Dublin", "Meath", "Offaly", ...}

    The province label itself is included so a venue seeded as "Leinster"
    (rather than a specific county) still matches when the couple picks
    "Leinster"."""
    if region in IRISH_REGION_HIERARCHY:
        return IRISH_REGION_HIERARCHY[region] | {region}
    return {region}


def region_matches(venue_region, preferred_region):
    """True if a venue's region label and a couple's preferred region label
    share any administrative geography. Handles county↔province in both
    directions:

        region_matches("Meath", "Leinster") -> True  (Meath is in Leinster)
        region_matches("Leinster", "Meath") -> True  (same, reversed)
        region_matches("Sligo", "Sligo")    -> True  (exact county)
        region_matches("Sligo", "Leinster") -> False (Sligo is in Connacht)
    """
    return bool(expand_region(venue_region) & expand_region(preferred_region))


# Irish Eircode: routing key (1 valid letter + 2 digits) + space + 4-char unique
# identifier, e.g. "A98 NP03". The routing-key letter set excludes B, G, I, J,
# L, M, O, Q, S, U, Z per the Eircode spec. Northern Irish postcodes (e.g.
# "BT33 0AH") do NOT match — they are not eircodes, so geocoding falls back to
# the full address for NI venues.
_EIRCODE_RE = re.compile(r"\b([AC-FHKNPRTV-Y]\d{2})\s+([0-9AC-FHKNPRTV-Y]{4})\b", re.IGNORECASE)


def extract_eircode(address):
    """Pull an Eircode out of an address string, normalized to 'A98 NP03'
    form, or None if the address contains no eircode. Address remains the
    single source of truth — this is a derived geocoding key, not a second
    place to maintain the postcode."""
    if not address:
        return None
    m = _EIRCODE_RE.search(address)
    if not m:
        return None
    return f"{m.group(1).upper()} {m.group(2).upper()}"
