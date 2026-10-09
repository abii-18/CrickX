FROM apache/spark:3.5.3
USER root
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir psycopg[binary]==3.2.6 kafka-python==2.1.2 prometheus-client==0.21.1
COPY . .
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1
RUN mkdir -p /checkpoints /tmp/ivy && chmod 777 /checkpoints /tmp/ivy
USER 185
CMD ["/opt/spark/bin/spark-submit", "--master", "local[2]", "--driver-memory", "2g", "--conf", "spark.jars.ivy=/tmp/ivy", "--packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3", "spark/streaming_job.py"]
