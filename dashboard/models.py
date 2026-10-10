"""Read-only chart/card derivations from canonical accepted delivery payloads."""
from cricx.events import total_runs, legal as is_legal


def over_text(balls):
    return f"{balls // 6}.{balls % 6}"


def summarize(events, overs_limit):
    runs = balls = 0
    progress = [{"overs": 0, "runs": 0}]
    wickets, deliveries = [], []
    phases = {}
    partnership = {"runs": 0, "balls": 0, "players": []}
    last_partnership = None
    for event in sorted(events, key=lambda item: item["raw_delivery_sequence"]):
        over = balls // 6
        phase = ("Powerplay (1–10)" if over < 10 else "Middle (11–40)" if over < 40 else "Death (41–50)") if overs_limit == 50 else ("Powerplay (1–6)" if over < 6 else "Middle (7–15)" if over < 15 else "Death (16–20)")
        bucket = phases.setdefault(phase, {"Phase": phase, "Runs": 0, "Wickets": 0, "Balls": 0})
        gained, legal = total_runs(event), int(is_legal(event))
        runs += gained
        balls += legal
        bucket["Runs"] += gained
        bucket["Balls"] += legal
        partnership["runs"] += gained
        partnership["balls"] += legal
        partnership["players"] = [event["striker"], event["non_striker"]]
        if event["wicket_type"]:
            bucket["Wickets"] += 1
            wickets.append({"#": len(wickets) + 1, "Score": runs, "Over": over_text(balls), "Player": event["player_out"]})
            last_partnership = partnership
            partnership = {"runs": 0, "balls": 0, "players": []}
        marker = "W" if event["wicket_type"] else "Wd" if event["extras"]["wides"] else "Nb" if event["extras"]["no_balls"] else str(gained)
        deliveries.append({"marker": marker, "over": over, "runs": gained, "sequence": event["raw_delivery_sequence"]})
        progress.append({"overs": balls / 6, "runs": runs})
    phase_rows = [{"Phase": p["Phase"], "Overs": over_text(p["Balls"]), "Runs": p["Runs"], "Wickets": p["Wickets"],
                   "RR": f"{p['Runs'] * 6 / p['Balls']:.2f}" if p["Balls"] else "—"} for p in phases.values()]
    current_over = deliveries[-1]["over"] if deliveries else 0
    return dict(progress=progress, wickets=wickets, phases=phase_rows, deliveries=deliveries,
                current_over=current_over, current_balls=[d for d in deliveries if d["over"] == current_over],
                partnership=partnership, last_partnership=last_partnership)
