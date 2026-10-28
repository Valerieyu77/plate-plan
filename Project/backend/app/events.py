"""
Campus fitness and wellness events, from the university's public "Recreation, Health & Wellness"
calendar (calendars.illinois.edu, calendar 637), which Campus Recreation and others post to.

The calendar is read as an iCal file and kept in memory for an hour, so a page view doesn't call
the campus server every time. Parsing is done by hand (iCal is simple text), so no new package
is needed. RSO (student club) events live in a system that needs a login, so they are not here.
"""

import re
import time
from datetime import date, datetime, timedelta

import requests

CALENDAR_ID = 637
FEED_URL = f"https://calendars.illinois.edu/icalGmail/{CALENDAR_ID}.ics?hourOffset=0&timeZone=America%2FChicago"
CALENDAR_PAGE = f"https://calendars.illinois.edu/list/{CALENDAR_ID}"
CACHE_SECONDS = 3600

# Words that mark an event as exercise rather than, say, a flu shot clinic
FITNESS_WORDS = [
    "fitness", "workout", "yoga", "pilates", "cycle", "cycling", "spin", "run", "5k", "walk", "swim", "aqua",
    "skate", "climb", "boulder", "dance", "zumba", "hiit", "strength", "lift", "boxing", "kickbox", "martial",
    "intramural", "tournament", "basketball", "volleyball", "soccer", "tennis", "pickleball", "badminton",
    "hike", "bike", "barre", "bootcamp", "core", "stretch", "mobility", "arc", "crce", "skating", "freestyle",
    "ice arena",
]
_FITNESS = re.compile(r"\b(" + "|".join(FITNESS_WORDS) + r")\b", re.I)

_cache: dict = {"at": 0.0, "events": None}


def _unfold(text: str) -> list[str]:
    """iCal wraps long lines: a line starting with a space or tab continues the one before."""
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _unescape(value: str) -> str:
    return value.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\").strip()


def _parse_time(value: str) -> tuple[datetime, bool]:
    """(start, all_day). Times in this feed are local Chicago times without a zone suffix."""
    value = value.rstrip("Z")
    if "T" in value:
        return datetime.strptime(value[:15], "%Y%m%dT%H%M%S"), False
    return datetime.strptime(value[:8], "%Y%m%d"), True


def parse_ics(text: str) -> list[dict]:
    """Events from an iCal file: {title, start, end, all_day, location, description, url}, sorted by start."""
    events, current = [], None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT" and current is not None:
            if current.get("start") and current.get("title"):
                events.append(current)
            current = None
        elif current is not None and ":" in line:
            key, value = line.split(":", 1)
            name = key.split(";", 1)[0].upper()
            if name == "SUMMARY":
                current["title"] = _unescape(value)
            elif name in ("DTSTART", "DTEND"):
                try:
                    moment, all_day = _parse_time(value)
                except ValueError:
                    continue
                current["start" if name == "DTSTART" else "end"] = moment
                if name == "DTSTART":
                    current["all_day"] = all_day
            elif name == "LOCATION":
                current["location"] = _unescape(value) or None
            elif name == "DESCRIPTION":
                current["description"] = _unescape(value) or None
            elif name == "URL":
                current["url"] = value.strip() or None
    for e in events:
        for k in ("end", "location", "description", "url"):
            e.setdefault(k, None)
    return sorted(events, key=lambda e: e["start"])


def is_fitness(event: dict) -> bool:
    return bool(_FITNESS.search(f"{event['title']} {event.get('location') or ''}"))


def fetch_events(now: float | None = None) -> list[dict]:
    """The calendar's events, from the cache when it is fresh. Raises requests.RequestException
    when the campus server can't be reached and nothing is cached."""
    now = now or time.time()
    if _cache["events"] is not None and now - _cache["at"] < CACHE_SECONDS:
        return _cache["events"]
    try:
        r = requests.get(FEED_URL, timeout=20)
        r.raise_for_status()
        events = parse_ics(r.text)
    except requests.RequestException:
        if _cache["events"] is not None:
            return _cache["events"]  # an hour-old list beats an error
        raise
    _cache.update(at=now, events=events)
    return events


def upcoming(events: list[dict], start: date, days: int, fitness_only: bool = True, q: str | None = None) -> list[dict]:
    """Events starting from `start` for `days` days, optionally only exercise and matching `q`."""
    end = start + timedelta(days=days)
    q = (q or "").strip().lower()
    out = []
    for e in events:
        if not start <= e["start"].date() < end:
            continue
        if fitness_only and not is_fitness(e):
            continue
        if q and q not in f"{e['title']} {e['location'] or ''} {e['description'] or ''}".lower():
            continue
        out.append({**e, "description": (e["description"] or "")[:300] or None})
    return out
