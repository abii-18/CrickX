# Engineering changelog

## 2026-10-10

- Established a versioned delivery contract, deterministic fixtures and reference scorer.
- Added a transactional PostgreSQL ledger, correction history, rejection audit and seven serving tables.
- Added separate checkpointed Spark queries for canonical scoring and bounded event-time feed-activity windows. Watermarks do not discard canonical deliveries.
- Validated duplicate/correction replay, transaction rollback, PostgreSQL outage recovery, partition sharing, late-event behavior and a finite burst. Experiment reports record local measurements; no production SLA is claimed.
- Added durable replay controls, six ODI fixtures using selected 2023 World Cup XIs, match-specific dashboard tabs and clickable match cards.
- Added Prometheus/Grafana monitoring and a tested Alertmanager notification route.
- Added public-repository CI, an architecture diagram and reproducible demo evidence.
- Resolved schema loading relative to the source file. Rejection metrics distinguish new audit rows from retries of previously audited Kafka offsets.
- All 18 scoring, simulator, read-model and PostgreSQL tests passed locally.

Cloud deployment is deferred. No cloud resources or paid services have been created.
The current architecture is frozen for learning and interview preparation.

Implementation and documentation were developed with AI assistance. Architectural tradeoffs, verification evidence and known limits remain explicit in the repository.
