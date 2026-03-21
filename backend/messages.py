from html import escape as _esc

TEMPLATES: dict[str, dict[str, str]] = {
    "start_welcome": {
        "he": "ברוך הבא! 🚨\nנרשמת לקבלת התראות פיקוד העורף.\nהשתמש ב-/help לרשימת פקודות.",
        "en": "Welcome! 🚨\nYou are now subscribed to Pikud HaOref alerts.\nUse /help for commands.",
    },
    "stop_confirmation": {
        "he": "בוטל המנוי. לא תקבל יותר התראות.\nלהרשמה מחדש: /start",
        "en": "Unsubscribed. You will no longer receive alerts.\nTo resubscribe: /start",
    },
    "filter_added": {
        "he": "סינון נוסף: {area}",
        "en": "Filter added: {area}",
    },
    "filter_not_found": {
        "he": "האזור '{area}' לא נמצא. השתמש ב-/areas לרשימה מלאה.",
        "en": "Area '{area}' not found. Use /areas for the full list.",
    },
    "filter_already_exists": {
        "he": "האזור '{area}' כבר נמצא בסינונים שלך.",
        "en": "Area '{area}' is already in your filters.",
    },
    "filter_limit_reached": {
        "he": "הגעת למגבלת 10 סינונים. השתמש ב-/clearfilters כדי לנקות.",
        "en": "You have reached the 10-filter limit. Use /clearfilters to reset.",
    },
    "filters_cleared": {
        "he": "כל הסינונים הוסרו. תקבל עכשיו את כל ההתראות.",
        "en": "All filters cleared. You will now receive all alerts.",
    },
    "no_filters": {
        "he": "אין לך סינונים פעילים — מקבל את כל ההתראות.",
        "en": "No active filters — you receive all alerts.",
    },
    "status_active": {
        "he": "מנוי פעיל ✅\nשפה: {language}\nסינונים: {filters}",
        "en": "Subscription active ✅\nLanguage: {language}\nFilters: {filters}",
    },
    "language_set": {
        "he": "שפה שונתה לעברית.",
        "en": "Language set to English.",
    },
    "language_invalid": {
        "he": "שפה לא חוקית. השתמש ב-/language he או /language en",
        "en": "Invalid language. Use /language he or /language en",
    },
    "help": {
        "he": (
            "/start — הרשמה להתראות\n"
            "/stop — ביטול מנוי\n"
            "/filter <אזור> — הוסף סינון אזור\n"
            "/filters — רשימת הסינונים שלך\n"
            "/clearfilters — נקה סינונים\n"
            "/areas — רשימת אזורים תקינים\n"
            "/status — סטטוס מנוי\n"
            "/language he|en — שנה שפה\n"
            "/app — פתח את האפליקציה"
        ),
        "en": (
            "/start — Subscribe to alerts\n"
            "/stop — Unsubscribe\n"
            "/filter <area> — Add area filter\n"
            "/filters — Your current filters\n"
            "/clearfilters — Clear all filters\n"
            "/areas — List valid areas\n"
            "/status — Subscription status\n"
            "/language he|en — Change language\n"
            "/app — Open the Mini App"
        ),
    },
}


def render(key: str, language: str, **kwargs) -> str:
    template = TEMPLATES[key][language]  # raises KeyError if missing
    return template.format(**kwargs) if kwargs else template


def render_alert(
    language: str,
    title: str,
    areas: list[str],
    time_str: str,
) -> str:
    areas_str = ", ".join(areas)
    if language == "he":
        return (
            f"🚨 <b>{_esc(title)}</b>\n\n"
            f"📍 <b>אזורים:</b> {_esc(areas_str)}\n"
            f"🕐 <b>שעה:</b> {time_str}\n\n"
            f"היכנסו למרחב המוגן מיד!"
        )
    return (
        f"🚨 <b>Rocket &amp; Missile Fire</b>\n\n"
        f"📍 <b>Areas:</b> {_esc(areas_str)}\n"
        f"🕐 <b>Time:</b> {time_str}\n\n"
        f"Enter a protected space immediately!"
    )
