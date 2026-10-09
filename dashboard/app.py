import os
import psycopg
from psycopg.rows import dict_row
import streamlit as st

st.set_page_config(page_title="CricX", page_icon="🏏", layout="wide")
st.title("🏏 CricX")
st.caption("SIMULATED MATCH · Streaming cricket analytics · Historical fixtures, not a live feed")


def query(sql, params=()):
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        return conn.execute(sql, params).fetchall()


@st.fragment(run_every="5s")
def live():
    try:
        matches = query("SELECT match_id FROM matches ORDER BY created_at DESC")
        if not matches:
            st.info("No accepted deliveries yet. Run the producer replay command in README.")
            return
        match = st.selectbox("Simulated match", [m["match_id"] for m in matches])
        cards = query("SELECT * FROM innings_scorecard WHERE match_id=%s ORDER BY innings_number", (match,))
        for card in cards:
            st.subheader(f"Innings {card['innings_number']}")
            a, b, c, d = st.columns(4)
            a.metric("Score", f"{card['runs']}/{card['wickets']}")
            balls = card["legal_balls"]
            b.metric("Overs", f"{balls // 6}.{balls % 6}")
            c.metric("Run rate", f"{card['runs'] * 6 / balls:.2f}" if balls else "—")
            d.metric("Extras", card["extras"])
            st.caption(f"Last score update: {card['updated_at']} · Missing sequences may make this provisional")
            params = (match, card["innings_number"])
            left, right = st.columns(2)
            left.dataframe(query("SELECT player,runs,balls,fours,sixes,dismissal FROM batting_scorecard WHERE match_id=%s AND innings_number=%s", params), hide_index=True)
            right.dataframe(query("SELECT player,runs,legal_balls,wickets FROM bowling_scorecard WHERE match_id=%s AND innings_number=%s", params), hide_index=True)
            overs = query("SELECT over_number,runs FROM over_summary WHERE match_id=%s AND innings_number=%s ORDER BY over_number", params)
            st.bar_chart(overs, x="over_number", y="runs")
        st.subheader("Recent accepted deliveries")
        st.dataframe(query("SELECT innings_number,raw_delivery_sequence,revision_number,payload->>'batter_runs' AS batter_runs,payload->'extras' AS extras FROM delivery_events WHERE match_id=%s ORDER BY innings_number DESC,raw_delivery_sequence DESC LIMIT 10", (match,)), hide_index=True)
        st.caption("Operational dashboards: Grafana on localhost:3000 · Prometheus on localhost:9090")
    except psycopg.Error:
        st.warning("Database unavailable or schema not initialized. Scores cannot refresh; inspect Spark logs.")


live()
