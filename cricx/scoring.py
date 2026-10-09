"""Deterministic scoring from canonical deliveries, sorted by raw sequence."""
from cricx.events import legal, total_runs, validate, slot_key


def canonicalize(events):
    slots, event_ids = {}, {}
    for event in events:
        validate(event)
        if event["event_id"] in event_ids and event_ids[event["event_id"]] != event:
            raise ValueError("event_id reused with conflicting payload")
        event_ids[event["event_id"]] = event
        key = slot_key(event)
        previous = slots.get(key)
        if previous and previous["revision_number"] == event["revision_number"] and previous != event:
            raise ValueError("conflicting payload for same slot revision")
        if previous is None or event["revision_number"] > previous["revision_number"]:
            slots[key] = event
    return sorted(slots.values(), key=slot_key)


def score(events):
    result = {}
    for event in canonicalize(events):
        key = (event["match_id"], event["innings_number"])
        innings = result.setdefault(key, {"runs": 0, "wickets": 0, "legal_balls": 0,
                                          "extras": 0, "batting": {}, "bowling": {}, "overs": {}})
        # Position is derived from preceding canonical legal balls, never arrival order.
        over = innings["legal_balls"] // 6
        summary = innings["overs"].setdefault(over, {"runs": 0, "wickets": 0, "legal_balls": 0})
        batter = innings["batting"].setdefault(event["striker"],
                    {"runs": 0, "balls": 0, "fours": 0, "sixes": 0, "dismissal": None})
        bowler = innings["bowling"].setdefault(event["bowler"],
                    {"runs": 0, "legal_balls": 0, "wickets": 0})
        runs, is_legal = total_runs(event), int(legal(event))
        innings["runs"] += runs
        innings["extras"] += sum(event["extras"].values())
        innings["legal_balls"] += is_legal
        summary["runs"] += runs
        summary["legal_balls"] += is_legal
        batter["runs"] += event["batter_runs"]
        batter["balls"] += int(not event["extras"]["wides"])
        batter["fours"] += int(event["batter_runs"] == 4)
        batter["sixes"] += int(event["batter_runs"] == 6)
        bowler["runs"] += event["batter_runs"] + event["extras"]["wides"] + event["extras"]["no_balls"]
        bowler["legal_balls"] += is_legal
        if event["wicket_type"]:
            innings["wickets"] += 1
            summary["wickets"] += 1
            dismissed = innings["batting"].setdefault(event["player_out"],
                    {"runs": 0, "balls": 0, "fours": 0, "sixes": 0, "dismissal": None})
            dismissed["dismissal"] = event["wicket_type"]
            bowler["wickets"] += int(event["wicket_type"] != "run_out")
    return result
