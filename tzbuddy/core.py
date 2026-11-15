"""Zone lookup, time parsing and meeting-slot search on top of zoneinfo."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo, available_timezones

# Common names people actually type that are not IANA city names.
ALIASES = {
    "utc": "UTC", "gmt": "UTC", "z": "UTC",
    "beijing": "Asia/Shanghai", "china": "Asia/Shanghai", "cst-cn": "Asia/Shanghai", "peking": "Asia/Shanghai",
    "hongkong": "Asia/Hong_Kong", "hk": "Asia/Hong_Kong", "taipei": "Asia/Taipei", "seoul": "Asia/Seoul",
    "korea": "Asia/Seoul", "chuncheon": "Asia/Seoul", "japan": "Asia/Tokyo", "osaka": "Asia/Tokyo",
    "india": "Asia/Kolkata", "mumbai": "Asia/Kolkata", "delhi": "Asia/Kolkata", "bangalore": "Asia/Kolkata",
    "sf": "America/Los_Angeles", "san francisco": "America/Los_Angeles", "seattle": "America/Los_Angeles",
    "la": "America/Los_Angeles", "pst": "America/Los_Angeles", "pdt": "America/Los_Angeles",
    "nyc": "America/New_York", "new york": "America/New_York", "boston": "America/New_York",
    "est": "America/New_York", "edt": "America/New_York", "dc": "America/New_York",
    "chicago": "America/Chicago", "cst": "America/Chicago", "austin": "America/Chicago",
    "denver": "America/Denver", "mst": "America/Denver",
    "london": "Europe/London", "uk": "Europe/London", "bst": "Europe/London",
    "cet": "Europe/Paris", "cest": "Europe/Paris", "germany": "Europe/Berlin", "munich": "Europe/Berlin",
    "frankfurt": "Europe/Berlin", "sydney": "Australia/Sydney", "melbourne": "Australia/Melbourne",
    "aest": "Australia/Sydney", "dubai": "Asia/Dubai", "moscow": "Europe/Moscow", "sg": "Asia/Singapore",
}


@lru_cache(maxsize=1)
def _by_city() -> dict:
    out = {}
    for name in available_timezones():
        city = name.rsplit("/", 1)[-1].replace("_", " ").lower()
        # Prefer canonical-looking zones (no Etc/, US/ etc.) when two share a city name.
        if city not in out or "/" in name and not name.startswith(("Etc/", "US/", "SystemV/")):
            out.setdefault(city, name)
    return out


@lru_cache(maxsize=1)
def _canonical() -> dict:
    return {z.lower(): z for z in available_timezones()}


_OFFSET = re.compile(r"^(?:utc|gmt)?\s*([+-])(\d{1,2})(?::?(\d{2}))?$", re.I)


def resolve(name: str):
    """Return (label, tzinfo) for an IANA name, a city, a common alias, or an offset like +05:30."""
    raw = name.strip()
    key = raw.lower()
    if key in ("local", "here"):
        tz = datetime.now().astimezone().tzinfo
        return "local", tz
    m = _OFFSET.match(raw)
    if m and key not in ALIASES:
        sign, h, mm = m.group(1), int(m.group(2)), int(m.group(3) or 0)
        if h > 14 or mm >= 60:
            raise ValueError(f"bad offset: {name}")
        delta = timedelta(hours=h, minutes=mm) * (1 if sign == "+" else -1)
        return f"UTC{sign}{h:02d}:{mm:02d}", timezone(delta)
    target = ALIASES.get(key) or _by_city().get(key.replace("_", " "))
    if target is None:
        target = _canonical().get(key)  # case-insensitive IANA match, canonical spelling
    if target is None:
        close = suggest(raw)
        hint = f" (did you mean {', '.join(close)}?)" if close else ""
        raise ValueError(f"unknown time zone: {name}{hint}")
    label = raw if "/" not in raw and raw.lower() not in ("utc", "gmt") else target.rsplit("/", 1)[-1].replace("_", " ")
    return label, ZoneInfo(target)


def suggest(name: str, n: int = 3) -> list:
    import difflib
    pool = list(_by_city()) + list(ALIASES)
    return difflib.get_close_matches(name.lower(), pool, n=n, cutoff=0.7)


_TIME = re.compile(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", re.I)


def parse_when(text: str | None, tz, today: date | None = None) -> datetime:
    """Parse 'now', '15:30', '3pm', '2026-03-01 09:00', 'tomorrow 9am' in zone tz."""
    now = datetime.now(tz)
    if not text or text.strip().lower() == "now":
        return now.replace(microsecond=0)
    s = text.strip().lower()
    base = today or now.date()
    for word, days in (("today", 0), ("tomorrow", 1), ("yesterday", -1)):
        if s.startswith(word):
            base = base + timedelta(days=days)
            s = s[len(word):].strip() or "00:00"
    m = re.match(r"^(\d{4}-\d{2}-\d{2})(?:[ t](.+))?$", s)
    if m:
        base = date.fromisoformat(m.group(1))
        s = (m.group(2) or "00:00").strip()
    m = _TIME.match(s)
    if not m:
        raise ValueError(f"cannot understand time: {text}")
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ap:
        if not 1 <= h <= 12:
            raise ValueError(f"bad 12-hour time: {text}")
        h = h % 12 + (12 if ap == "pm" else 0)
    if h > 23 or mi > 59:
        raise ValueError(f"bad time: {text}")
    return datetime(base.year, base.month, base.day, h, mi, tzinfo=tz)


def offset_str(dt: datetime) -> str:
    off = dt.utcoffset() or timedelta(0)
    sign = "+" if off >= timedelta(0) else "-"
    mins = abs(int(off.total_seconds())) // 60
    return f"UTC{sign}{mins // 60:02d}:{mins % 60:02d}"


def day_shift(dt: datetime, ref: datetime) -> str:
    d = (dt.date() - ref.date()).days
    return "" if d == 0 else f"{d:+d}d"


def meeting_slots(zones: list, day: date, start: int = 9, end: int = 18, step: int = 30,
                  duration: int = 60, ref_tz=None) -> list:
    """Start times (in ref_tz, default first zone) where everyone is within [start, end) local hours
    for the whole meeting. Returns a list of aware datetimes."""
    ref_tz = ref_tz or zones[0]
    t = datetime(day.year, day.month, day.day, tzinfo=ref_tz)
    stop = t + timedelta(days=1)
    dur = timedelta(minutes=duration)
    out = []
    while t < stop:
        ok = True
        for z in zones:
            a = t.astimezone(z)
            b = (t + dur).astimezone(z)
            mins_a = a.hour * 60 + a.minute
            mins_b = b.hour * 60 + b.minute
            if a.date() != b.date() and mins_b != 0:
                ok = False
                break
            if mins_b == 0 and a.date() != b.date():
                mins_b = 24 * 60
            if mins_a < start * 60 or mins_b > end * 60:
                ok = False
                break
        if ok:
            out.append(t)
        t += timedelta(minutes=step)
    return out


def best_compromise(zones: list, day: date, start: int = 9, end: int = 18, ref_tz=None) -> tuple:
    """When no slot fits, the hour minimizing total minutes outside working hours."""
    ref_tz = ref_tz or zones[0]
    best = None
    for h in range(24):
        t = datetime(day.year, day.month, day.day, h, tzinfo=ref_tz)
        pain = 0
        for z in zones:
            lh = t.astimezone(z).hour
            pain += max(0, start - lh, lh + 1 - end) if not (start <= lh < end) else 0
        if best is None or pain < best[1]:
            best = (t, pain)
    return best
