"""Read-only presentation of canonical match data and actual pipeline telemetry."""
import json
from html import escape
from urllib.request import urlopen
from urllib.error import URLError
import streamlit as st
from prometheus_client.parser import text_string_to_metric_families
from cricx.teams import TEAMS
from dashboard.flags import flag_svg
from dashboard.models import over_text

COLORS = ["#38a5ff", "#efc84b"]


def html(value):
    st.markdown(value, unsafe_allow_html=True)


def heading(kicker, name, description):
    html(f'<div class="sectionhero"><div class="eyebrow">{escape(kicker)}</div>'
         f'<h2>{escape(name)}</h2><p>{escape(description)}</p></div>')


def empty(name="Innings yet to begin", detail="Statistics appear as deliveries are accepted."):
    html(f'<div class="visualempty"><span>◌</span><b>{escape(name)}</b><p>{escape(detail)}</p></div>')


def kpis(values):
    for col, (label, value, note) in zip(st.columns(len(values)), values):
        with col:
            html(f'<div class="statcard"><div>{escape(label)}</div><strong>{escape(str(value))}</strong><small>{escape(str(note))}</small></div>')


def bars(rows, x, y, teams, title, horizontal=False, height=240):
    st.markdown(f"**{title}**")
    if not rows:
        empty("No recorded deliveries")
        return
    quantitative = {"field": x, "type": "quantitative", "title": None}
    category = {"field": y, "type": "nominal", "title": None, "sort": "-x" if horizontal else None}
    encoding = {"x": quantitative if horizontal else category,
                "y": category if horizontal else quantitative,
                "color": {"field": "team", "type": "nominal", "scale": {"domain": list(teams), "range": COLORS},
                          "legend": {"title": None, "orient": "top", "labelColor": "#b2c6de"}},
                "tooltip": [{"field": y}, {"field": x}, {"field": "team"}]}
    if not horizontal:
        encoding["xOffset"] = {"field": "team"}
    st.vega_lite_chart(rows, {"height": height, "background": "transparent",
                            "mark": {"type": "bar", "cornerRadiusEnd": 4}, "encoding": encoding,
                            "config": {"view": {"stroke": None}, "axis": {"labelColor": "#a4bad2", "gridColor": "#20374c", "domain": False, "ticks": False}}}, use_container_width=True)


def leader(label, row, kind, team):
    if not row:
        empty("No " + kind + " figures yet")
        return
    name = row["player"]
    initials = "".join(p[0] for p in name.split()[:2])
    value = f'{row["runs"]} runs' if kind == "batting" else f'{row["wickets"]} wickets'
    detail = f'{row["balls"]} balls · {row["fours"]} fours · {row["sixes"]} sixes' if kind == "batting" else f'{over_text(row["legal_balls"])} overs · {row["runs"]} runs conceded'
    html(f'<div class="leadercard"><div class="eyebrow">{escape(label)}</div><div class="leaderbody"><div class="avatar">{escape(initials)}</div><div><b>{escape(name)}</b><small>{escape(team)}</small></div><strong>{escape(value)}</strong></div><p>{escape(detail)}</p></div>')


@st.cache_data(ttl=5, show_spinner=False)
def telemetry():
    result = {"targets": [], "metrics": {}, "errors": []}
    try:
        with urlopen("http://prometheus:9090/api/v1/targets", timeout=2) as response:
            result["targets"] = json.load(response)["data"]["activeTargets"]
    except (URLError, TimeoutError, ValueError, KeyError, OSError):
        result["errors"].append("Prometheus target status unavailable")
    try:
        with urlopen("http://spark:9101/metrics", timeout=2) as response:
            for family in text_string_to_metric_families(response.read().decode()):
                for sample in family.samples:
                    if sample.name.startswith("cricx_"):
                        result["metrics"][sample.name] = result["metrics"].get(sample.name, 0) + sample.value
    except (URLError, TimeoutError, ValueError, OSError):
        result["errors"].append("Spark metrics unavailable")
    return result


