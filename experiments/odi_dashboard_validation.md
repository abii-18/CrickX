# ODI dashboard validation — October 10, 2026

This report records the first dashboard revision based on the v2 specification: match banner, compact
controls, current-over markers, score/overs/rate cards, batting/bowling tables,
progression/worm charts, partnership, innings phases and fall-of-wicket panels.
At this stage, the stadium background was a CSS illustration.

India/Australia names use the 2023 final XIs, verified against the
[ICC report](https://www.icc-cricket.com/news/awesome-australia-beat-india-to-win-the-icc-mens-cricket-world-cup).
The current synthetic generator starts India batting and supports 50-over innings,
five rotating bowlers capped at ten overs, strike changes, wickets, extras, and
restricted free-hit dismissals. It is not a historical ball-by-ball reconstruction.

Observed checks:

- 16 unit/database tests passed, including hand-calculated chart/partnership/wicket
  fixtures and ODI player/bowling-limit invariants.
- Complete seed-42 ODI: 504 accepted deliveries; India 291/10 in 42.4 overs,
  Australia 259/10 in 36.3 overs. All serving scorecards reconciled.
- Injection controls: duplicate, invalid and reordered deliveries generated
  19 messages, 17 canonical deliveries, one invalid rejection, and unchanged
  short-match scorecards (India 14/0, Australia 15/0).
- Streamlit AppTest passed. Headless Edge captured the actual rendered local UI;
  unreadable light-theme controls were corrected by an explicit dark configuration.
- Canonical reads use a repeatable-read snapshot, so banner, cards and charts are
  consistent with each other within each refresh. Provisional gaps are indicated.
- Final browser Start/Pause checks passed; Streamlit reported no widget warnings
  or exceptions. An in-progress preview was paused at 105/5 after 17 overs before
  the browser control test resumed and paused it again.

Validation was performed on the local Docker Compose deployment.
