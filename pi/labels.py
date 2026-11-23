"""Single source of truth for the spearmint thresholds (same rules as the answer key)."""

ALERT_ORDER = ["DRY_DANGER", "TOO_WET", "HEAT_DANGER", "COLD_DANGER", "LOW_LIGHT"]


def moisture_level(m):
    if m > 100: return "too_wet"
    if m >= 90: return "optimal"
    if m > 70: return "acceptable"
    if m > 25: return "dry"
    return "danger_dry"


def temp_level(t):
    if 15 <= t <= 25: return "optimal"
    if 4 <= t <= 36: return "acceptable"
    return "danger"


def light_level(lh):
    if lh >= 285000: return "optimal"
    if lh >= 90000: return "acceptable"
    return "low"


def humidity_level(h):
    return "optimal" if 60 <= h <= 70 else "outside_optimal"


def label(m, t, h, lh):
    """Return the correct answer for one reading."""
    ml = moisture_level(m)
    alerts = []
    if ml == "danger_dry": alerts.append("DRY_DANGER")
    if ml == "too_wet": alerts.append("TOO_WET")
    if t > 36: alerts.append("HEAT_DANGER")
    if t < 4: alerts.append("COLD_DANGER")
    if light_level(lh) == "low": alerts.append("LOW_LIGHT")
    return {
        "moisture_level": ml,
        "temp_level": temp_level(t),
        "light_level": light_level(lh),
        "humidity_level": humidity_level(h),
        "alerts": alerts,
        "water": "yes" if m <= 70 else "no",
    }
