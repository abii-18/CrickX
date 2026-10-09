"""Known synthetic innings and deterministic replay source."""
from datetime import datetime, timedelta, timezone


def fixture(match_id="demo-001"):
    outcomes = [(1, {}, None), (4, {}, None), (0, {"wides": 1}, None),
                (2, {"no_balls": 1}, None), (0, {"byes": 2}, None),
                (0, {}, "run_out"), (6, {}, None), (0, {}, "bowled")]
    events = []
    start = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
    for sequence, (runs, extras, wicket) in enumerate(outcomes, 1):
        events.append({"schema_version": 1, "event_id": f"{match_id}:1:{sequence}:1",
             "match_id": match_id, "innings_number": 1, "raw_delivery_sequence": sequence,
             "revision_number": 1, "event_time": (start + timedelta(seconds=sequence)).isoformat(),
             "striker": "Batter A", "non_striker": "Batter B", "bowler": "Bowler X",
             "batter_runs": runs, "extras": {k: extras.get(k, 0) for k in ("wides", "no_balls", "byes", "leg_byes")},
             "wicket_type": wicket, "player_out": ("Batter B" if wicket == "run_out" else "Batter A") if wicket else None})
    return events
