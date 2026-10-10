"""Cricket-first UI; live statistics read from a consistent PostgreSQL snapshot."""
import os
import json
import base64
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError
import psycopg
from psycopg.rows import dict_row
import streamlit as st
from dashboard.models import summarize, over_text
from dashboard.flags import flag_svg
from dashboard.panels import render_tabs
from cricx.teams import TEAMS, MATCH_PROFILES, PROFILE

st.set_page_config(page_title="CricX · Match Centre", page_icon="🏏", layout="wide")
dashboard_dir = Path(__file__).resolve().parent
stylesheet = (dashboard_dir / "style.css").read_text()
stadium_path = dashboard_dir / "assets" / "stadium-night.png"
if stadium_path.exists():
    stadium_image = base64.b64encode(stadium_path.read_bytes()).decode("ascii")
    stylesheet += f'''
    .hero {{
        background-image: linear-gradient(180deg, rgba(3, 12, 25, .35), rgba(3, 12, 25, .65)),
                          url("data:image/png;base64,{stadium_image}");
        background-size: cover;
        background-position: center 58%;
    }}
    .hero::before, .hero::after {{ display: none; }}
    .hero .matchtitle, .hero .score, .hero .teamname, .hero .subscore,
    .hero .matchsubtitle, .hero .result {{ text-shadow: 0 2px 8px rgba(0, 0, 0, .8); }}
    '''
st.markdown(f"<style>{stylesheet}</style>", unsafe_allow_html=True)
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
        return True
    except (URLError, TimeoutError) as exc:
        st.warning(f"Control unavailable: {type(exc).__name__}")
        return False


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


