"""Run in dashboard container. Advances global event time; use after other demos."""
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.request import urlopen
import psycopg
from kafka import KafkaProducer
from cricx.fixtures import fixture


def metric(name):
    with urlopen("http://spark:9101/metrics", timeout=5) as response:
        for line in response.read().decode().splitlines():
            if line.startswith(name + " "):
                return float(line.split()[1])
    return 0


def wait_for(predicate):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(1)
    raise TimeoutError("Watermark verification condition did not converge")


if __name__ == "__main__":
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        maximum = conn.execute("SELECT max((payload->>'event_time')::timestamptz) FROM delivery_events").fetchone()[0]
    origin = max(maximum or datetime.now(timezone.utc), datetime.now(timezone.utc)) + timedelta(minutes=5)
    match = "late-" + uuid.uuid4().hex[:12]
    events = fixture(match)[:3]
    producer = KafkaProducer(bootstrap_servers="kafka:29092", acks="all", value_serializer=lambda event: json.dumps(event).encode())
    for event, seconds in zip(events[:2], (0, 90)):
        event["event_time"] = (origin + timedelta(seconds=seconds)).isoformat()
        producer.send("match-events", key=match.encode(), value=event).get(timeout=20)
    wait_for(lambda: metric("cricx_window_watermark_seconds") >= (origin + timedelta(seconds=60)).timestamp())
    before = metric("cricx_window_late_rows_total")
    events[2]["event_time"] = (origin + timedelta(seconds=1)).isoformat()
    producer.send("match-events", key=match.encode(), value=events[2]).get(timeout=20)
    wait_for(lambda: metric("cricx_window_late_rows_total") > before)
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        count = conn.execute("SELECT count(*) FROM delivery_events WHERE match_id=%s", (match,)).fetchone()[0]
        card = conn.execute("SELECT runs,wickets,legal_balls,extras FROM innings_scorecard WHERE match_id=%s", (match,)).fetchone()
    assert count == 3 and card == (6, 0, 2, 1), (count, card)
    print(json.dumps({"match": match, "canonical_events": count, "scorecard": card, "watermark_drops": metric("cricx_window_late_rows_total") - before}))
    producer.close()
