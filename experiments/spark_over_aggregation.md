# Spark-native over summaries — executed 2026-10-10

## Before and after

Before: Kafka DataFrame -> driver `toLocalIterator()` -> Python validation and
revision decisions -> PostgreSQL current ledger -> Python scorer -> all serving
rows in one transaction. Spark's other query only counted feed messages.

After: acceptance and the reference scorer remain intact. The same transactional
ledger snapshot additionally enters a finite Spark DataFrame. A partitioned,
raw-sequence-ordered prefix window computes preceding legal balls, followed by
`floor(legal_before / 6)` and match/innings/over `groupBy` sums for runs, wickets
and legal balls. Verified Spark rows supply the existing `over_summary` table.
Exact reference agreement is required before commit. This uses the existing schema, services and checkpoints, without Python UDFs.

Spark aggregates the accepted ledger snapshot, not raw Kafka messages.
Acceptance removes identical duplicates, replaces slots with higher revisions,
and audits stale/conflicting revisions before Spark sees a snapshot. A legality
correction rebuilds all overs in its innings. Raw sequence determines ordering;
old event timestamps do not prevent canonical rebuilds. The unrelated analytics
watermark can still drop those messages from feed counts.

## Validation results

| Check | Observed result |
| --- | --- |
| Host pure-Python discovery | 13 passed; 6 PostgreSQL and 4 Spark tests skipped because not enabled there |
| Docker `test` discovery | 19 passed (13 pure + 6 PostgreSQL); 4 Spark tests explicitly skipped |
| Real Spark 3.5.3 runner | All 4 passed, including Spark + PostgreSQL revision reconciliation |
| Same over, multiple overs, innings/matches, reversed input, empty frame | Spark agrees with hand totals and reference scorer |
| Duplicate, legality-changing correction, stale/conflicting revision, malformed message | Only accepted current slots reach Spark; reference agreement and audit/history checks passed |
| Injected Spark exception / intentionally wrong output | PostgreSQL test confirmed prior totals/history remain intact and new audit writes roll back |
| Docker rebuild | Spark and test images rebuilt successfully; Spark service recreated with existing volumes |
| Kafka end-to-end replay | 36 messages -> 16 canonical deliveries, 1 accepted correction, 16 duplicates, 3 rejections; all four serving tables match reference |
| Spark stop / queued correction + duplicate / restart | Existing checkpoint resumed; innings 1 changed 23 -> 25 runs, with 14 legal balls and 3 extras; duplicate added nothing |
| Checkpoints and state | Existing `canonical`, `windows-p4` used; historical `windows` retained. Recovered analytics reported 4 state/shuffle partitions |
| Dashboard | All 6 tabs rendered in headless installed Edge without a Streamlit exception; replay script separately verified dashboard run-progression totals |
| Existing watermark experiment | `late-178f5a005ee5`: 3 canonical deliveries, score 6/0, 2 legal balls, 1 extra; analytics dropped 1 late message |
| Existing duplicate burst experiment | 2400 messages -> 1200 deliveries / 150 correct scorecards; observed catch-up 27.80 seconds, sampled backlog peak 2400 |
| Actual processor-down alert | New firing notification received 11:12:42 UTC; resolved notification 11:13:32 UTC; both Prometheus scrape targets subsequently up |

The burst timing is a single local observation, not a benchmark or improvement
claim. Existing experiment reports are retained; their historical timings were
not overwritten. Partition-sharing, simulator injection-control and database-down
end-to-end experiments were not rerun in this change. Database transaction rollback
was exercised by integration tests. No cloud execution was performed.

End-to-end match: `spark-e2e-20261010-1112`. After recovery, committed over rows
`(innings, over, runs, wickets, legal_balls)` were:

```text
(1, 0, 18, 1, 6)
(1, 1,  5, 1, 6)
(1, 2,  2, 0, 2)
(2, 0,  1, 0, 1)
```

## Reproduce in PowerShell

Use an already configured `.env` and running Docker Desktop. Preserve volumes.
The tests use unique match IDs and delete their own PostgreSQL rows. The end-to-end
replay deliberately retains its fixture for inspection; use a fresh ID each run.

```powershell
docker compose build spark test dashboard
docker compose up -d
docker compose run --rm test
docker compose run --rm --no-deps spark /opt/spark/bin/spark-submit --master local[2] --driver-memory 512m tests/run_spark_tests.py

$replayMatch = "spark-e2e-" + [guid]::NewGuid().ToString("N").Substring(0,12)
docker compose exec -T dashboard python experiments/verify_spark_overs.py --match $replayMatch --action publish
docker compose stop spark
docker compose exec -T dashboard python experiments/verify_spark_overs.py --match $replayMatch --action queue-recovery
docker compose start spark
docker compose exec -T dashboard python experiments/verify_spark_overs.py --match $replayMatch --action verify-recovery
docker compose logs --tail 30 spark

# Optional existing experiments; watermark test advances global analytics event time.
docker compose exec -T dashboard python experiments/verify_watermark.py
docker compose exec -T dashboard python experiments/verify_burst.py
```

Dashboard: `http://localhost:8501`; Prometheus: `http://localhost:9090`.
The new metric is `cricx_spark_verified_over_rows_total`; it counts observed
committed rebuild output rows, not distinct deliveries/overs. It resets on restart.
Existing sink-error and processor-down alerts still cover failures of this stage.

## Limitations

This does not remove driver-side Kafka batching, ledger acceptance, Python
reference scoring or serial SQL writes. The source batch is capped at 1000 offsets,
but snapshots include full touched-innings histories and thus can be larger.
Only aggregate output is collected from Spark for reconciliation; creating its
input still starts from the driver-read canonical ledger. There is no distributed
database read or write, and Spark runs on `local[2]`.

Spark sorting/shuffles and the reference comparison add work while database locks
are held. Old committed rows remain valid and are recalculated with Spark only
when a new accepted event touches that innings. Sequence gaps remain provisional;
full cricket-law enforcement has not been added. This preserves retry-safe
transaction effects, not end-to-end exactly-once processing. Snapshot memory, SQL round trips and lock duration still need measurement.
