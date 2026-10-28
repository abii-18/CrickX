# Deployment

CrickX is deployed with Docker Compose. The stack runs the Python simulator,
Kafka, PySpark Structured Streaming, PostgreSQL, Streamlit, and monitoring.
Validation results in this repository were captured from the local Docker stack.

## Start

Copy `.env.example` to `.env` and replace both placeholder passwords with
URL-safe random values. Keep `.env` private.

```sh
docker compose up -d --build
docker compose --profile tools run --rm --build test
docker compose exec -T dashboard python tests/verify_simulator.py
```

Open the dashboard at `http://localhost:8501`. Grafana and Prometheus are available
at `http://localhost:3000` and `http://localhost:9090`.

The optional `deploy/compose.cloud.yml` overlay supplies container memory limits
and bounded logs; it does not provision infrastructure or establish hosting status.

```sh
docker compose -f docker-compose.yml -f deploy/compose.cloud.yml up -d --build
```

## Stop

```sh
docker compose down
```

This preserves data and checkpoints. Use `docker compose down -v` only when you
intend to delete the project's data and checkpoints.
