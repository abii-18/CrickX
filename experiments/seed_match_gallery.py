"""Create five ODI fixtures through Kafka/Spark, reconcile, restore paused replay.

Run explicitly inside the dashboard container; never runs on dashboard refresh.
"""
import json
import os
import time
from urllib.request import Request, urlopen
import psycopg
from cricx.teams import MATCH_PROFILES, PROFILE
from cricx.scoring import score


def control(path="", data=None):
    request = Request("http://simulator:9700" + path,
                      data=json.dumps(data).encode() if data is not None else None,
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def main():
    original = control().get("match_id")
    control("/pause", {})
    try:
        for seed, profile in enumerate(MATCH_PROFILES, 7):
            if profile == PROFILE:
                continue
            # Re-running this demonstration does not create duplicate fixtures.
            with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
                existing = conn.execute("SELECT 1 FROM delivery_events WHERE payload->>'match_profile'=%s LIMIT 1", (profile,)).fetchone()
            if existing:
                continue
            control("/new", {"profile": profile, "overs": 50, "seed": seed, "rate": 100})
            deadline = time.monotonic()+120
            while time.monotonic() < deadline:
                status = control()
                with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
                    events = [row[0] for row in conn.execute("SELECT payload FROM delivery_events WHERE match_id=%s ORDER BY innings_number,raw_delivery_sequence", (status["match_id"],))]
                    cards = conn.execute("SELECT innings_number,runs,wickets,legal_balls,extras FROM innings_scorecard WHERE match_id=%s ORDER BY innings_number", (status["match_id"],)).fetchall()
                if not status["running"] and len(events) == status["expected_deliveries"]:
                    expected = score(events)
                    assert len(cards) == 2
                    for innings, *actual in cards:
                        card = expected[(status["match_id"], innings)]
                        assert actual == [card[key] for key in ("runs", "wickets", "legal_balls", "extras")]
                    print(json.dumps({"fixture": MATCH_PROFILES[profile], "match_id": status["match_id"], "accepted": len(events), "scorecards": cards}), flush=True)
                    break
                time.sleep(2)
            else:
                raise TimeoutError("Fixture failed to reconcile in 120 seconds")
    finally:
        if original:
            control("/select", {"match_id": original})
            control("/pause", {})


if __name__ == "__main__":
    main()
