"""Explicit local demo: preserve replay, verify faults/recovery, restore replay.

Run inside dashboard. Evidence is written to /tmp/cricx-demo.json, not screenshots
or fabricated benchmark data. PostgreSQL/Spark stop/start commands stay explicit.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import psycopg
from experiments.prepare_ui_preview import api
from cricx.scoring import score

EVIDENCE = Path("/tmp/cricx-demo.json")


def now():
    return datetime.now(timezone.utc).isoformat()


def committed(match, expected_count):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
                events = [row[0] for row in conn.execute("SELECT payload FROM delivery_events WHERE match_id=%s ORDER BY innings_number,raw_delivery_sequence", (match,))]
                cards = conn.execute("SELECT innings_number,runs,wickets,legal_balls,extras FROM innings_scorecard WHERE match_id=%s ORDER BY innings_number", (match,)).fetchall()
            if len(events) == expected_count and len(cards) == 2:
                calculated = score(events)
                for innings, *actual in cards:
                    assert actual == [calculated[(match, innings)][key] for key in ("runs", "wickets", "legal_balls", "extras")]
                return {"match_id": match, "accepted": len(events), "scorecards": [list(card) for card in cards], "verified_at": now()}
        except psycopg.OperationalError:
            pass
        time.sleep(2)
    raise TimeoutError("Committed deliveries and scorecards did not reconcile")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["duplicate", "queue-recovery", "verify-recovery", "verify-restart", "mark-alert", "verify-alert", "restore"])
    step = parser.parse_args().step
    evidence = json.loads(EVIDENCE.read_text()) if EVIDENCE.exists() else {}
    if step == "duplicate":
        if "original" not in evidence:
            current = api()
            evidence["original"] = {key: current.get(key) for key in ("match_id", "cursor", "rate", "running")}
            EVIDENCE.write_text(json.dumps(evidence))
        api("/pause", {})
        subprocess.run([sys.executable, "-m", "experiments.verify_injection_controls"], check=True)
        status = api()
        observed = committed(status["match_id"], status["expected_deliveries"])
        observed["acknowledged_messages"] = status["cursor"]
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            observed["invalid_audit_rows"] = conn.execute("SELECT count(*) FROM rejected_events WHERE raw_payload LIKE %s", ("%"+status["match_id"]+"%",)).fetchone()[0]
        assert observed["acknowledged_messages"] == 19 and observed["accepted"] == 17
        evidence["duplicate"] = observed
    elif step == "queue-recovery":
        api("/new", {"overs": 2, "seed": 42, "rate": 100})
        deadline = time.monotonic()+30
        while api()["running"]:
            if time.monotonic() > deadline:
                raise TimeoutError("Kafka replay did not finish")
            time.sleep(.2)
        status = api()
        evidence["recovery_queued"] = {"match_id": status["match_id"], "expected": status["expected_deliveries"], "acknowledged": status["cursor"], "queued_at": now()}
    elif step in ("verify-recovery", "verify-restart"):
        queued = evidence["recovery_queued"]
        evidence[step] = committed(queued["match_id"], queued["expected"])
        assert evidence[step]["scorecards"] == [[1, 14, 0, 12, 1], [2, 15, 0, 5, 0]]
    elif step == "mark-alert":
        evidence["alert_after"] = now()
    elif step == "verify-alert":
        deadline = time.monotonic()+100
        while time.monotonic() < deadline:
            fresh = [item for item in api().get("alerts", []) if item["name"] == "CricXProcessorUnavailable" and item["status"] == "firing" and item["received_at"] >= evidence["alert_after"]]
            if fresh:
                evidence["alert"] = fresh[-1]
                break
            time.sleep(2)
        else:
            raise TimeoutError("No newly routed processor-down alert")
    else:
        original = evidence["original"]
        if original["match_id"]:
            api("/select", {"match_id": original["match_id"]})
            api("/speed", {"rate": original["rate"]})
            api("/pause", {})
            assert api()["cursor"] == original["cursor"]
        evidence["restored_paused_at"] = now()
    EVIDENCE.write_text(json.dumps(evidence, indent=2))
    print(json.dumps({"step": step, "evidence": evidence}, indent=2))


if __name__ == "__main__":
    main()
