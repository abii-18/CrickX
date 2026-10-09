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

## Remaining work

Continuous cricket-valid simulator; start/pause controls; completion/gap state;
persisted match time origin; producer and host exporters; alert notification routing;
full supported-scoring fixtures; automated container recovery/outage tests; ARM64
verification; one-day cloud demonstration and evidence. No result is claimed before
it is run and recorded.
