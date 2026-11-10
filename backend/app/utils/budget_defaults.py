"""The suggested budget categories and their one-tap expense ideas (PD-013 call b).

The ten categories are the nine groups from the owner's brief plus Contingency (the
brief's "Emergency expenses"). The couple add them with one click; nothing adds them
automatically, and none comes with a target amount. Each category's items are
suggestions shown while adding an expense, never rows of their own. This lives in
code, not the database, so changing a suggestion needs no migration.
"""
from typing import Dict, List, Optional, Tuple

from app.agents.budget_split import category_key
from app.utils.budget_math import CONTINGENCY_NAME

DEFAULT_CATEGORIES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("Venue & Catering", (
        "Ceremony venue", "Reception venue", "Catering", "Bar and beverages",
        "Wedding cake and desserts", "Rentals", "Tables, chairs and linens")),
    ("Photography & Entertainment", (
        "Photographer", "Videographer", "Photo booth", "DJ", "Live music",
        "Ceremony musicians")),
    ("Attire & Beauty", (
        "Wedding dress", "Suit/tuxedo", "Alterations", "Accessories", "Hair", "Makeup",
        "Bridal party attire")),
    ("Flowers & Decor", (
        "Bridal bouquet", "Bridesmaid bouquets", "Boutonnieres", "Ceremony flowers",
        "Reception centerpieces", "Decorations", "Lighting")),
    ("Planning & Stationery", (
        "Wedding planner", "Day-of coordinator", "Invitations", "Save-the-dates", "Programs",
        "Signage", "Postage")),
    ("Transportation & Accommodation", (
        "Transportation", "Hotel accommodations", "Guest transportation", "Parking")),
    # The Jewish-ceremony items were added to the brief's list by PD-013 call b.
    ("Ceremony & Legal", (
        "Officiant", "Marriage license", "Ceremony fees", "Rehearsal", "Ketubah", "Chuppah",
        "Rabbi's fee")),
    ("Additional Events", (
        "Engagement party", "Bridal shower", "Bachelorette party", "Bachelor party",
        "Rehearsal dinner", "Welcome party", "Farewell brunch")),
    ("Other", ("Wedding favors", "Gifts", "Tips and gratuities", "Miscellaneous")),
    # The dashboard finds the contingency by this exact name (budget_math).
    (CONTINGENCY_NAME, ()),
)

DEFAULT_NAMES: Tuple[str, ...] = tuple(name for name, _ in DEFAULT_CATEGORIES)

# Names the couple (or migration 0009, for Wildman BT) may already use for the venue
# category: a category with one of these counts as having Venue & Catering, so the
# venue's expenses are never split across two look-alike categories.
_ALIASES = {"venue": "venue and catering", "venues": "venue and catering"}


def default_key(name: Optional[str]) -> str:
    """category_key, with "&" read as "and": "Flowers & Decor" is "flowers and decor"."""
    key = " ".join(category_key(name).replace("&", " and ").split())
    return _ALIASES.get(key, key)


_SUGGESTIONS: Dict[str, Tuple[str, ...]] = {
    default_key(name): items for name, items in DEFAULT_CATEGORIES}


def suggestions_for(category_name: str) -> List[str]:
    """The one-tap expense ideas for a category, or none if it isn't a suggested one."""
    return list(_SUGGESTIONS.get(default_key(category_name), ()))


def missing_defaults(existing_names) -> List[str]:
    """The suggested categories the couple don't have yet, in the suggested order."""
    have = {default_key(n) for n in existing_names}
    return [name for name in DEFAULT_NAMES if default_key(name) not in have]
