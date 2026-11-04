import re

ALLOWED_BUDGET_CATEGORIES = {
    "venue", "catering", "florals", "photography", "videography", "music",
    "dj", "officiant", "stationery", "hair_makeup", "transport", "cake", "other",
}

# Supplier-facing subset. Excludes 'venue' (matched separately by venue_matcher)
# and 'other' (catch-all budget bucket with no sourcing flow).
SUPPLIER_CATEGORIES = tuple(sorted(ALLOWED_BUDGET_CATEGORIES - {"venue", "other"}))


def normalize_category(raw):
    """Lowercase + strip a category label so 'Venue', ' venue ', 'VENUE' all
    match the lowercase whitelist. Returns '' for None/missing."""
    return (raw or "").strip().lower()


# Irish administrative geography. Map of province -> set of constituent counties
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
    """Return the set of region labels that should match a given selection."""
    if region in IRISH_REGION_HIERARCHY:
        return IRISH_REGION_HIERARCHY[region] | {region}
    return {region}


def region_matches(venue_region, preferred_region):
    """True if a venue's region label and a couple's preferred region label
    share any administrative geography."""
    return bool(expand_region(venue_region) & expand_region(preferred_region))


# Irish Eircode: routing key (1 valid letter + 2 digits) + space + 4-char unique
# identifier, e.g. "A98 NP03".
_EIRCODE_RE = re.compile(r"\b([AC-FHKNPRTV-Y]\d{2})\s+([0-9AC-FHKNPRTV-Y]{4})\b", re.IGNORECASE)


def extract_eircode(address):
    """Pull an Eircode out of an address string, normalized to 'A98 NP03' form,
    or None if the address contains no eircode."""
    if not address:
        return None
    m = _EIRCODE_RE.search(address)
    if not m:
        return None
    return f"{m.group(1).upper()} {m.group(2).upper()}"
