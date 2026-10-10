"""One transaction per micro-batch: ledger acceptance and serving rebuild together."""
import json
from pathlib import Path
from collections import Counter
import psycopg
from psycopg.types.json import Jsonb
from cricx.events import validate, slot_key
from cricx.scoring import score


def initialize(dsn):
    with psycopg.connect(dsn) as conn:
        schema = Path(__file__).resolve().parent.parent / "database" / "schema.sql"
        conn.execute(schema.read_text(encoding="utf-8"))


def persist(dsn, records):
    counts = Counter()
    with psycopg.connect(dsn) as conn:
        touched = set()
        for source_key, raw in records:
            if raw is None:
                raw = "null"  # Kafka tombstone is audited, not a delivery.
            reason = None
            try:
                event = validate(json.loads(raw))
            except (ValueError, TypeError) as exc:
                reason = str(exc)
            if reason is None:
                match, innings, sequence = slot_key(event)
                conn.execute("INSERT INTO matches(match_id,match_name) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                             (match, f"{match} — Simulated match"))
                # Match row lock serializes writers and prevents read/rebuild races.
                conn.execute("SELECT match_id FROM matches WHERE match_id=%s FOR UPDATE", (match,))
                reused = conn.execute("SELECT payload,revision_history FROM delivery_events WHERE event_id=%s OR revision_history @> %s",
                                      (event["event_id"], Jsonb([{"event_id": event["event_id"]}]))).fetchone()
                existing = conn.execute("SELECT payload,revision_history FROM delivery_events WHERE match_id=%s AND innings_number=%s AND raw_delivery_sequence=%s",
                                        (match, innings, sequence)).fetchone()
                known_versions = ([reused[0]] + reused[1]) if reused else []
                same_id = [version for version in known_versions if version["event_id"] == event["event_id"]]
                if same_id and any(version != event for version in same_id):
                    reason = "event_id reused with conflicting payload"
                elif existing and existing[0] == event:
                    counts["duplicate"] += 1
                    continue
                elif existing and event["revision_number"] <= existing[0]["revision_number"]:
                    reason = "stale revision" if event["revision_number"] < existing[0]["revision_number"] else "conflicting slot revision"
                else:
                    history = existing[1] + [existing[0]] if existing else []
                    conn.execute("""INSERT INTO delivery_events(match_id,innings_number,raw_delivery_sequence,event_id,revision_number,payload,revision_history)
                      VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(match_id,innings_number,raw_delivery_sequence)
                      DO UPDATE SET event_id=EXCLUDED.event_id,revision_number=EXCLUDED.revision_number,
                      payload=EXCLUDED.payload,revision_history=EXCLUDED.revision_history,received_at=now()""",
                      (match, innings, sequence, event["event_id"], event["revision_number"], Jsonb(event), Jsonb(history)))
                    counts["corrected" if existing else "accepted"] += 1
                    touched.add((match, innings))
            if reason is not None:
                inserted = conn.execute("INSERT INTO rejected_events(source_key,reason,raw_payload) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING RETURNING rejection_id", (source_key, reason, raw)).fetchone()
                counts["rejected" if inserted else "rejection_replayed"] += 1
        for match, innings in sorted(touched):
            events = [row[0] for row in conn.execute("SELECT payload FROM delivery_events WHERE match_id=%s AND innings_number=%s", (match, innings))]
            result = score(events)[(match, innings)]
            conn.execute("""INSERT INTO innings_scorecard(match_id,innings_number,runs,wickets,legal_balls,extras)
               VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(match_id,innings_number) DO UPDATE SET
               runs=EXCLUDED.runs,wickets=EXCLUDED.wickets,legal_balls=EXCLUDED.legal_balls,extras=EXCLUDED.extras,updated_at=now()""",
               (match, innings, result["runs"], result["wickets"], result["legal_balls"], result["extras"]))
            for table in ("over_summary", "batting_scorecard", "bowling_scorecard"):
                conn.execute(f"DELETE FROM {table} WHERE match_id=%s AND innings_number=%s", (match, innings))
            for over, data in result["overs"].items():
                conn.execute("INSERT INTO over_summary VALUES (%s,%s,%s,%s,%s,%s)", (match, innings, over, data["runs"], data["wickets"], data["legal_balls"]))
            for player, data in result["batting"].items():
                conn.execute("INSERT INTO batting_scorecard VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (match, innings, player, data["runs"], data["balls"], data["fours"], data["sixes"], data["dismissal"]))
            for player, data in result["bowling"].items():
                conn.execute("INSERT INTO bowling_scorecard VALUES (%s,%s,%s,%s,%s,%s)", (match, innings, player, data["runs"], data["legal_balls"], data["wickets"]))
    return counts
