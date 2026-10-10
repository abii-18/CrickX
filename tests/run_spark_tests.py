"""Run via spark-submit in the existing Spark image; credentials stay in env."""
import os
import sys
import unittest

os.environ["CRICX_RUN_SPARK_TESTS"] = "1"
os.environ["CRICX_TEST_DATABASE_URL"] = os.environ["DATABASE_URL"]
sys.path.insert(0, "/app")
suite = unittest.defaultTestLoader.discover("tests", pattern="test_spark_aggregation.py")
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(not result.wasSuccessful())