def match_strip(matches, previews, selected, status):
    # One current replay per fixture; older runs remain in the replay archive.
    fixtures = {}
    for row in matches:
        profile = row["payload"]["match_profile"]
        if profile not in fixtures or row["match_id"] == status.get("match_id"):
            fixtures[profile] = row
    rows = sorted(fixtures.values(), key=lambda row: list(MATCH_PROFILES).index(row["payload"]["match_profile"]))
    head, previous, following = st.columns([12, 1, 1])
    with head:
        html(f'<div class="matchnav"><span>All Matches ({len(rows)})</span><span>2023 World Cup XIs · Simulated ODI fixtures</span></div>')
    pages = max(1, (len(rows)+2)//3)
    page = min(st.session_state.get("match_page", 0), pages-1)
    if previous.button("❮", disabled=page == 0, help="Previous matches"):
        st.session_state["match_page"] = page-1
        st.rerun()
    if following.button("❯", disabled=page == pages-1, help="More matches"):
        st.session_state["match_page"] = page+1
        st.rerun()
    for column, row in zip(st.columns(3), rows[page*3:page*3+3]):
        profile = row["payload"]["match_profile"]
        teams = MATCH_PROFILES[profile]
        cards = {card["innings_number"]: card for card in previews if card["match_id"] == row["match_id"]}
        limit = row["payload"].get("innings_overs", 50)
        second = cards.get(2)
        complete = second and (second["runs"] > cards[1]["runs"] or second["wickets"] == 10 or second["legal_balls"] >= limit*6)
        result = "Replay paused · Synthetic match"
        if complete:
            if second["runs"] > cards[1]["runs"]:
                result = f'{teams[1]} won by {10-second["wickets"]} wickets'
            elif second["runs"] == cards[1]["runs"]:
                result = "Match tied"
            else:
                result = f'{teams[0]} won by {cards[1]["runs"]-second["runs"]} runs'
        elif row["match_id"] == status.get("match_id") and status.get("running"):
            result = "Replay streaming · Synthetic match"
        halves = []
        for innings, team in enumerate(teams, 1):
            card = cards.get(innings)
            score = f'{card["runs"]}/{card["wickets"]}' if card else "—"
            overs = f'({over_text(card["legal_balls"])})' if card else "Yet to bat"
            halves.append(f'<div class="fixtureteam"><div class="fixtureflag">{flag_svg(team)}</div><b>{TEAMS[team][0]}</b><div class="fixturescore">{score} <small>{overs}</small></div></div>')
        with column, st.container(key="matchcard_" + profile, border=True):
            active = "selected" if row["match_id"] == selected else ""
            html(f'<div class="fixture {active}"><div class="fixtureheading"><i class="statusdot {"finished" if complete else ""}"></i>2023 World Cup XI Simulation</div><div class="fixturesub">{limit}-over match · SIMULATED</div><div class="fixtureteams">{halves[0]}<span class="fixturevs">VS</span>{halves[1]}</div><div class="fixturefooter {"finished" if complete else ""}">{escape(result)}</div></div>')
            if st.button("Open " + " vs ".join(teams), key="open_"+profile, use_container_width=True):
                st.session_state["selected_match"] = row["match_id"]
                st.rerun()
    if matches:
        with st.expander("Replay archive"):
            names = {row["match_id"]: " vs ".join(MATCH_PROFILES[row["payload"]["match_profile"]]) + " · " + row["match_id"][-12:] for row in matches}
            archive = st.selectbox("Saved match", list(names), index=list(names).index(selected), format_func=names.get, key="archive_match")
            if st.button("View saved replay"):
                st.session_state["selected_match"] = archive
                st.rerun()


def chart(data, series=False, teams=("India", "Australia")):
    spec = {"height": 160, "background": "transparent", "mark": {"type": "line", "point": True, "strokeWidth": 2},
            "encoding": {"x": {"field": "overs", "type": "quantitative", "title": "Overs", "axis": {"grid": False}},
                         "y": {"field": "runs", "type": "quantitative", "title": "Runs"},
                         "tooltip": [{"field": "overs", "type": "quantitative", "format": ".2f"}, {"field": "runs", "type": "quantitative"}]},
            "config": {"view": {"stroke": None}, "axis": {"labelColor": "#8ba3bd", "titleColor": "#8ba3bd", "gridColor": "#20374c"}}}
    spec["encoding"]["color"] = {"field": "team", "type": "nominal", "scale": {"domain": list(teams), "range": ["#218af5", "#efc841"]}, "legend": {"title": None, "labelColor": "#a9bdd3", "orient": "top"}} if series else {"value": "#218af5"}
    st.vega_lite_chart(data, spec, use_container_width=True)


def batting_rows(innings, rows, full=False, active=False, team="India"):
    roster = TEAMS[team][1]
    selected = sorted([dict(row, sr=f"{row['runs']*100/row['balls']:.1f}" if row['balls'] else "—", dismissal=row['dismissal'] or "not out") for row in rows if row["innings_number"] == innings], key=lambda row: roster.index(row["player"]) if row["player"] in roster else 99)
    if active:
        selected = [row for row in selected if row["dismissal"] == "not out"]
    columns = [("Batter", "player"), ("R", "runs"), ("B", "balls"), ("4s", "fours"), ("6s", "sixes"), ("SR", "sr")]
    table(selected, columns + ([("Dismissal", "dismissal")] if full else []))


def bowling_rows(innings, rows):
    selected = [dict(row, overs=over_text(row["legal_balls"]), econ=f"{row['runs']*6/row['legal_balls']:.2f}" if row["legal_balls"] else "—") for row in rows if row["innings_number"] == innings]
    table(selected, [("Bowler", "player"), ("O", "overs"), ("R", "runs"), ("W", "wickets"), ("Econ", "econ")])


def controls(status, is_current, complete, match, profile):
    with st.container(border=True):
        title("Simulator Controls")
        buttons, speed, faults = st.columns([1.25, 1.25, 1.4])
        with buttons:
            a, b, c = st.columns(3)
            if a.button("▶ Start", type="primary", use_container_width=True):
                if match and not complete:
                    if is_current or command("/select", {"match_id": match}):
                        command("/resume", {})
                else:
                    command("/new", {"overs": 50, "seed": 42, "rate": 2, "profile": profile})
                st.session_state["follow_producer"] = True
                st.rerun()
            if b.button("Ⅱ Pause", use_container_width=True, disabled=not is_current):
                command("/pause", {})
                st.rerun()
            if c.button("↻ Reset", use_container_width=True, help="Start a new match ID; preserve previous scorecards"):
                command("/new", {"overs": 50, "seed": 42, "rate": status.get("rate", 2), "profile": profile})
                st.session_state["follow_producer"] = True
                st.rerun()
        with speed:
            rates = [0.5, 1, 2, 5, 10, 25, 100]
            if "speed" not in st.session_state or st.session_state.get("rate_match") != status.get("match_id"):
                st.session_state["speed"] = min(rates, key=lambda candidate: abs(candidate-status.get("rate", 2)))
                st.session_state["rate_match"] = status.get("match_id")
            rate = st.select_slider("Replay speed · deliveries/sec", options=rates, key="speed",
                                    disabled=not is_current, on_change=lambda: command("/speed", {"rate": st.session_state["speed"]}))
        with faults:
            x, y, z = st.columns(3)
            for column, mode, text in [(x, "duplicate", "Duplicate"), (y, "invalid", "Invalid"), (z, "delay", "Delay")]:
                if column.button(text, use_container_width=True, disabled=not is_current or complete, help="Inject one controlled event fault"):
                    command("/inject", {"mode": mode})
        with st.popover("⚙ Replay settings"):
            limit = st.selectbox("Match length", [50, 20, 5, 2], format_func=lambda value: f"{value} overs per innings" + (" · ODI" if value == 50 else " · short demo"))
            seed = st.number_input("Simulation seed", min_value=0, max_value=1000000, value=42)
            if st.button("Start configured match"):
                command("/new", {"overs": limit, "seed": seed, "rate": rate, "profile": profile})
                st.session_state["follow_producer"] = True
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
            matches = conn.execute("""SELECT m.match_id, first.payload FROM matches m
                JOIN LATERAL (SELECT payload FROM delivery_events d WHERE d.match_id=m.match_id
                ORDER BY innings_number,raw_delivery_sequence LIMIT 1) first ON TRUE
                WHERE first.payload->>'match_profile'=ANY(%s) ORDER BY m.created_at DESC""", (list(MATCH_PROFILES),)).fetchall()
            choices = [row["match_id"] for row in matches]
            if st.session_state.get("selected_match") not in choices:
                st.session_state["selected_match"] = status.get("match_id") if status.get("match_id") in choices else choices[0] if choices else None
            if st.session_state.get("follow_producer") and status.get("match_id") in choices:
                st.session_state["selected_match"] = status["match_id"]
                st.session_state.pop("follow_producer", None)
            match = st.session_state["selected_match"]
            previews = conn.execute("SELECT * FROM innings_scorecard WHERE match_id=ANY(%s)", (choices,)).fetchall()
            match_strip(matches, previews, match, status)
            params = (match,)
            cards = conn.execute("SELECT * FROM innings_scorecard WHERE match_id=%s ORDER BY innings_number", params).fetchall()
            payloads = [row["payload"] for row in conn.execute("SELECT payload FROM delivery_events WHERE match_id=%s ORDER BY innings_number,raw_delivery_sequence", params)]
            batters = conn.execute("SELECT * FROM batting_scorecard WHERE match_id=%s", params).fetchall()
            bowlers = conn.execute("SELECT * FROM bowling_scorecard WHERE match_id=%s", params).fetchall()
            over_rows = conn.execute("SELECT * FROM over_summary WHERE match_id=%s ORDER BY innings_number,over_number", params).fetchall()
    except psycopg.Error:
        st.warning("Score service is unavailable. Accepted scores cannot refresh.")
        return
    profile = payloads[0].get("match_profile", PROFILE) if payloads else PROFILE
    teams = MATCH_PROFILES[profile]
    codes = [TEAMS[team][0] for team in teams]
    limit = payloads[0].get("innings_overs", 50) if payloads else 50
    by_innings = {card["innings_number"]: card for card in cards}
    current = max(by_innings, default=1)
    data = {i: summarize([e for e in payloads if e["innings_number"] == i], limit) for i in (1, 2)}
    current_card = by_innings.get(current, dict(runs=0, wickets=0, legal_balls=0, extras=0))
    is_current = match is not None and match == status.get("match_id")
    complete = is_current and status.get("cursor", 0) == status.get("total", -1) and len(payloads) == status.get("expected_deliveries", status.get("total"))
    terminal = 2 in by_innings and (current_card["runs"] > by_innings[1]["runs"] or current_card["wickets"] == 10 or current_card["legal_balls"] >= limit*6)
    gaps = any(max((e["raw_delivery_sequence"] for e in payloads if e["innings_number"] == i), default=0) != sum(e["innings_number"] == i for e in payloads) for i in (1, 2))
    complete = complete or (terminal and not gaps)
    playing = is_current and status.get("running", False)
    label = "REPLAYING" if playing else "COMPLETED" if complete else "PAUSED" if is_current else "SAVED REPLAY" if match else "READY"
    result = f"{teams[0]} batting · First innings · Synthetic match"
    if 2 in by_innings:
        target = by_innings[1]["runs"] + 1
        result = f"{teams[1]} need {max(0, target-current_card['runs'])} runs · Target {target}"
        if current_card["runs"] >= target:
            result = f"{teams[1]} won by {10-current_card['wickets']} wickets · Simulated result"
        elif complete:
            result = "Match tied · Simulated result" if current_card["runs"] == by_innings[1]["runs"] else f"{teams[0]} won by {by_innings[1]['runs']-current_card['runs']} runs · Simulated result"
    teams_html = []
    for innings, team, code in [(1, teams[0], codes[0]), (2, teams[1], codes[1])]:
        card = by_innings.get(innings)
        score = f"{card['runs']}/{card['wickets']}" if card else "—"
        detail = f"{over_text(card['legal_balls'])} / {limit} overs · RR {card['runs']*6/card['legal_balls']:.2f}" if card and card["legal_balls"] else "Yet to bat" if innings == 2 else "Ready to bat"
        teams_html.append(f'<div class="team"><div class="flag">{flag_svg(team)}</div><div><div class="teamname">{code} · {team.upper()}</div><div class="score">{score}</div><div class="subscore">{detail}</div></div></div>')
    live_tab, score_tab, player_tab, team_tab, analytics_tab, monitor_tab = st.tabs(["Live Match", "Scorecards", "Player Stats", "Team Stats", "Analytics", "Monitoring"])
    with live_tab:
        html(f'<div class="hero"><div class="herotop"><span class="simtag">SIMULATED MATCH</span><span>CRICX MATCH SIMULATOR</span></div><div class="matchtitle">{teams[0]} vs {teams[1]}</div><div class="matchsubtitle">{limit}-over simulation · 2023 ODI World Cup players</div><div class="teams">{teams_html[0]}<div class="vs"><span class="state {"" if playing else "paused"}">{label}</span><br>VS</div>{teams_html[1]}</div><div class="result">{escape(result)}</div></div>')
        controls(status, is_current, complete, match, profile)
        a, b, c, d, e = st.columns([1.35, 1, 1, 1, 1])
        with a: html(f'<div class="tile"><div class="tilelabel">Current Over · {data[current]["current_over"]+1}</div>{balls_html(data[current]["current_balls"])}</div>')
        with b: tile("Runs", f"{current_card['runs']} / {current_card['wickets']}", teams[current-1] + " batting")
        with c: tile("Overs", over_text(current_card["legal_balls"]), f"of {limit} overs")
        rr = current_card["runs"]*6/current_card["legal_balls"] if current_card["legal_balls"] else 0
        with d: tile("Run Rate", f"{rr:.2f}", "runs per over")
        finished_innings = current_card["wickets"] == 10 or current_card["legal_balls"] >= limit*6 or complete
        with e: tile("Final Score" if finished_innings else "At Current Rate", current_card["runs"] if finished_innings else round(rr*limit) if rr else "—", "accepted innings total" if finished_innings else "linear projection · not a prediction")
        if not payloads:
            st.info("Press Start to generate a match through the streaming pipeline.")
        else:
            current_events = [event for event in payloads if event["innings_number"] == current]
            missing = max(event["raw_delivery_sequence"] for event in current_events)-len(current_events)
            if missing: st.warning(f"Provisional score: {missing} delivery sequence(s) pending.")
        left, right = st.columns(2)
        with left, st.container(border=True):
            title("Batters · " + codes[current-1])
            batting_rows(current, batters, active=True, team=teams[current-1])
        with right, st.container(border=True):
            title("Bowlers · " + codes[2-current])
            bowling_rows(current, bowlers)
        left, middle, right = st.columns([1, 1, .85])
        with left, st.container(border=True):
            title("Run Progression")
            chart(data[current]["progress"])
        with middle, st.container(border=True):
            title("Worm Chart · " + " / ".join(codes))
            chart([dict(row, team=teams[innings-1]) for innings in (1, 2) for row in data[innings]["progress"]], True, teams)
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
            html(f'<div class="matchinfo"><b>Format</b><span>{limit}-over simulation</span><b>Players</b><span>Selected 2023 World Cup XIs</span><b>Venue</b><span>Virtual stadium</span><b>Status</b><span>{label}</span><b>Source</b><span>CricX Event Simulator</span><b>Extras</b><span>{current_card["extras"]}</span></div>')
        if cards: st.caption(f"Last accepted score update: {cards[-1]['updated_at']} · Refreshes every 3 seconds")
    render_tabs((score_tab, player_tab, team_tab, analytics_tab, monitor_tab),
                teams, cards, batters, bowlers, payloads, over_rows, data, limit,
                status, match, label, batting_rows, bowling_rows, table, chart)



live()
