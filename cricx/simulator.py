"""Seeded India/Australia deliveries with 2023 XIs; synthetic match outcomes."""
import random
from datetime import datetime, timedelta
from cricx.teams import TEAMS, MATCH_PROFILES, PROFILE


def generate_match(match_id, seed, start_time, overs=50, profile=PROFILE):
    if profile not in MATCH_PROFILES:
        raise ValueError("unknown match profile")
    teams = MATCH_PROFILES[profile]
    if not 1 <= overs <= 50:
        raise ValueError("overs must be between 1 and 50")
    start = datetime.fromisoformat(start_time)
    if start.tzinfo is None:
        raise ValueError("start_time must have a timezone")
    rng = random.Random(seed)
    elapsed = 0
    target = None
    events = []
    for innings in (1, 2):
        batting_team = teams[innings - 1]
        bowling_team = teams[2 - innings]
        batters = TEAMS[batting_team][1]
        bowlers = TEAMS[bowling_team][2]
        striker, non_striker, next_batter = 1, 2, 3
        balls = runs = wickets = sequence = 0
        free_hit = False
        while balls < overs * 6 and wickets < 10 and (target is None or runs < target):
            sequence += 1
            extras = dict(wides=0, no_balls=0, byes=0, leg_byes=0)
            weights = [88, 4, 2, 3, 3] if overs == 50 else [80, 5, 3, 3, 9]
            kind = rng.choices(["normal", "wide", "no_ball", "bye", "wicket"], weights)[0]
            if free_hit and kind == "wicket":
                kind = "normal"
            run_weights = [42, 35, 9, 1, 10, 3] if overs == 50 else [30, 35, 10, 1, 17, 7]
            batter_runs = rng.choices([0, 1, 2, 3, 4, 6], run_weights)[0] if kind in ("normal", "no_ball") else 0
            if kind == "wide":
                extras["wides"] = 1
            elif kind == "no_ball":
                extras["no_balls"] = 1
            elif kind == "bye":
                extras["byes"] = 1
            wicket = "bowled" if kind == "wicket" else None
            event = dict(schema_version=1, event_id=f"{match_id}:{innings}:{sequence}:1",
                         match_id=match_id, innings_number=innings, raw_delivery_sequence=sequence,
                         revision_number=1, event_time=(start + timedelta(seconds=elapsed)).isoformat(),
                         striker=batters[striker - 1], non_striker=batters[non_striker - 1],
                         bowler=bowlers[(balls // 6) % 5], batter_runs=batter_runs,
                         extras=extras, wicket_type=wicket, player_out=batters[striker - 1] if wicket else None,
                         match_profile=profile, batting_team=batting_team, bowling_team=bowling_team,
                         innings_overs=overs, match_format="ODI" if overs == 50 else "Short simulation")
            events.append(event)
            elapsed += 1
            runs += batter_runs + sum(extras.values())
            legal = kind not in ("wide", "no_ball")
            if kind == "no_ball":
                free_hit = True
            elif legal:
                free_hit = False
            if wicket:
                wickets += 1
                striker = next_batter
                next_batter += 1
            elif (batter_runs + extras["byes"] + extras["leg_byes"]) % 2:
                striker, non_striker = non_striker, striker
            if legal:
                balls += 1
                if balls % 6 == 0:
                    striker, non_striker = non_striker, striker
        if innings == 1:
            target = runs + 1
    return events
