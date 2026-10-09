"""Separate canonical sink and watermark-bounded analytics queries."""
import json
import os
import time
from prometheus_client import Counter, Gauge, start_http_server
from pyspark.sql import SparkSession, functions as F, types as T
from cricx.store import initialize, persist

dsn = os.environ["DATABASE_URL"]
start_http_server(9101)
last_commit = Gauge("cricx_last_sink_commit_seconds", "Unix timestamp of successful canonical batch")
sink_errors = Counter("cricx_sink_errors_total", "Failed canonical micro-batch transactions")
records_metric = Counter("cricx_sink_records_total", "Observed committed sink outcomes; retries may be counted", ["outcome"])
batch_seconds = Gauge("cricx_batch_duration_seconds", "Latest canonical sink processing duration")
backlog = Gauge("cricx_spark_backlog_records", "Kafka end offset minus last successfully processed offset", ["partition"])
windows_metric = Gauge("cricx_window_event_count", "Latest emitted bounded window count", ["match_id"])
initialize(dsn)
spark = SparkSession.builder.appName("CricX").config("spark.sql.shuffle.partitions", "4").getOrCreate()
spark.sparkContext.setLogLevel("WARN")
source = spark.readStream.format("kafka").option("kafka.bootstrap.servers", os.environ["KAFKA_BOOTSTRAP"]).option("subscribe", "match-events").option("startingOffsets", "earliest").option("maxOffsetsPerTrigger", "1000").load()


def write_batch(frame, batch_id):
    started = time.monotonic()
    records = [(f"{row.topic}:{row.partition}:{row.offset}", row.value) for row in frame.select("topic", "partition", "offset", F.col("value").cast("string")).toLocalIterator()]
    try:
        counts = persist(dsn, records)
    except Exception:
        sink_errors.inc()
        raise
    for outcome, count in counts.items():
        records_metric.labels(outcome).inc(count)
    last_commit.set(time.time()); batch_seconds.set(time.monotonic() - started)
    print(json.dumps({"query": "canonical", "batch": batch_id, "outcomes": counts}), flush=True)


canonical = source.writeStream.foreachBatch(write_batch).option("checkpointLocation", "/checkpoints/canonical").trigger(processingTime="5 seconds").start()
schema = T.StructType([T.StructField("match_id", T.StringType()), T.StructField("event_time", T.StringType()), T.StructField("event_id", T.StringType())])
analytics = source.select(F.from_json(F.col("value").cast("string"), schema).alias("e")).select("e.*").withColumn("event_ts", F.to_timestamp("event_time")).filter("event_ts IS NOT NULL AND match_id IS NOT NULL")
windows = analytics.withWatermark("event_ts", "30 seconds").groupBy(F.window("event_ts", "10 seconds"), "match_id").count()


def emit_windows(frame, batch_id):
    for row in frame.toLocalIterator():
        windows_metric.labels(row.match_id).set(row["count"])
        print(json.dumps({"query": "event_windows", "batch": batch_id, "match": row.match_id, "window": str(row.window), "count": row["count"]}), flush=True)


# A separate checkpoint avoids changing the partition count of existing state.
window_query = windows.writeStream.outputMode("update").foreachBatch(emit_windows).option("checkpointLocation", "/checkpoints/windows-p4").trigger(processingTime="5 seconds").start()
# Offset backlog uses completed Spark progress, not Kafka consumer-group commits.
from kafka import KafkaConsumer, TopicPartition
consumer = KafkaConsumer(bootstrap_servers=os.environ["KAFKA_BOOTSTRAP"], group_id=None)
while canonical.isActive and window_query.isActive:
    progress = canonical.lastProgress
    if progress and progress.get("sources"):
        offsets = progress["sources"][0].get("endOffset", {})
        if isinstance(offsets, str):
            offsets = json.loads(offsets)
        for topic, partitions in offsets.items():
            for partition, processed in partitions.items():
                tp = TopicPartition(topic, int(partition))
                latest = consumer.end_offsets([tp])[tp]
                backlog.labels(str(partition)).set(max(0, latest - processed))
    time.sleep(2)
consumer.close()
for query in (canonical, window_query):
    if query.exception():
        raise RuntimeError(str(query.exception()))
