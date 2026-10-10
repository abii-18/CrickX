# CricX

A ball-by-ball cricket simulator using selected 2023 World Cup XIs.
**All match outcomes are simulated.**

Python replay → Kafka → PySpark Structured Streaming → PostgreSQL → Streamlit.
Prometheus and Grafana track processing outcomes, backlog and failures.

![Tests](https://github.com/abii-18/CrickX/actions/workflows/tests.yml/badge.svg)

The pipeline handles late deliveries, duplicates, corrections and replay after
a failure. PostgreSQL stores the accepted deliveries and scorecards.

![CricX match gallery and live scorecard](docs/images/dashboard.png)

[Full screenshot gallery](screenshots/README.md) · [Architecture and limits](docs/architecture.md) · [Short demo and evidence](docs/demo.md) ·
[Design decisions](docs/design_decisions.md) · [Learning guide](docs/learning_guide.md) ·
[Engineering changelog](docs/progress.md) · [Spark aggregation validation report](experiments/spark_over_aggregation.md)

## Status

The pipeline runs in Docker. You can choose from six match fixtures and start,
pause or resume a replay from the dashboard.

There are **27 tests**: 17 Python/producer tests, 6 PostgreSQL tests and 4 Spark
tests. The latest Docker run passed **23 tests**. The 4 Spark tests passed in a
separate run and are not included in CI. See the
[Spark test report](experiments/spark_over_aggregation.md) for the results.

Earlier replay, outage, ordering, watermark and burst checks are recorded in
[initial validation](experiments/initial_validation.md),
[simulator validation](experiments/simulator_validation.md) and [the demo report](docs/demo.md).

Cloud deployment is still pending. The current setup uses no paid services.

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

To run the Python tests, install the two dependencies below. These tests do not
need a running Kafka broker. Database and Spark tests are skipped in this run:

```powershell
python -m pip install 'kafka-python==2.1.2' 'prometheus-client==0.21.1'
python -m unittest discover -s tests -v
```

Database integration tests run inside Docker:

```powershell
docker compose --profile tools run --rm --build test
```

Run the four Spark tests separately in the existing Spark image:

```powershell
docker compose build spark
docker compose run --rm --no-deps spark /opt/spark/bin/spark-submit --master local[2] --driver-memory 512m tests/run_spark_tests.py
```

Start PostgreSQL before running the Spark tests. The
[Spark report](experiments/spark_over_aggregation.md) also covers the Kafka replay
and restart checks.

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

GitHub Actions runs the Python and PostgreSQL tests on each push and pull request.
The Python job includes the producer concurrency tests. Neither job starts Kafka
or Spark. Both have a ten-minute timeout.
Jobs run only when the repository is public. Standard hosted runners in public
repositories are [free under GitHub's documented policy](https://docs.github.com/en/actions/concepts/billing-and-usage).
Making this repository private disables these jobs until explicitly reconfigured.
The four Spark tests currently run through Docker, not CI.

The project has only been tested in local Docker. The cloud demo is still planned;
`docs/cloud_demo.md` describes the proposed setup.

## AI assistance

AI tools helped with the code, documentation and testing. The
[learning guide](docs/learning_guide.md) covers the design choices and questions
to work through when learning the project.
