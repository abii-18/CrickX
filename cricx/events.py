"""Strict v1 delivery contract. Slot identity is independent of arrival order."""
from datetime import datetime

DISMISSALS = {"bowled", "caught", "lbw", "stumped", "hit_wicket", "run_out"}
REQUIRED = {"schema_version", "event_id", "match_id", "innings_number",
            "raw_delivery_sequence", "revision_number", "event_time", "striker",
            "non_striker", "bowler", "batter_runs", "extras", "wicket_type", "player_out"}


def slot_key(event):
    return (event["match_id"], event["innings_number"], event["raw_delivery_sequence"])


def validate(event):
    if not isinstance(event, dict):
        raise ValueError("event must be an object")
    missing = REQUIRED - event.keys()
    if missing:
        raise ValueError("missing fields: " + ", ".join(sorted(missing)))
    if type(event["schema_version"]) is not int or event["schema_version"] != 1:
        raise ValueError("unsupported schema_version")
    for name in ("event_id", "match_id", "striker", "non_striker", "bowler"):
        if not isinstance(event[name], str) or not event[name].strip():
            raise ValueError(f"{name} must be a nonempty string")
    for name in ("innings_number", "raw_delivery_sequence", "revision_number", "batter_runs"):
        if type(event[name]) is not int or event[name] < (0 if name == "batter_runs" else 1):
            raise ValueError(f"invalid {name}")
    if event["innings_number"] not in (1, 2) or event["batter_runs"] > 6:
        raise ValueError("v1 supports two innings and batter runs 0..6")
    try:
        timestamp = datetime.fromisoformat(event["event_time"].replace("Z", "+00:00"))
    except (TypeError, AttributeError, ValueError) as exc:
        raise ValueError("invalid event_time") from exc
    if timestamp.tzinfo is None:
        raise ValueError("event_time requires timezone")
    extras = event["extras"]
    if not isinstance(extras, dict) or set(extras) != {"wides", "no_balls", "byes", "leg_byes"}:
        raise ValueError("extras must contain wides, no_balls, byes, leg_byes")
    if any(type(value) is not int or value < 0 for value in extras.values()):
        raise ValueError("extras must be nonnegative integers")
    if extras["no_balls"] > 1:
        raise ValueError("v1 supports one no-ball penalty per delivery")
    if extras["wides"] and (event["batter_runs"] or any(extras[k] for k in ("no_balls", "byes", "leg_byes"))):
        raise ValueError("wide cannot coexist with batter runs or other extras")
    if extras["byes"] and extras["leg_byes"]:
        raise ValueError("byes and leg byes cannot coexist")
    if event["batter_runs"] and (extras["byes"] or extras["leg_byes"]):
        raise ValueError("batter runs cannot coexist with byes or leg byes")
    wicket = event["wicket_type"]
    if wicket is not None and wicket not in DISMISSALS:
        raise ValueError("unsupported dismissal")
    if (wicket is None) != (event["player_out"] is None):
        raise ValueError("wicket_type and player_out must be supplied together")
    if wicket and event["player_out"] not in (event["striker"], event["non_striker"]):
        raise ValueError("player_out must be a batter at the crease")
    if wicket and wicket != "run_out" and event["player_out"] != event["striker"]:
        raise ValueError("only run_out may dismiss the non-striker")
    if extras["no_balls"] and wicket not in (None, "run_out"):
        raise ValueError("unsupported dismissal on no-ball")
    if extras["wides"] and wicket not in (None, "stumped", "run_out", "hit_wicket"):
        raise ValueError("unsupported dismissal on wide")
    return event


def total_runs(event):
    return event["batter_runs"] + sum(event["extras"].values())


def legal(event):
    return not (event["extras"]["wides"] or event["extras"]["no_balls"])