def render_tabs(tabs, teams, cards, batters, bowlers, payloads, over_rows, data,
                limit, status, match, label, batting_rows, bowling_rows, table, chart):
    score_tab, player_tab, team_tab, analytics_tab, monitor_tab = tabs
    by_innings = {c["innings_number"]: c for c in cards}
    with score_tab:
        heading("MATCH CENTRE / SCORECARDS", "Every innings. Every contribution.", "Batting and bowling figures from accepted deliveries.")
        for inn, team in enumerate(teams, 1):
            card = by_innings.get(inn)
            score = f'{card["runs"]}<small> / {card["wickets"]}</small>' if card else "—"
            detail = f'{over_text(card["legal_balls"])} overs · {card["extras"]} extras' if card else "Yet to bat"
            html(f'<div class="inningsbanner" style="--accent:{COLORS[inn-1]}"><div class="bannerflag">{flag_svg(team)}</div><div><div class="eyebrow">INNINGS {inn}</div><h3>{escape(team)}</h3><p>{escape(detail)}</p></div><div class="bannerscore">{score}</div></div>')
            if not card:
                empty("Waiting for " + team, "This innings will appear here when its first delivery is accepted.")
                continue
            boundary_runs = sum(r["fours"]*4 + r["sixes"]*6 for r in batters if r["innings_number"] == inn)
            kpis([("Run rate", f'{card["runs"]*6/card["legal_balls"]:.2f}' if card["legal_balls"] else "—", "runs per over"),
                  ("Boundary runs", boundary_runs, "fours + sixes"), ("Extras", card["extras"], "included in total")])
            a, b = st.columns([1.2, 1])
            with a, st.container(border=True):
                st.markdown("**Batting · " + team + "**")
                batting_rows(inn, batters, True, team=team)
            with b, st.container(border=True):
                st.markdown("**Bowling · " + teams[2-inn] + "**")
                bowling_rows(inn, bowlers)
            with st.expander("Innings timeline · phases and wickets"):
                a, b = st.columns(2)
                with a: table(data[inn]["phases"], [("Phase", "Phase"), ("Overs", "Overs"), ("Runs", "Runs"), ("W", "Wickets")])
                with b: table(data[inn]["wickets"], [("#", "#"), ("Score", "Score"), ("Over", "Over"), ("Player", "Player")])
    with player_tab:
        heading("PERFORMANCE / PLAYERS", "The players behind the score.", "Match-only leaderboards · synthetic simulation, not career statistics.")
        a, b = st.columns(2)
        best_bat = max(batters, key=lambda r: r["runs"], default=None)
        best_bowl = max(bowlers, key=lambda r: (r["wickets"], -r["runs"]), default=None)
        with a: leader("LEADING RUN SCORER", best_bat, "batting", teams[best_bat["innings_number"]-1] if best_bat else "")
        with b: leader("LEADING WICKET TAKER", best_bowl, "bowling", teams[2-best_bowl["innings_number"]] if best_bowl else "")
        a, b = st.columns(2)
        with a, st.container(border=True):
            bars([dict(r, team=teams[r["innings_number"]-1]) for r in sorted(batters, key=lambda r: r["runs"], reverse=True)[:8]], "runs", "player", teams, "Batting leaderboard", True)
        with b, st.container(border=True):
            bars([dict(r, team=teams[2-r["innings_number"]]) for r in sorted(bowlers, key=lambda r: r["wickets"], reverse=True)[:8]], "wickets", "player", teams, "Bowling leaderboard", True)
        with st.expander("Full batting figures and selected XIs"):
            for inn, team in enumerate(teams, 1):
                st.markdown("**" + team + "**")
                batting_rows(inn, batters, True, team=team)
                st.caption("Selected XI · " + " · ".join(TEAMS[team][1]))
    with team_tab:
        heading("HEAD TO HEAD / TEAMS", "Two teams. One match story.", "Compare accepted innings totals; incomplete innings are not equal-length comparisons.")
        a, b = st.columns(2)
        for col, inn, team in zip((a, b), (1, 2), teams):
            with col:
                card = by_innings.get(inn)
                html(f'<div class="teamidentity"><div class="bannerflag">{flag_svg(team)}</div><b>{escape(team)}</b><span>INNINGS {inn}</span></div>')
                if card:
                    kpis([("Score", f'{card["runs"]}/{card["wickets"]}', over_text(card["legal_balls"]) + " overs"), ("Run rate", f'{card["runs"]*6/card["legal_balls"]:.2f}' if card["legal_balls"] else "—", "runs per over")])
                else: empty("Yet to bat")
        rows = []
        for card in cards:
            inn = card["innings_number"]
            boundary = sum(r["fours"]*4 + r["sixes"]*6 for r in batters if r["innings_number"] == inn)
            rows.extend({"team": teams[inn-1], "source": source, "runs": value} for source, value in (("Boundaries", boundary), ("Other bat runs", card["runs"]-card["extras"]-boundary), ("Extras", card["extras"])))
        with st.container(border=True): bars(rows, "runs", "source", teams, "Where the runs came from")
        with st.container(border=True):
            table([dict(c, team=teams[c["innings_number"]-1], overs=over_text(c["legal_balls"])) for c in cards], [("Team", "team"), ("Runs", "runs"), ("Wickets", "wickets"), ("Overs", "overs"), ("Extras", "extras")])
    with analytics_tab:
        heading("MATCH INSIGHTS / ANALYTICS", "Read the rhythm of the innings.", "Over-by-over pressure, scoring progression and wicket milestones.")
        legal = [e for e in payloads if not e["extras"]["wides"] and not e["extras"]["no_balls"]]
        dots = sum(e["batter_runs"] + sum(e["extras"].values()) == 0 for e in legal)
        boundaries = sum(r["fours"] + r["sixes"] for r in batters)
        best_over = max(over_rows, key=lambda r: r["runs"], default=None)
        kpis([("Boundaries", boundaries, "fours + sixes · both innings"),
              ("Dot-ball share", f'{dots*100/len(legal):.1f}%' if legal else "—", "zero-run legal deliveries · both innings"),
              ("Highest scoring over", best_over["runs"] if best_over else "—", f'{teams[best_over["innings_number"]-1]} · over {best_over["over_number"]+1}' if best_over else "no recorded overs")])
        with st.container(border=True):
            bars([dict(r, over=str(r["over_number"]+1), team=teams[r["innings_number"]-1]) for r in over_rows], "runs", "over", teams, "Runs per over", height=260)
        a, b = st.columns(2)
        with a, st.container(border=True):
            st.markdown("**Cumulative run progression**")
            chart([dict(row, team=teams[inn-1]) for inn in (1, 2) if inn in by_innings for row in data[inn]["progress"]], True, teams)
        with b, st.container(border=True):
            phase_rows = [dict(r, team=teams[inn-1]) for inn in (1, 2) for r in data[inn]["phases"]]
            bars(phase_rows, "Runs", "Phase", teams, "Scoring by innings phase", height=160)
        for inn, team in enumerate(teams, 1):
            with st.container(border=True):
                st.markdown("**" + team + " · Wicket timeline**")
                wickets = data[inn]["wickets"]
                if not wickets: empty("No wickets recorded", "Wicket milestones appear as dismissals are accepted.")
                else:
                    html('<div class="wicketrail">' + ''.join(f'<div class="wicketstop"><span>W{w["#"]}</span><b>{w["Score"]}</b><small>{escape(w["Player"])}</small><em>Over {escape(w["Over"])}</em></div>' for w in wickets) + '</div>')
        st.caption("Canonical accepted deliveries only. Corrections update charts; partial overs are included.")
    with monitor_tab:
        heading("OPERATIONS / STREAM HEALTH", "Follow the pipeline, not just the score.", "Live scrape status and processor metrics · match context is shown separately.")
        observed = telemetry()
        targets = {t["labels"]["job"]: t for t in observed["targets"]}
        stages = []
        for name, job, note in (("Producer", "cricx-producer", "delivery publishing"), ("Spark", "cricx-spark", "canonical processing")):
            target = targets.get(job)
            health = target.get("health", "unknown") if target else "unknown"
            stages.append(f'<div class="healthstage {health}"><i></i><b>{name}</b><span>{health.upper()}</span><small>{note}</small></div>')
        html('<div class="healthflow">' + ''.join(stages) + '</div>')
        metrics = observed["metrics"]
        def metric(name, decimals=0):
            value = metrics.get(name)
            return f'{value:,.{decimals}f}' if value is not None else "—"
        kpis([("Kafka backlog", metric("cricx_spark_backlog_records"), "records · all partitions"),
              ("Last batch", metric("cricx_batch_duration_seconds", 2) + " s" if "cricx_batch_duration_seconds" in metrics else "—", "canonical sink duration"),
              ("Sink errors", metric("cricx_sink_errors_total"), "since processor start"),
              ("Verified over rows", metric("cricx_spark_verified_over_rows_total"), "committed rebuilds · since start")])
        for warning in observed["errors"]: st.warning(warning)
        a, b = st.columns(2)
        with a, st.container(border=True):
            st.markdown("**Selected match**")
            kpis([("Accepted deliveries", len(payloads), "canonical ledger"), ("Replay state", label, "selected match")])
            st.caption(match or "No match selected")
        with b, st.container(border=True):
            st.markdown("**Active producer**")
            cursor, total = status.get("cursor"), status.get("total")
            if isinstance(cursor, int) and isinstance(total, int) and total > 0:
                st.progress(min(1.0, max(0.0, cursor/total)))
                st.caption(f"{cursor:,} / {total:,} messages acknowledged · active replay only")
            else: empty("Producer progress unavailable")
            if status.get("error"): st.error(f'Producer error: {status["error"]}')
        a, b = st.columns(2)
        with a: st.link_button("↗ Open Grafana pipeline dashboard", "http://localhost:3000/d/cricx/cricx-pipeline", use_container_width=True)
        with b: st.link_button("↗ Open Prometheus alerts", "http://localhost:9090/alerts", use_container_width=True)
        with st.container(border=True):
            st.markdown("**Alert activity**")
            alerts = list(reversed(status.get("alerts", [])))[:12]
            if not alerts: empty("No received alert notifications", "This is notification history, not a current-health assertion.")
            for alert in alerts:
                state = alert.get("status", "unknown")
                html(f'<div class="alertrow"><span class="alertpill {escape(state, quote=True)}">{escape(state.upper())}</span><div><b>{escape(alert.get("name", "Unknown alert"))}</b><small>{escape(alert.get("summary", ""))}</small></div><time>{escape(alert.get("received_at", ""))}</time></div>')
        st.caption("Telemetry refreshes every 5 seconds. Unknown means unavailable; historical alerts may already be resolved.")
