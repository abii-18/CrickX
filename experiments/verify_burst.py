"""Finite duplicate burst; logs measured catch-up, not a capacity claim."""
import json
import os
import time
import uuid
from urllib.request import urlopen
import psycopg
from kafka import KafkaProducer
from cricx.fixtures import fixture


if __name__ == "__main__":
    prefix = "burst-" + uuid.uuid4().hex[:8] + "-"
    producer = KafkaProducer(bootstrap_servers="kafka:29092", acks="all", retries=5,
                             value_serializer=lambda value: json.dumps(value).encode())
    started = time.monotonic()
    futures = []
    for index in range(150):
        for event in fixture(prefix + str(index)):
            for _ in range(2):
                futures.append(producer.send("match-events", key=event["match_id"].encode(), value=event))
    for future in futures:
        future.get(timeout=30)
    published_seconds = time.monotonic() - started
    peak_backlog = 0
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        with urlopen("http://spark:9101/metrics", timeout=5) as response:
            lines = response.read().decode().splitlines()
        peak_backlog = max(peak_backlog, sum(float(line.split()[1]) for line in lines if line.startswith("cricx_spark_backlog_records{")))
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            cards = conn.execute("SELECT runs,wickets,legal_balls,extras FROM innings_scorecard WHERE match_id LIKE %s", (prefix + "%",)).fetchall()
            count = conn.execute("SELECT count(*) FROM delivery_events WHERE match_id LIKE %s", (prefix + "%",)).fetchone()[0]
        if len(cards) == 150 and count == 1200:
            assert all(card == (17, 2, 6, 4) for card in cards)
            print(json.dumps({"prefix": prefix, "published_messages": len(futures), "canonical_deliveries": count,
                              "matches": len(cards), "publish_seconds": round(published_seconds, 2),
                              "catch_up_seconds": round(time.monotonic() - started, 2), "sampled_peak_backlog": peak_backlog}))
            break
        time.sleep(1)
    else:
        raise TimeoutError("Burst did not converge in 180 seconds")
    producer.close()
