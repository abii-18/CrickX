"""CLI deterministic replay. Fresh match by default; --match-id repeats a run."""
import argparse
import copy
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from kafka import KafkaProducer
from cricx.fixtures import fixture


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--match-id", default=None)
    parser.add_argument("--rate", type=float, default=1)
    parser.add_argument("--duplicate", action="store_true")
    parser.add_argument("--correction", action="store_true")
    parser.add_argument("--invalid", action="store_true")
    parser.add_argument("--late", action="store_true")
    args = parser.parse_args()
    if args.rate <= 0:
        parser.error("--rate must be positive")
    match = args.match_id or "demo-" + uuid.uuid4().hex[:10]
    producer = KafkaProducer(bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP", "localhost:9092"),
            acks="all", retries=5, value_serializer=lambda value: json.dumps(value).encode())
    print(f"Replaying SIMULATED match {match}", flush=True)
    events = fixture(match)
    # Keep IDs and timestamps fixed so replay preserves delivery identity.
    for event in events:
        producer.send("match-events", key=match.encode(), value=event).get(timeout=30)
        print(event["event_id"], flush=True)
        if args.duplicate:
            producer.send("match-events", key=match.encode(), value=event).get(timeout=30)
        time.sleep(1 / args.rate)
    if args.correction:
        event = copy.deepcopy(events[1]); event.update(revision_number=2, event_id=f"{match}:1:2:2", batter_runs=6)
        producer.send("match-events", key=match.encode(), value=event).get(timeout=30)
    if args.invalid:
        producer.send("match-events", key=match.encode(), value={"match_id": match, "batter_runs": -1}).get(timeout=30)
    if args.late:
        event = copy.deepcopy(events[0]); event.update(event_id=f"{match}:1:9:1", raw_delivery_sequence=9,
             event_time=(datetime(2026, 10, 10, 12, tzinfo=timezone.utc)-timedelta(minutes=10)).isoformat(), wicket_type=None, player_out=None)
        producer.send("match-events", key=match.encode(), value=event).get(timeout=30)
    producer.flush(); producer.close()


if __name__ == "__main__":
    main()
