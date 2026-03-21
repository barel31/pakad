# Full list sourced from https://www.oref.org.il
AREAS: list[str] = [
    "תל אביב - מרכז העיר",
    "תל אביב - דרום העיר",
    "תל אביב - צפון העיר",
    "רמת גן - כפר אז\"ר",
    "רמת גן - מרכז העיר",
    "גבעתיים",
    "חולון",
    "בת ים",
    "ירושלים",
    "חיפה",
    "באר שבע",
    "אשדוד",
    "אשקלון",
    "נתניה",
    "פתח תקווה",
    "ראשון לציון",
    "רחובות",
    "הרצליה",
    "כפר סבא",
    "מודיעין",
    "לוד",
    "רמלה",
    "עכו",
    "נהריה",
    "עפולה",
    "טבריה",
    "צפת",
    "קריית שמונה",
    "שדרות",
    "ספיר",
]

def normalize_area_input(text: str) -> str | None:
    """Return matching area name from AREAS or None if not found (case-insensitive strip)."""
    text = text.strip()
    for area in AREAS:
        if area.strip().lower() == text.lower():
            return area
    return None
