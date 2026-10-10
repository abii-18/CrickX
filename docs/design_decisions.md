# Initial decisions

1. Canonical scoring is independent of analytics watermarks. Valid old deliveries
   reach PostgreSQL; bounded windows may omit old events without corrupting scores.
2. Canonical slot: match ID, innings, raw sequence. Revision number distinguishes
   correction from duplicate. Identical slot/revision with different content is rejected.
3. Match-row locking serializes sink changes. Rebuild touched innings inside the
   same transaction as ledger changes. This favors demo correctness over scale.
4. Audit superseded accepted revisions in the ledger's JSON history. Invalid/stale
   revisions go to rejected_events, keyed by Kafka source location for retry safety.
5. New matches preserve history. A repeat of an existing fixture preserves identity.
6. Operational window counts intentionally count feed messages, including revisions
   and duplicates. They must never be interpreted as canonical run totals.
7. No new cloud resources, paid APIs or external AI calls are required by the app.
8. Four shuffle partitions for the two-core demo. The initial 200-partition window
   batch took roughly 69 seconds. Its experimental checkpoint is retained; the
   tuned window query uses a new checkpoint and replays analytics only. Canonical
   checkpoint/database state remain intact. Stateful partition changes must not
   casually reuse incompatible checkpoints.

## Current boundary

The simulator, replay controls, match gallery and private alert route are implemented.
Canonical scoring runs in driver-side Python inside `foreachBatch`; this is a
correctness tradeoff at demo scale, not distributed scoring. The Spark window
query measures feed activity, not cricket business aggregates.

## Spark-native over summaries (2026-10-10)

The isolated enhancement computes the existing over serving rows with Spark
SQL window expressions and `groupBy` sums. Input is the accepted current ledger
snapshot inside the existing transaction, not raw messages. PostgreSQL retains
all duplicate/revision/conflict decisions and row locks. Reusing the original
snapshot SELECT avoids additional database reads; all touched innings share one
aggregation action. Python reference output is the mandatory reconciliation gate,
so a Spark mismatch fails atomically rather than publishing divergent scores.

This deliberately retains the reference scorer and driver-side ledger acceptance.
It provides a verifiable Spark business transformation, not a throughput upgrade
or a full distributed scoring rewrite. Full affected-innings recomputation is
necessary when a correction changes legal-ball counts. No watermark applies to
this stage, and there is no new streaming state, schema, service or checkpoint.
Existing feed-window counts still include duplicate/correction messages and must
not be read as runs. The new `cricx_spark_verified_over_rows_total` counter reports
observed committed, reference-verified rebuild rows; repeated rebuilds count
again and a process restart resets it. Sink errors still use the existing alert.

See [executed checks and limits](../experiments/spark_over_aggregation.md).

Beyond this bounded enhancement, the architecture is frozen while streaming fundamentals are learned. Distributed
business analytics, larger datasets, lake/warehouse services and cloud deployment
are deferred. ARM64 image manifests have been checked; ARM64 runtime behavior has
not been demonstrated. See the changelog and experiment reports for dated evidence.
