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
- Git workspace initially had no commits or remote. No push has been performed.
- Cloud readiness has not been achieved. No cloud account/resources provisioned.

Continue with continuous simulator and controls, full watermark behavior, resource
tuning, monitoring exporters/notifications, sustained burst/partition/outage tests,
and cloud-readiness checks. See experiments/initial_validation.md for evidence.
