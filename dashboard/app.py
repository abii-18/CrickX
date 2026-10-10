"""Cricket-first UI; live statistics read from a consistent PostgreSQL snapshot."""
import os
import json
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError
import psycopg
from psycopg.rows import dict_row
import streamlit as st
from dashboard.models import summarize, over_text
from dashboard.flags import flag_svg
from cricx.teams import INDIA, AUSTRALIA, PROFILE

st.set_page_config(page_title="CricX · India vs Australia", page_icon="🏏", layout="wide")
st.markdown(f"<style>{Path('dashboard/style.css').read_text()}</style>", unsafe_allow_html=True)
st.markdown('<div class="brandbar"><div class="brand">Cric<span>X</span></div><div class="brandnote">BALL BY BALL. EVENT BY EVENT.</div></div>', unsafe_allow_html=True)


def simulator(path="", data=None):
    request = Request(os.environ.get("SIMULATOR_URL", "http://simulator:9700") + path,
                      data=json.dumps(data).encode() if data is not None else None,
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=25) as response:
        return json.load(response)


def command(path, data):
    try:
        simulator(path, data)
    except (URLError, TimeoutError) as exc:
        st.warning(f"Control unavailable: {type(exc).__name__}")


def html(text):
    st.markdown(text, unsafe_allow_html=True)


def table(rows, columns):
    if not rows:
        html('<div class="empty">Waiting for accepted deliveries</div>')
        return
    header = ''.join(f'<th>{escape(str(label))}</th>' for label, _ in columns)
    body = ''.join('<tr>' + ''.join(f'<td>{escape(str(row.get(key, "—")))}</td>' for _, key in columns) + '</tr>' for row in rows)
    html(f'<table class="crictable"><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>')


def balls_html(deliveries):
    parts = []
    for delivery in deliveries:
        marker = delivery["marker"]
        cls = "wicket" if marker == "W" else "six" if marker == "6" else "boundary" if marker == "4" else "extra" if marker in ("Wd", "Nb") else ""
        parts.append(f'<span class="ball {cls}" title="Delivery {delivery["sequence"]}">{escape(marker)}</span>')
    return '<div class="balls">' + ''.join(parts) + '</div>'


def tile(label, value, foot=""):
    html(f'<div class="tile"><div class="tilelabel">{escape(label)}</div><div class="tilevalue">{escape(str(value))}</div><div class="tilefoot">{escape(foot)}</div></div>')


def title(text):
    html(f'<div class="paneltitle">{escape(text)}</div>')


def chart(data, series=False):
    spec = {"height": 160, "background": "transparent", "mark": {"type": "line", "point": True, "strokeWidth": 2},
            "encoding": {"x": {"field": "overs", "type": "quantitative", "title": "Overs", "axis": {"grid": False}},
                         "y": {"field": "runs", "type": "quantitative", "title": "Runs"},
                         "tooltip": [{"field": "overs", "type": "quantitative", "format": ".2f"}, {"field": "runs", "type": "quantitative"}]},
            "config": {"view": {"stroke": None}, "axis": {"labelColor": "#8ba3bd", "titleColor": "#8ba3bd", "gridColor": "#20374c"}}}
    spec["encoding"]["color"] = {"field": "team", "type": "nominal", "scale": {"domain": ["India", "Australia"], "range": ["#218af5", "#efc841"]}, "legend": {"title": None, "labelColor": "#a9bdd3", "orient": "top"}} if series else {"value": "#218af5"}
    st.vega_lite_chart(data, spec, use_container_width=True)


def batting_rows(innings, rows, full=False, active=False):
    roster = INDIA if innings == 1 else AUSTRALIA
    selected = sorted([dict(row, sr=f"{row['runs']*100/row['balls']:.1f}" if row['balls'] else "—", dismissal=row['dismissal'] or "not out") for row in rows if row["innings_number"] == innings], key=lambda row: roster.index(row["player"]) if row["player"] in roster else 99)
    if active:
        selected = [row for row in selected if row["dismissal"] == "not out"]
    columns = [("Batter", "player"), ("R", "runs"), ("B", "balls"), ("4s", "fours"), ("6s", "sixes"), ("SR", "sr")]
    table(selected, columns + ([("Dismissal", "dismissal")] if full else []))


