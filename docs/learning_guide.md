# Learning guide

## Trace a delivery

1. `producer/replay.py` publishes delivery-level JSON keyed by match ID.
2. Kafka stores the event in one partition. Offset is a source position, not a score.
3. `spark/streaming_job.py` reads micro-batches and passes source keys to the sink.
4. `cricx/events.py` validates the contract; invalid input cannot affect scoring.
5. `cricx/store.py` locks the match, classifies revision, writes the ledger and rebuilds
   affected innings atomically. A failed transaction rolls back every change.
6. `dashboard/app.py` queries PostgreSQL. It never invents totals or pipeline health.

## Predict before experimenting

- Duplicate the fixture: why should neither runs nor legal balls increase?
- Change a four to a six with revision 2: which tables must change together?
- Replay revision 1 afterward: why should the score stay at 19?
- Restart Spark: why is the checkpoint necessary even with an idempotent database?
- Stop PostgreSQL: which offset is safe to call successfully processed?
- Send an old delivery: why can canonical scoring accept it while the window query
  excludes it? What does the analytics watermark actually measure?
- Run one match over three partitions: why can one match remain on only one partition?

## Why rebuild an innings?

Recomputing a short innings is simple and correction-safe. It is not the optimal
approach for millions of events per entity. Explain the scale boundary instead of
claiming that a small fixture proves unlimited throughput.

## Experiments to explain

- `cricx/simulator.py` generates a seeded match; `producer/service.py` stores its
  identity, delivery payloads and acknowledged cursor. Predict the retry if the
  producer dies after Kafka acknowledgement but before saving its cursor.
- `experiments/verify_partitions.py`: explain why two consumers divide three
  partitions and why an independent group gets the same records again. Partition
  ordering does not imply ordering across the whole topic.
- `experiments/verify_watermark.py`: explain the observed one window drop and
  three accepted canonical deliveries. The watermark bounds analytical state;
  it must not remove a correction from the score ledger.
- `experiments/verify_burst.py`: explain why 2,400 messages become 1,200 deliveries,
  what `maxOffsetsPerTrigger=1000` controls, and why 53 seconds in one run does not
  establish a production SLA. Backlog measures pending source records, not lost data.
- `experiments/verify_alert.py`: trace failed scrape → Prometheus rule → Alertmanager
  → private webhook → dashboard notification. An alert endpoint is itself a
  dependency; production monitoring should also work when the product UI is down.
- All containers share one host. A VM failure stops the entire demo. Kafka replication
  factor 1 and Spark local mode demonstrate semantics without demonstrating HA.

Interview practice: draw the two Spark queries and their separate checkpoints.
Explain transaction failure, replay, deduplication, higher revisions, missing
sequences and late window drops without looking at the code. Then reproduce each
experiment and compare what you predicted with the recorded result.
