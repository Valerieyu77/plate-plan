from datetime import date, datetime

import pytest
import requests

from app import events

ICS = """BEGIN:VCALENDAR\r
VERSION:2.0\r
BEGIN:VEVENT\r
DTSTART:20261028T111500\r
DTEND:20261028T123000\r
SUMMARY:Lunch Skate\r
LOCATION:Ice Arena 406 E. Armory Ave. Champaign\\, IL 61820\r
URL:https://calendars.illinois.edu/detail/637/1\r
DESCRIPTION:Skate rental is available\\nbring a\r
  student ID.\r
END:VEVENT\r
BEGIN:VEVENT\r
DTSTART:20261028T133000\r
SUMMARY:Flu Shots: Gies College of Business\r
LOCATION:BIF Atrium\r
END:VEVENT\r
BEGIN:VEVENT\r
DTSTART;VALUE=DATE:20261030\r
SUMMARY:Sunrise Yoga on the Quad\r
END:VEVENT\r
BEGIN:VEVENT\r
DTSTART:20261110T180000\r
SUMMARY:Intramural Basketball Registration\r
LOCATION:ARC\r
END:VEVENT\r
END:VCALENDAR\r
"""


def test_parse_unfolds_lines_unescapes_text_and_reads_all_day_events():
    parsed = events.parse_ics(ICS)
    assert [e["title"] for e in parsed] == [
        "Lunch Skate", "Flu Shots: Gies College of Business", "Sunrise Yoga on the Quad", "Intramural Basketball Registration"]
    skate = parsed[0]
    assert skate["start"] == datetime(2026, 10, 28, 11, 15) and skate["end"] == datetime(2026, 10, 28, 12, 30)
    assert skate["location"] == "Ice Arena 406 E. Armory Ave. Champaign, IL 61820"
    assert skate["description"] == "Skate rental is available\nbring a student ID."
    assert skate["url"].endswith("/637/1") and skate["all_day"] is False
    yoga = parsed[2]
    assert yoga["all_day"] is True and yoga["end"] is None and yoga["location"] is None


def test_upcoming_keeps_exercise_in_the_date_range():
    parsed = events.parse_ics(ICS)
    week = events.upcoming(parsed, date(2026, 10, 28), 7)
    assert [e["title"] for e in week] == ["Lunch Skate", "Sunrise Yoga on the Quad"]  # no flu shots, nothing in November
    assert len(events.upcoming(parsed, date(2026, 10, 28), 7, fitness_only=False)) == 3
    assert [e["title"] for e in events.upcoming(parsed, date(2026, 10, 1), 60, q="basketball")] == [
        "Intramural Basketball Registration"]


def test_fetch_uses_the_cache_and_falls_back_to_it_when_the_server_is_down(monkeypatch):
    calls = []

    class Response:
        text = ICS

        def raise_for_status(self):
            pass

    def fake_get(url, timeout):
        calls.append(url)
        return Response()

    monkeypatch.setattr(events, "_cache", {"at": 0.0, "events": None})
    monkeypatch.setattr(events.requests, "get", fake_get)
    first = events.fetch_events(now=10_000)
    events.fetch_events(now=10_000 + 60)
    assert len(calls) == 1 and len(first) == 4  # the second call was served from the cache

    def down(url, timeout):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(events.requests, "get", down)
    assert events.fetch_events(now=10_000 + events.CACHE_SECONDS + 1) == first  # stale beats an error
    monkeypatch.setattr(events, "_cache", {"at": 0.0, "events": None})
    with pytest.raises(requests.RequestException):
        events.fetch_events(now=1)


def test_a_gym_name_alone_does_not_make_an_event_exercise():
    blood_drive = {"title": "Annual Deterding Blood Drive", "location": "ARC MP6"}
    party = {"title": "Well-O-Ween", "location": "ARC Well-Being Lounge"}
    skating = {"title": "Freestyle", "location": "Ice Arena 406 E. Armory Ave."}
    assert not events.is_fitness(blood_drive) and not events.is_fitness(party)
    assert events.is_fitness(skating) and events.is_fitness({"title": "Spin Class", "location": "ARC"})