def bowling_rows(innings, rows):
    selected = [dict(row, overs=over_text(row["legal_balls"]), econ=f"{row['runs']*6/row['legal_balls']:.2f}" if row["legal_balls"] else "—") for row in rows if row["innings_number"] == innings]
    table(selected, [("Bowler", "player"), ("O", "overs"), ("R", "runs"), ("W", "wickets"), ("Econ", "econ")])


def controls(status, is_current, complete):
    with st.container(border=True):
        title("Simulator Controls")
        buttons, speed, faults = st.columns([1.25, 1.25, 1.4])
        with buttons:
            a, b, c = st.columns(3)
            if a.button("▶ Start", type="primary", use_container_width=True):
                command("/resume" if is_current and not complete else "/new", {} if is_current and not complete else {"overs": 50, "seed": 42, "rate": 2})
                st.rerun()
            if b.button("Ⅱ Pause", use_container_width=True):
                command("/pause", {})
                st.rerun()
            if c.button("↻ Reset", use_container_width=True, help="Start a new match ID; preserve previous scorecards"):
                command("/new", {"overs": 50, "seed": 42, "rate": status.get("rate", 2)})
                st.rerun()
        with speed:
            rates = [0.5, 1, 2, 5, 10, 25, 100]
            if "speed" not in st.session_state or st.session_state.get("rate_match") != status.get("match_id"):
                st.session_state["speed"] = min(rates, key=lambda candidate: abs(candidate-status.get("rate", 2)))
                st.session_state["rate_match"] = status.get("match_id")
            rate = st.select_slider("Replay speed · deliveries/sec", options=rates, key="speed",
                                    on_change=lambda: command("/speed", {"rate": st.session_state["speed"]}))
        with faults:
            x, y, z = st.columns(3)
            for column, mode, text in [(x, "duplicate", "Duplicate"), (y, "invalid", "Invalid"), (z, "delay", "Delay")]:
                if column.button(text, use_container_width=True, help="Inject one controlled event fault"):
                    command("/inject", {"mode": mode})
        with st.popover("⚙ Replay settings"):
            limit = st.selectbox("Match length", [50, 20, 5, 2], format_func=lambda value: f"{value} overs per innings" + (" · ODI" if value == 50 else " · short demo"))
            seed = st.number_input("Simulation seed", min_value=0, max_value=1000000, value=42)
            if st.button("Start configured match"):
                command("/new", {"overs": limit, "seed": seed, "rate": rate})
                st.rerun()


