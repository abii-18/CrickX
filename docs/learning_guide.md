# Learn from the initial pipeline

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

## Important tradeoff

Recomputing a short innings is simple and correction-safe. It is not the optimal
approach for millions of events per entity. Explain the scale boundary instead of
claiming that a small fixture proves unlimited throughput.
