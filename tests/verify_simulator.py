"""Explicit running-stack smoke test: run inside dashboard container."""
import json
import os
import time
import sys
from urllib.request import Request, urlopen
import psycopg
from cricx.scoring import score


def control(path="", data=None):
    req = Request("http://simulator:9700" + path, data=json.dumps(data).encode() if data is not None else None,
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=30) as response:
        return json.load(response)


if __name__ == "__main__":
    if "--existing" not in sys.argv:
        control("/new", {"seed": 42, "overs": 50 if "--odi" in sys.argv else 2, "rate": 100})
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        status = control()
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            events = [row[0] for row in conn.execute("SELECT payload FROM delivery_events WHERE match_id=%s ORDER BY innings_number,raw_delivery_sequence", (status["match_id"],))]
            cards = conn.execute("SELECT innings_number,runs,wickets,legal_balls,extras FROM innings_scorecard WHERE match_id=%s ORDER BY innings_number", (status["match_id"],)).fetchall()
        if not status["running"] and len(events) == status["total"]:
            expected = score(events)
            assert len(cards) == 2
            for innings, runs, wickets, balls, extras in cards:
                card = expected[(status["match_id"], innings)]
                assert (runs, wickets, balls, extras) == tuple(card[key] for key in ("runs", "wickets", "legal_balls", "extras"))
            print(json.dumps({"match_id": status["match_id"], "accepted_deliveries": len(events), "scorecards": cards}))
            break
        time.sleep(2)
    else:
        raise TimeoutError("Simulator did not produce two committed scorecards within 120 seconds")
