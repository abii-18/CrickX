"""Finite canonical-ledger snapshots, not raw Kafka messages or streaming state."""
from pyspark.sql import Window, functions as F, types as T

SCHEMA = T.StructType([
    T.StructField("match_id", T.StringType(), False),
    *[T.StructField(name, T.LongType(), False) for name in (
        "innings_number", "raw_delivery_sequence", "batter_runs", "wides",
        "no_balls", "byes", "leg_byes")],
    T.StructField("wicket_type", T.StringType(), True),
])


def aggregate_overs(frame):
    """Input contract: validated, unique current slots from the transactional ledger."""
    preceding = Window.partitionBy("match_id", "innings_number").orderBy(
        "raw_delivery_sequence").rowsBetween(Window.unboundedPreceding, -1)
    deliveries = frame.withColumn("legal", (
        (F.col("wides") == 0) & (F.col("no_balls") == 0)).cast("long"))
    deliveries = deliveries.withColumn("over_number", F.floor(
        F.coalesce(F.sum("legal").over(preceding), F.lit(0)) / 6).cast("long"))
    return deliveries.groupBy("match_id", "innings_number", "over_number").agg(
        F.sum(F.col("batter_runs") + F.col("wides") + F.col("no_balls") +
              F.col("byes") + F.col("leg_byes")).alias("runs"),
        F.sum(F.col("wicket_type").isNotNull().cast("long")).alias("wickets"),
        F.sum("legal").alias("legal_balls"))


def compute_over_summaries(spark, events):
    # Only field projection happens in Python; cricket arithmetic happens in Spark.
    rows = [(e["match_id"], e["innings_number"], e["raw_delivery_sequence"],
             e["batter_runs"], e["extras"]["wides"], e["extras"]["no_balls"],
             e["extras"]["byes"], e["extras"]["leg_byes"], e["wicket_type"])
            for e in events]
    if not rows:
        return {}
    return {(r.match_id, r.innings_number, r.over_number):
            {"runs": r.runs, "wickets": r.wickets, "legal_balls": r.legal_balls}
            for r in aggregate_overs(spark.createDataFrame(rows, SCHEMA)).toLocalIterator()}
