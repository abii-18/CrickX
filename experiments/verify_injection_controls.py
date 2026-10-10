"""Exercise private duplicate/invalid controls against a finite short match."""
import os
import time
import psycopg
from experiments.prepare_ui_preview import api


if __name__ == "__main__":
    api("/new", {"overs": 2, "seed": 42, "rate": .5})
    deadline = time.monotonic() + 30
    while api()["cursor"] < 1:
        if time.monotonic() > deadline:
            raise TimeoutError("Producer did not acknowledge its first delivery")
        time.sleep(.1)
    api("/pause", {})
    api("/inject", {"mode": "duplicate"})
    api("/inject", {"mode": "invalid"})
    api("/inject", {"mode": "delay"})
    api("/speed", {"rate": 100})
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        status = api()
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            cards = conn.execute("SELECT runs,wickets,legal_balls,extras FROM innings_scorecard WHERE match_id=%s ORDER BY innings_number", (status["match_id"],)).fetchall()
            count = conn.execute("SELECT count(*) FROM delivery_events WHERE match_id=%s", (status["match_id"],)).fetchone()[0]
            rejected = conn.execute("SELECT count(*) FROM rejected_events WHERE raw_payload LIKE %s", ("%" + status["match_id"] + "%",)).fetchone()[0]
        if not status["running"] and count == status["expected_deliveries"] and rejected:
            assert cards == [(14, 0, 12, 1), (15, 0, 5, 0)], cards
            assert status["total"] == count + 2
            print(f"Injection controls passed: {status['total']} messages, {count} canonical deliveries, {rejected} invalid rejection; unchanged scorecards")
            break
        time.sleep(1)
    else:
        raise TimeoutError("Injection controls did not converge")
