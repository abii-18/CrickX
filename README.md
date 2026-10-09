# CricX

Streaming cricket analytics and pipeline reliability. **Simulated data only.**

Python replay → Kafka → PySpark Structured Streaming → PostgreSQL → Streamlit.
Prometheus and Grafana expose processing outcomes, backlog and failures.

## Status

Initial working pipeline. Twelve scoring/database tests and the acceptance replay
passed; duplicate replay plus Spark restart retained correct totals. See
`experiments/initial_validation.md`. Full simulator, remaining failure experiments,
visual polish and cloud deployment are pending.
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
All published ports bind localhost. Cloud access will use an SSH tunnel.

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
  free-hit restrictions, retired batters, DLS and full cricket-law validation are
  outside this initial version. Maidens/partnership charts are not implemented.
- Out-of-order gaps produce provisional scores; full sequence-completeness and
  simulator cricket-state validation are still pending.
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
