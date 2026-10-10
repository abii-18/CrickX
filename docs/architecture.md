# Architecture and interview explanation

```mermaid
flowchart TB
    Sim["Python simulator / deterministic replay"] -->|"delivery JSON, match_id key"| Kafka["Kafka: match-events, 3 partitions"]
    State[("Producer state: IDs and acknowledged cursor")] --- Sim
    Kafka --> Canon["Spark query 1: canonical foreachBatch"]
    Kafka --> Windows["Spark query 2: event-time feed windows"]
    Canon --- CP1[("Canonical checkpoint / Kafka offsets")]
    Canon --> Driver["Driver-side Python validation and scoring"]
    Driver --> Tx["One PostgreSQL transaction per batch"]
    Tx --> Ledger[("Canonical slots and revision history")]
    Tx --> Audit[("Retry-safe rejection audit")]
    Tx --> Serving[("Innings, overs, batting, bowling tables")]
    Serving --> UI["Streamlit: match-specific dashboard"]
    UI -->|"Private HTTP replay controls"| Sim
    Windows --- CP2[("Separate windows-p4 checkpoint / state")]
    Windows --> Counts["10-second counts / 30-second watermark"]
    Counts -->|"Feed activity, including duplicate messages"| Prom["Prometheus"]
    Canon -->|"Commits, errors, duration, backlog"| Prom
    Sim -->|"Acknowledgements, errors, active state"| Prom
    Prom --> Grafana["Grafana pipeline dashboard"]
    Prom --> Alerts["Alertmanager"]
    Alerts -->|"Private webhook"| Sim
    Sim -->|"Received alert notifications"| UI
```

## Two queries, two meanings

**Canonical query:** valid events reach the PostgreSQL ledger even when old.
A slot is `(match_id, innings_number, raw_delivery_sequence)`. Identical deliveries
are skipped; higher revisions replace the current payload and preserve history;
stale or conflicting revisions are audited. Touched innings are rebuilt inside
the same transaction. The scoreboard reads these committed tables.

**Window query:** Spark groups parsed feed messages by event time and match.
It counts messages, including duplicates and revisions. Its watermark bounds
state and can discard late records. Counts are operational metrics, not unique
runs or score totals. It has no durable business-analytics sink.

## What recovery guarantees

Spark checkpoints track source progress, separately for each query. A failed
PostgreSQL transaction rolls back ledger and serving changes together. Retrying
a batch checks existing slots and audit source keys. A crash after commit but
before checkpoint progress can cause replay, which the sink tolerates. This is
idempotent database effect handling, not an end-to-end exactly-once claim.

Producer cursor persistence can also resend an acknowledged event after a crash.
Restart pauses the simulator for explicit resume. Checkpoints, database data and
producer state live in Docker volumes; deleting those volumes changes recovery.

## Limits and what would change at 100 times the load

| Current limit | Change to investigate after learning the current design |
| --- | --- |
| Scoring gathers each batch on the Spark driver | Define correction-aware distributed business aggregates and compare their results with the reference scorer |
| Per-event SQL and full touched-innings rebuild | Measure query/lock costs; batch ledger lookups and writes before changing the transaction model |
| One Kafka broker, Spark `local[2]`, one PostgreSQL instance | Design replication, distributed compute and database availability; this demo has no host failover |
| Synthetic finite inputs and global event-time watermark | Use an isolated, licensed replay with controlled disorder and timestamps; measure state, skew and backlog |
| A Prometheus label per match, including past matches | Bound metric cardinality or move match history to a durable analytics store |

These are proposed investigations, not implemented scaling claims. No new stack,
warehouse or cloud deployment is required for the present learning milestone.
