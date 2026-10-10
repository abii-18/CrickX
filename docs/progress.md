# Build progress

## October 10, 2026

- Created initial Python contract/reference scorer and six independent unit tests.
- Added correction-aware transactional PostgreSQL sink and seven-table schema.
- Added deterministic Kafka replay, two Spark queries, Streamlit scorecard, and
  initial Prometheus/Grafana configurations.
- Twelve scoring/PostgreSQL tests passed in Docker.
- Kafka/Spark acceptance replay produced 19/2 with 6 legal balls and 4 extras.
- Repeated replay plus Spark restart retained 19/2; checkpointed canonical batch
  progressed from 0 to 1. Streamlit functional rendering passed; Prometheus scraped Spark.
- Docker access required sandbox escalation, which was approved.
- Initial milestone pushed to origin/master as f60a0c5.
- Cloud readiness has not been achieved. No cloud account/resources provisioned.

Continue with continuous simulator and controls, full watermark behavior, resource
tuning, monitoring exporters/notifications, sustained burst/partition/outage tests,
and cloud-readiness checks. See experiments/initial_validation.md for evidence.

### Simulator milestone (in progress)

- Added seeded two-innings T20 simulator and dashboard start/pause/resume controls.
- Persisted producer run and acknowledged cursor; restart pauses for explicit resume.
- Added producer acknowledgement/error metrics and Prometheus alert rules.
- Ten Python tests passed, including 20 seeded matches; four database tests require Docker.
- All 14 tests passed in Docker. Full simulator-to-scorecard smoke test passed.
- Dashboard functional rendering and saved simulator state after restart passed.
- PostgreSQL outage/checkpoint recovery passed; see experiments/simulator_validation.md.
- Consumer groups/order, canonical late-event acceptance and finite duplicate burst passed.
- Real processor-down alert routed through Alertmanager to the dashboard; Spark restored.
- Final dashboard AppTest passed; both Prometheus targets healthy.
- All image tags have ARM64 manifests; cloud resource overlay validates.
- User has not created an Oracle account. Cloud deployment remains pending.
- User requested a cricket-first UI matching the v2 document, using 2023 India/Australia XIs.
- Replaced generic teams; added ODI support, reference-style cards/charts and compact fault controls.
- All 16 tests, full ODI reconciliation, injection controls and browser rendering passed.
- No cloud account creation authorized; continue local UI work only.
