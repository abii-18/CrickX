"""Finite Kafka/Spark/PostgreSQL replay. Use a fresh --match for each run."""
import argparse
import copy
import json
import os
import time
from urllib.request import urlopen
import psycopg
from kafka import KafkaProducer
from cricx.fixtures import fixture
from cricx.scoring import score
from dashboard.models import summarize


def scenario(match):
    events = fixture(match)
    for sequence in range(9, 16):
        event = copy.deepcopy(events[0])
        event.update(event_id=f"{match}:{sequence}", raw_delivery_sequence=sequence)
        events.append(event)
    second = copy.deepcopy(events[0])
    second.update(event_id=match + ":innings2", innings_number=2)
    events.append(second)
    correction = copy.deepcopy(events[2])
    correction.update(event_id=match + ":rev2", revision_number=2, event_time="2020-01-01T00:00:00Z")
    correction["extras"]["wides"] = 0
    return events, correction


def publish(match, values):
    producer = KafkaProducer(bootstrap_servers="kafka:29092", acks="all")
    try:
        for value in values:
            raw = value if isinstance(value, str) else json.dumps(value)
            producer.send("match-events", key=match.encode(), value=raw.encode()).get(timeout=20)
    finally:
        producer.close()


def verify(match, expected):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            events = [r[0] for r in conn.execute("SELECT payload FROM delivery_events WHERE match_id=%s", (match,))]
            cards = conn.execute("SELECT innings_number,runs,wickets,legal_balls,extras FROM innings_scorecard WHERE match_id=%s ORDER BY innings_number", (match,)).fetchall()
            overs = conn.execute("SELECT innings_number,over_number,runs,wickets,legal_balls FROM over_summary WHERE match_id=%s ORDER BY innings_number,over_number", (match,)).fetchall()
            batting = conn.execute("SELECT innings_number,player,runs,balls,fours,sixes,dismissal FROM batting_scorecard WHERE match_id=%s ORDER BY innings_number,player", (match,)).fetchall()
            bowling = conn.execute("SELECT innings_number,player,runs,legal_balls,wickets FROM bowling_scorecard WHERE match_id=%s ORDER BY innings_number,player", (match,)).fetchall()
        expected_cards = [(inn, *[result[k] for k in ("runs", "wickets", "legal_balls", "extras")]) for (_, inn), result in sorted(expected.items())]
        if cards == expected_cards:
            assert len(events) == 16
            assert score(events) == expected
            expected_overs, expected_batting, expected_bowling = [], [], []
            for (_, inn), result in sorted(expected.items()):
                expected_overs.extend((inn, over, *[v[k] for k in ("runs", "wickets", "legal_balls")]) for over, v in sorted(result["overs"].items()))
                expected_batting.extend((inn, player, *[v[k] for k in ("runs", "balls", "fours", "sixes", "dismissal")]) for player, v in sorted(result["batting"].items()))
                expected_bowling.extend((inn, player, *[v[k] for k in ("runs", "legal_balls", "wickets")]) for player, v in sorted(result["bowling"].items()))
                display = summarize([e for e in events if e["innings_number"] == inn], 50)
                assert display["progress"][-1]["runs"] == result["runs"]
            assert overs == expected_overs, overs
            assert batting == expected_batting, batting
            assert bowling == expected_bowling, bowling
            with urlopen("http://spark:9101/metrics", timeout=5) as response:
                metrics = response.read().decode().splitlines()
            verified = next(float(line.split()[1]) for line in metrics if line.startswith("cricx_spark_verified_over_rows_total "))
            assert verified > 0, verified
            print(json.dumps({"match": match, "canonical_deliveries": len(events), "scorecards": cards,
                              "over_summary": overs, "batting_bowling_reference_agreement": True,
                              "dashboard_model_agreement": True, "observed_verified_over_rows": verified}), flush=True)
            return
        time.sleep(1)
    raise TimeoutError("Canonical cards did not converge in 120 seconds")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--match", required=True)
    parser.add_argument("--action", choices=("publish", "verify", "queue-recovery", "verify-recovery"), default="publish")
    args = parser.parse_args()
    events, correction = scenario(args.match)
    if args.action == "publish":
        conflict = copy.deepcopy(correction)
        conflict.update(event_id=args.match + ":conflict", batter_runs=4)
        publish(args.match, list(reversed(events)) + events + [correction, events[2], conflict, "{malformed"])
    if args.action in ("queue-recovery", "verify-recovery"):
        correction.update(event_id=args.match + ":rev3", revision_number=3, batter_runs=2)
    if args.action == "queue-recovery":
        publish(args.match, [correction, correction])
        print(json.dumps({"match": args.match, "queued_messages": 2}))
    else:
        verify(args.match, score(events + [correction]))