@st.fragment(run_every="3s")
def live():
    try:
        status = simulator()
    except (URLError, TimeoutError):
        status = {}
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            matches = conn.execute("SELECT m.match_id FROM matches m WHERE EXISTS (SELECT 1 FROM delivery_events d WHERE d.match_id=m.match_id AND d.payload->>'match_profile'=%s) ORDER BY m.created_at DESC", (PROFILE,)).fetchall()
            choices = [match["match_id"] for match in matches]
            preferred = status.get("match_id")
            match = st.selectbox("Match replay", choices, index=choices.index(preferred) if preferred in choices else 0, format_func=lambda value: f"India vs Australia · {value[-12:]}", label_visibility="collapsed") if choices else None
            params = (match,)
            cards = conn.execute("SELECT * FROM innings_scorecard WHERE match_id=%s ORDER BY innings_number", params).fetchall()
            payloads = [row["payload"] for row in conn.execute("SELECT payload FROM delivery_events WHERE match_id=%s ORDER BY innings_number,raw_delivery_sequence", params)]
            batters = conn.execute("SELECT * FROM batting_scorecard WHERE match_id=%s", params).fetchall()
            bowlers = conn.execute("SELECT * FROM bowling_scorecard WHERE match_id=%s", params).fetchall()
            over_rows = conn.execute("SELECT * FROM over_summary WHERE match_id=%s ORDER BY innings_number,over_number", params).fetchall()
    except psycopg.Error:
        st.warning("Score service is unavailable. Accepted scores cannot refresh.")
        return
    limit = payloads[0].get("innings_overs", 50) if payloads else 50
    by_innings = {card["innings_number"]: card for card in cards}
    current = max(by_innings, default=1)
    data = {i: summarize([e for e in payloads if e["innings_number"] == i], limit) for i in (1, 2)}
    current_card = by_innings.get(current, dict(runs=0, wickets=0, legal_balls=0, extras=0))
    is_current = match is not None and match == status.get("match_id")
    complete = is_current and status.get("cursor", 0) == status.get("total", -1) and len(payloads) == status.get("expected_deliveries", status.get("total"))
    playing = is_current and status.get("running", False)
    label = "REPLAYING" if playing else "COMPLETED" if complete else "PAUSED" if is_current else "SAVED REPLAY" if match else "READY"
    result = "India batting · First innings · Synthetic match"
    if 2 in by_innings:
        target = by_innings[1]["runs"] + 1
        result = f"Australia need {max(0, target-current_card['runs'])} runs · Target {target}"
        if current_card["runs"] >= target:
            result = f"Australia won by {10-current_card['wickets']} wickets · Simulated result"
        elif complete:
            result = "Match tied · Simulated result" if current_card["runs"] == by_innings[1]["runs"] else f"India won by {by_innings[1]['runs']-current_card['runs']} runs · Simulated result"
    teams_html = []
    for innings, team, code in [(1, "India", "IND"), (2, "Australia", "AUS")]:
        card = by_innings.get(innings)
        score = f"{card['runs']}/{card['wickets']}" if card else "—"
        detail = f"{over_text(card['legal_balls'])} / {limit} overs · RR {card['runs']*6/card['legal_balls']:.2f}" if card and card["legal_balls"] else "Yet to bat" if innings == 2 else "Ready to bat"
        teams_html.append(f'<div class="team"><div class="flag">{flag_svg(team)}</div><div><div class="teamname">{code} · {team.upper()}</div><div class="score">{score}</div><div class="subscore">{detail}</div></div></div>')
    live_tab, score_tab, player_tab, team_tab, analytics_tab, monitor_tab = st.tabs(["Live Match", "Scorecards", "Player Stats", "Team Stats", "Analytics", "Monitoring"])
    with live_tab:
        html(f'<div class="hero"><div class="herotop"><span class="simtag">SIMULATED MATCH</span><span>CRICX MATCH SIMULATOR</span></div><div class="matchtitle">India vs Australia</div><div class="matchsubtitle">{limit}-over simulation · 2023 ODI World Cup players</div><div class="teams">{teams_html[0]}<div class="vs"><span class="state {"" if playing else "paused"}">{label}</span><br>VS</div>{teams_html[1]}</div><div class="result">{escape(result)}</div></div>')
        controls(status, is_current, complete)
        a, b, c, d, e = st.columns([1.35, 1, 1, 1, 1])
        with a: html(f'<div class="tile"><div class="tilelabel">Current Over · {data[current]["current_over"]+1}</div>{balls_html(data[current]["current_balls"])}</div>')
        with b: tile("Runs", f"{current_card['runs']} / {current_card['wickets']}", "India batting" if current == 1 else "Australia batting")
        with c: tile("Overs", over_text(current_card["legal_balls"]), f"of {limit} overs")
        rr = current_card["runs"]*6/current_card["legal_balls"] if current_card["legal_balls"] else 0
        with d: tile("Run Rate", f"{rr:.2f}", "runs per over")
        finished_innings = current_card["wickets"] == 10 or current_card["legal_balls"] >= limit*6 or complete
        with e: tile("Final Score" if finished_innings else "At Current Rate", current_card["runs"] if finished_innings else round(rr*limit) if rr else "—", "accepted innings total" if finished_innings else "linear projection · not a prediction")
        if not payloads:
            st.info("Press Start to generate an India vs Australia match through the streaming pipeline.")
        else:
            current_events = [event for event in payloads if event["innings_number"] == current]
            missing = max(event["raw_delivery_sequence"] for event in current_events)-len(current_events)
            if missing: st.warning(f"Provisional score: {missing} delivery sequence(s) pending.")
        left, right = st.columns(2)
        with left, st.container(border=True):
            title("Batters · " + ("IND" if current == 1 else "AUS"))
            batting_rows(current, batters, active=True)
        with right, st.container(border=True):
            title("Bowlers · " + ("AUS" if current == 1 else "IND"))
            bowling_rows(current, bowlers)
        left, middle, right = st.columns([1, 1, .85])
        with left, st.container(border=True):
            title("Run Progression")
            chart(data[current]["progress"])
        with middle, st.container(border=True):
            title("Worm Chart · IND / AUS")
            chart([dict(row, team="India" if innings == 1 else "Australia") for innings in (1, 2) for row in data[innings]["progress"]], True)
        with right, st.container(border=True):
            title("Last 10 Deliveries")
            html(balls_html(data[current]["deliveries"][-10:]))
            partnership = data[current]["partnership"]
            title("Current Partnership")
            html(f'<div class="partscore">{partnership["runs"]} runs <small>({partnership["balls"]} balls)</small></div>')
            st.caption(" & ".join(partnership["players"]) or "New partnership yet to start")
        left, middle, right = st.columns([1, 1, .85])
        with left, st.container(border=True):
            title("Innings Summary")
            table(data[current]["phases"], [("Phase", "Phase"), ("Overs", "Overs"), ("Runs", "Runs"), ("W", "Wickets"), ("RR", "RR")])
        with middle, st.container(border=True):
            title("Fall of Wickets")
            table(data[current]["wickets"][-4:], [("#", "#"), ("Score", "Score"), ("Over", "Over"), ("Player", "Player")])
            if len(data[current]["wickets"]) > 4:
                st.caption("Latest four wickets · Full history in Analytics")
        with right, st.container(border=True):
            title("Match Info")
            html(f'<div class="matchinfo"><b>Format</b><span>{limit}-over simulation</span><b>Players</b><span>2023 World Cup final XIs</span><b>Venue</b><span>Virtual stadium</span><b>Status</b><span>{label}</span><b>Source</b><span>CricX Event Simulator</span><b>Extras</b><span>{current_card["extras"]}</span></div>')
        if cards: st.caption(f"Last accepted score update: {cards[-1]['updated_at']} · Refreshes every 3 seconds")
    with score_tab:
        for innings in (1, 2):
            st.subheader("India" if innings == 1 else "Australia")
            a, b = st.columns(2)
            with a, st.container(border=True): batting_rows(innings, batters, True)
            with b, st.container(border=True): bowling_rows(innings, bowlers)
    with player_tab:
        st.subheader("Player Performance · This Simulation")
        batting_rows(1, batters, True)
        batting_rows(2, batters, True)
        with st.expander("2023 World Cup final playing XIs"):
            a, b = st.columns(2)
            a.write("**India**\n\n" + "\n\n".join(INDIA))
            b.write("**Australia**\n\n" + "\n\n".join(AUSTRALIA))
    with team_tab:
        st.subheader("Team Comparison")
        table([dict(card, team="India" if card["innings_number"] == 1 else "Australia", overs=over_text(card["legal_balls"])) for card in cards], [("Team", "team"), ("Runs", "runs"), ("Wickets", "wickets"), ("Overs", "overs"), ("Extras", "extras")])
    with analytics_tab:
        st.subheader("Runs per Over")
        chart([dict(overs=row["over_number"]+1, runs=row["runs"], team="India" if row["innings_number"] == 1 else "Australia") for row in over_rows], True)
        for innings in (1, 2):
            title(("India" if innings == 1 else "Australia") + " · Fall of Wickets")
            table(data[innings]["wickets"], [("#", "#"), ("Score", "Score"), ("Over", "Over"), ("Player", "Player")])
        st.caption("Charts derive from accepted canonical deliveries; corrections update them.")
    with monitor_tab:
        st.subheader("Pipeline Monitoring")
        st.markdown("[Open Grafana](http://localhost:3000/d/cricx/cricx-pipeline) · [Open Prometheus](http://localhost:9090/alerts)")
        st.caption(f"Producer acknowledged: {status.get('cursor', 'unavailable')} / {status.get('total', 'unavailable')} · {status.get('match_id', 'not started')}")
        if status.get("error"): st.error(f"Producer error: {status['error']}")
        table(list(reversed(status.get("alerts", []))), [("Alert", "name"), ("Status", "status"), ("Received", "received_at")])
        st.caption("Operational health comes from Prometheus/Grafana.")


live()
