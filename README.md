# CricX

Streaming cricket analytics and pipeline reliability. **Simulated data only.**

Python replay → Kafka → PySpark Structured Streaming → PostgreSQL → Streamlit.
Prometheus and Grafana expose processing outcomes, backlog and failures.

## Status

Working local pipeline with seeded simulator and dashboard start/pause/resume controls.
All 14 tests passed, alongside end-to-end simulation, database outage recovery,
consumer-group/order, watermark handling and finite duplicate burst experiments.
See `experiments/initial_validation.md` and `experiments/simulator_validation.md`.
Cloud deployment and visual polish are pending.
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

## Cleanup

`docker compose down` preserves data and checkpoints. Normal recovery uses these.
`docker compose down -v` **deletes this project's local data and checkpoints**;
use only when intentionally discarding the demonstration. It deletes no cloud VM.

## Deployment gate

Before the one-day cloud demo: finish independent fixtures, integration/failure tests,
ARM64 image checks, resource measurements, experiment writeups and clean-checkout
validation. Use verified OCI Always Free resources only, on an unupgraded account.
If free capacity is unavailable, deployment remains pending. No paid fallback.
Capture evidence before deleting VM, volumes and other temporary resources.
See `docs/cloud_demo.md` for current limits, pending checks and the bounded-resource
Compose overlay. Cloud eligibility is not implied by passing local tests.
