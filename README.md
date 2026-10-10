# CricX

Streaming cricket analytics and pipeline reliability. **Simulated data only.**

Python replay → Kafka → PySpark Structured Streaming → PostgreSQL → Streamlit.
Prometheus and Grafana expose processing outcomes, backlog and failures.

![Tests](https://github.com/abii-18/CrickX/actions/workflows/tests.yml/badge.svg)

A cricket streaming portfolio project focused on duplicate handling, delivery
corrections, event-time behavior and failure recovery. Uses selected 2023 World
Cup XIs with synthetic outcomes; it is not a live sports feed.

![CricX match gallery and live scorecard](docs/images/dashboard.png)

[Full screenshot gallery](screenshots/README.md) · [Architecture and limits](docs/architecture.md) · [Short demo and evidence](docs/demo.md) ·
[Design decisions](docs/design_decisions.md) · [Learning guide](docs/learning_guide.md) ·
[Engineering changelog](docs/progress.md)

## Status

Working local pipeline with seeded simulator and dashboard start/pause/resume controls.
All 18 tests passed, alongside end-to-end simulation, database outage recovery,
consumer-group/order, watermark handling and finite duplicate burst experiments.
See `experiments/initial_validation.md`, `experiments/simulator_validation.md` and `docs/demo.md`.
The stadium dashboard includes a selectable six-fixture match gallery. Cloud deployment is deferred.
The architecture is frozen for streaming fundamentals and interview preparation.
No paid services or cloud resources have been provisioned.

## Run locally

Docker Desktop must run Linux containers. Copy `.env.example` to `.env` and replace
the two placeholder passwords with URL-safe random values. Do not commit `.env`.

```powershell
docker compose up -d --build
docker compose --profile tools run --rm producer --match-id learning-001 --duplicate --correction --invalid
docker compose logs -f spark
```

Dashboard: http://localhost:8501. Grafana: http://localhost:3000 (user `admin`,
password from `.env`). Prometheus: http://localhost:9090, including active alert rules.
Alertmanager routes firing/resolved notifications to the dashboard's alert panel;
this route stays inside Docker and uses no email or paid monitoring service.
All published ports bind localhost. Cloud access will use an SSH tunnel.

Use **Simulator Controls** on the dashboard to start an India/Australia simulation
using the 2023 ODI World Cup final XIs. Default length is 50 overs; replay settings
also offer 2, 5 or 20-over demos. All outcomes are synthetic, not historical results.
Playing XI names are sourced from the
[ICC final report](https://www.icc-cricket.com/news/awesome-australia-beat-india-to-win-the-icc-mens-cricket-world-cup).
New runs get new match IDs; existing scorecards remain.
The match cards also support India/New Zealand, Australia/South Africa,
England/Pakistan, New Zealand/Australia and India/South Africa. Their selected XIs
use the [confirmed 2023 ICC squads](https://www.icc-cricket.com/media-releases/squads-confirmed-for-icc-mens-cricket-world-cup-2023).
Click a card to view that match's banner, scorecards, players, team statistics and
analytics. Arrow buttons show the next three fixtures; the replay archive retains
older runs. Viewing a card does not switch or start the active producer. Start
resumes an unfinished saved replay, or creates a new run for a finished fixture.
Only one replay publishes at a time; other cards display stored accepted scores.
To populate the five additional fixtures explicitly through Kafka and Spark:

```powershell
docker compose exec dashboard python -m experiments.seed_match_gallery
```

The script reconciles both innings and restores the previous replay paused.
Pause/resume preserves the run. A simulator restart pauses automatically and
retains acknowledged progress in its Docker volume. A crash between Kafka acknowledgement
and cursor persistence can resend a delivery; the canonical ledger deduplicates it.
The private control API is available only within the Docker network.
Synthetic event time advances one second per generated delivery, independently
of replay speed; accelerated replay therefore differs from a wall-clock live feed.

Pure scoring tests need only Python:

```powershell
python -m unittest discover -s tests -v
```

Database integration tests run inside Docker:

```powershell
docker compose --profile tools run --rm --build test
```

The base fixture has **17 runs, 2 wickets, 6 legal balls, 4 extras**. Its correction
changes a four to a six: **19 runs**. Replaying it must not inflate totals.

## Correctness and limitations

- A slot is `(match_id, innings_number, raw_delivery_sequence)`; wides/no-balls get
  their own raw sequence. Each revision has a unique event ID.
- Higher revisions replace canonical events and rebuild the innings in one DB
  transaction. Previous payloads remain in `revision_history`. Stale/conflicting
  revisions and invalid records are audited in `rejected_events`.
- New match means new match ID. Explicitly replaying an existing ID retains its
  fixture timestamps and identities. No destructive UI reset is implemented.
- Canonical scoring accepts valid old events independently of watermark analytics.
  The separate 10-second/30-second-watermark windows count received parseable events,
  including duplicates/revisions; they are feed activity metrics, not unique runs.
- Spark retries may replay database effects. Transactions and ledger checks provide
  retry safety; this is not a blanket end-to-end exactly-once claim.
- Bowler figures exclude byes/leg-byes; no-balls count as batter balls faced, wides
  do not. Supported dismissals are listed in `cricx/events.py`. Penalty runs,
  retired batters, DLS and full cricket-law validation are outside this version.
  The simulator prevents bowled dismissals on free hits; arbitrary input events
  are not validated against complete innings/free-hit state. Maidens are omitted.
  Partnerships and fall-of-wicket cards derive from canonical event sequences.
- Out-of-order gaps produce provisional scores; the dashboard shows a missing
  sequence warning. Simulator tests check dismissal/innings/chase invariants,
  but the scorer does not enforce complete cricket-law or strike-state validation.
- One broker, replication factor 1, Spark `local[2]`: no host failover or multi-node
  scalability. Innings rebuilds are appropriate for small demos, not unlimited scale.
- Metrics count observed commit outcomes; replay/restarts can affect counter totals.
  Backlog is based on successful Spark progress, not consumer-group commits.
  Rejections count new audit rows; `rejection_replayed` counts retried source keys
  already present in the audit table.

## Cleanup

`docker compose down` preserves data and checkpoints. Normal recovery uses these.
`docker compose down -v` **deletes this project's local data and checkpoints**;
use only when intentionally discarding the demonstration. It deletes no cloud VM.

## CI and cost

GitHub Actions runs pure-Python tests and a separate PostgreSQL 16 integration job
on pushes and pull requests. It does not start Kafka or Spark, deploy anything,
upload artifacts or enable dependency caches. Both jobs have ten-minute limits.
Jobs run only when the repository is public. Standard hosted runners in public
repositories are [free under GitHub's documented policy](https://docs.github.com/en/actions/concepts/billing-and-usage).
Making this repository private disables these jobs until explicitly reconfigured.

Cloud deployment is deferred. Current verification is on local Docker, so a
cloud-hosted demo remains unfulfilled. The previous cloud plan is retained in
`docs/cloud_demo.md` as unexecuted planning, not as deployment evidence.

## Development and attribution

This project was developed with substantial AI assistance for implementation,
documentation and test execution. Test results show behavior for the recorded
cases; they do not demonstrate the owner's interview readiness or independent
authorship. The learning guide provides questions to explain and defend the design.
