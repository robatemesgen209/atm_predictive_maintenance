import re

# Official canonical district names for the ATM maintenance system
CANONICAL_DISTRICTS = [
    "Adama",
    "Dire Dawa",
    "Chiro",
    "Jimma",
    "West Finfine",
    "East Finfine",
    "North Finfine",
    "South Finfine",
    "Nekemte",
    "Mekele",
    "Shashemene",
    "Hawassa",
    "Hosana",
]

# Map inconsistent district names to canonical names
DISTRICT_ALIASES = {
    "adama": "Adama",

    "diredawa": "Dire Dawa",
    "dire dawa": "Dire Dawa",

    "chiro": "Chiro",

    "jima": "Jimma",
    "jimma": "Jimma",

    "wfd": "West Finfine",
    "west fin": "West Finfine",
    "west finfine": "West Finfine",
    "west finfinne": "West Finfine",

    "efd": "East Finfine",
    "east fin": "East Finfine",
    "east finfine": "East Finfine",
    "east finfinne": "East Finfine",

    "nfd": "North Finfine",
    "north fin": "North Finfine",
    "north finfine": "North Finfine",
    "north finfinne": "North Finfine",

    "sfd": "South Finfine",
    "south fin": "South Finfine",
    "south finfine": "South Finfine",
    "south finfinne": "South Finfine",

    "nekemte": "Nekemte",

    "mekele": "Mekele",
    "mekelle": "Mekele",

    "shashemene": "Shashemene",

    "hawasa": "Hawassa",
    "hawassa": "Hawassa",

    "hosana": "Hosana",
    "hossana": "Hosana",
    "hosaena": "Hosana",
}


def normalize_district(district):
    """Convert inconsistent district names to canonical names."""

    if district is None:
        return None

    if not isinstance(district, str):
        return district

    cleaned = re.sub(r"\s+", " ", district.strip()).lower()

    if not cleaned:
        return None

    return DISTRICT_ALIASES.get(cleaned, district.strip())


def get_canonical_districts():
    """Return the list of official district names."""
    return CANONICAL_DISTRICTS.copy()


def is_valid_district(district):
    """Check whether a district maps to one of the canonical districts."""
    normalized = normalize_district(district)
    return normalized in CANONICAL_DISTRICTS