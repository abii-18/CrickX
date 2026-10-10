"""Isolated Kafka topic: ordering, group partition sharing, independent replay."""
import json
import time
import uuid
from kafka import KafkaConsumer, KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic


if __name__ == "__main__":
    topic = "cricx-experiment-" + uuid.uuid4().hex[:12]
    admin = KafkaAdminClient(bootstrap_servers="kafka:29092")
    admin.create_topics([NewTopic(topic, 3, 1)])
    producer = KafkaProducer(bootstrap_servers="kafka:29092", acks="all", retries=5, retry_backoff_ms=500)
    consumers = []
    try:
        for index in range(30):
            producer.send(topic, key=f"match-{index % 3}".encode(), value=str(index).encode()).get(timeout=20)
        group = topic + "-shared"
        options = dict(bootstrap_servers="kafka:29092", auto_offset_reset="earliest", enable_auto_commit=False)
        consumers = [KafkaConsumer(topic, group_id=group, **options) for _ in range(2)]
        received = set()
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            for consumer in consumers:
                records = consumer.poll(timeout_ms=500)
                for messages in records.values():
                    received.update(int(message.value) for message in messages)
                if records:
                    consumer.commit()
            assignments = [consumer.assignment() for consumer in consumers]
            if len(received) == 30 and all(assignments) and not assignments[0] & assignments[1] and len(assignments[0] | assignments[1]) == 3:
                break
        else:
            raise TimeoutError("Shared consumer group failed to converge")
        independent = KafkaConsumer(topic, group_id=topic + "-independent", **options)
        consumers.append(independent)
        replayed = []
        per_key = {}
        deadline = time.monotonic() + 60
        while len(replayed) < 30 and time.monotonic() < deadline:
            for messages in independent.poll(timeout_ms=500).values():
                for message in messages:
                    index = int(message.value)
                    replayed.append(index)
                    per_key.setdefault(message.key.decode(), []).append(index)
        assert set(replayed) == set(range(30))
        assert all(values == sorted(values) for values in per_key.values()), per_key
        print(json.dumps({"partitions": [[tp.partition for tp in sorted(assignment)] for assignment in assignments],
                          "shared_group_unique_records": len(received), "independent_group_records": len(replayed),
                          "per_match_order": per_key}))
    finally:
        for consumer in consumers:
            consumer.close()
        producer.close()
        admin.delete_topics([topic])
        admin.close()
