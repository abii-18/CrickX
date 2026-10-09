# Initial local validation — October 10, 2026

Environment: Docker Desktop Linux engine, Windows host, roughly 5.8 GiB allocated
to Docker. Single Kafka broker, PostgreSQL 16.8, Spark 3.5.3 in local[2] mode.

## Automated scoring and database tests

Command: `docker compose --profile tools run --rm --build test`

Result: **12 tests passed**. Includes fixed expected totals, wide stumping, leg-byes,
out-of-order/duplicate replay, correction audit, invalid-record retry safety, and
transaction rollback after an injected scorer exception. This rollback test is
not equivalent to an actual PostgreSQL service outage; that experiment is pending.

## Kafka → Spark → PostgreSQL acceptance replay

Command:
`docker compose --profile tools run --rm producer --match-id acceptance-001 --rate 5 --duplicate --correction --invalid`

Observed canonical batch 0: 8 accepted, 8 duplicate, 1 corrected, 1 rejected.
Database: 19 runs, 2 wickets, 6 legal balls, 4 extras. Eight canonical delivery slots.
Hand fixture is 17 runs before replacing a four with a six.

## Repeated replay and Spark restart

Republished the same match fixture with identical flags at rate 20, then ran
`docker compose restart spark` without removing checkpoint/data volumes.

Observed canonical batch 1 after restart: 15 duplicate, 3 rejected. The rejected
records are two stale revision-1 copies of the corrected slot, plus invalid input.
Totals remained **19/2 from 6 legal balls**. This verifies this restart/replay case,
not every crash point or host failure.

## Dashboard and monitoring checks

Streamlit AppTest executed `dashboard/app.py` against the running database.
No exceptions. Rendered metrics: score 19/2, overs 1.0, run rate 19.00, extras 4.
This is a functional rendering check, not visual screenshot QA.

Prometheus API returned `up{job="cricx-spark"}=1` after Spark restart.
Alert notifications, detailed host exporters and full watermark experiments remain pending.

## Startup issues resolved

- Host port 5432 could not bind. Removed PostgreSQL host publication; internal
  container networking is sufficient and avoids interfering with other projects.
- Kafka volume initially root-owned. Added a one-shot ownership initialization
  service, while broker itself continues to run as its non-root image user.
- Producer CLI arguments initially replaced the Docker CMD. Explicit entrypoint
  now preserves the replay executable.

## Limitations

Initial batches took about 12–14 seconds against a 5-second trigger, including
startup work. This is not a throughput benchmark. Resource tuning, window-query
behavior, sustained bursts and outage experiments need separate measurement.

The original default-200-partition analytics batch emitted a count of 17 parseable
feed messages for the first replay and took about 69 seconds. Changed new analytics
query to four partitions with a new checkpoint (`windows-p4`), retaining the
canonical checkpoint. This is an explicit analytics replay, not ordinary recovery.
The tuned query emitted 34 messages across both replays; its first batch took about
15 seconds. Different input volume/startup conditions mean this is observational
evidence, not a controlled performance comparison.
