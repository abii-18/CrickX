"""Real threaded HTTP requests with a controlled Kafka acknowledgement future."""
import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch
from producer import service


class PendingProducer:
    def __init__(self, failure=None):
        self.waiting = threading.Event()
        self.release = threading.Event()
        self.failure = failure
        self.sent = []

    def send(self, topic, key, value):
        self.sent.append(copy.deepcopy(value))
        return self

    def get(self, timeout):
        self.waiting.set()
        if not self.release.wait(5):
            raise TimeoutError("test acknowledgement not released")
        if self.failure:
            raise self.failure


class ProducerServiceTests(unittest.TestCase):
    def setUp(self):
        self.original = service.state
        service.state = dict(running=True, cursor=0, events=[{"match_id": "first", "n": 1}, {"match_id": "first", "n": 2}],
                             rate=2, match_id="first", error=None)
        self.directory = tempfile.TemporaryDirectory()
        self.state_patch = patch.object(service, "STATE", Path(self.directory.name) / "run.json")
        self.state_patch.start()
        self.server = service.ThreadingHTTPServer(("127.0.0.1", 0), service.Handler)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.producer = PendingProducer()
        self.workers = []

    def tearDown(self):
        self.producer.release.set()
        for worker in self.workers:
            worker.join(6)
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(2)
        self.state_patch.stop()
        service.state = self.original
        self.directory.cleanup()

    def request(self, path="", data=None):
        request = Request(f"http://127.0.0.1:{self.server.server_port}{path}",
                          data=json.dumps(data).encode() if data is not None else None,
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=2) as response:
            return json.load(response)

    def start_send(self):
        worker = threading.Thread(target=service.send_next, args=(self.producer,))
        self.workers.append(worker)
        worker.start()
        self.assertTrue(self.producer.waiting.wait(2))

    def test_status_pause_speed_and_alerts_respond_during_ack_wait(self):
        self.start_send()
        self.assertEqual(self.request()["cursor"], 0)
        self.assertEqual(self.request("/pause", {}), {"ok": True})
        self.request("/speed", {"rate": 10})
        self.request("/alerts", {"alerts": [{"labels": {"alertname": "test"}, "status": "firing"}]})
        self.producer.release.set()
        self.workers[0].join(2)
        self.assertFalse(self.workers[0].is_alive())
        snapshot = self.request()
        self.assertEqual(snapshot["cursor"], 1)
        self.assertFalse(snapshot["running"])
        self.assertEqual(snapshot["rate"], 10)
        self.assertEqual(snapshot["alerts"][0]["name"], "test")
        self.assertEqual(json.loads(service.STATE.read_text())["cursor"], 1)

    def test_queue_injection_waits_for_ack_and_preserves_slot_order(self):
        attempted = threading.Event()
        original_lock = service.SEND_LOCK
        class ObservedLock:
            def __enter__(self):
                if original_lock.locked():
                    attempted.set()
                original_lock.acquire()
            def __exit__(self, *args):
                original_lock.release()
        lock_patch = patch.object(service, "SEND_LOCK", ObservedLock())
        lock_patch.start()
        self.addCleanup(lock_patch.stop)
        self.start_send()
        responses = []
        started = threading.Event()
        def inject():
            started.set()
            responses.append(self.request("/inject", {"mode": "duplicate"}))
        worker = threading.Thread(target=inject)
        self.workers.append(worker)
        worker.start()
        self.assertTrue(started.wait(1))
        self.assertTrue(attempted.wait(1))  # HTTP reached the guard before ack release.
        self.assertEqual(self.request()["cursor"], 0)
        self.producer.release.set()
        for worker in self.workers:
            worker.join(2)
            self.assertFalse(worker.is_alive())
        self.assertEqual(responses, [{"ok": True}])
        self.assertEqual(service.state["cursor"], 1)
        self.assertEqual([e["n"] for e in service.state["events"]], [1, 1, 2])
        service.send_next(self.producer)
        service.send_next(self.producer)
        self.assertEqual([e["n"] for e in self.producer.sent], [1, 1, 2])

    def test_timeout_keeps_cursor_and_requires_explicit_resume(self):
        self.producer.failure = TimeoutError("injected timeout")
        self.start_send()
        self.assertEqual(self.request()["cursor"], 0)
        self.producer.release.set()
        self.workers[0].join(2)
        snapshot = self.request()
        self.assertEqual(snapshot["cursor"], 0)
        self.assertFalse(snapshot["running"])
        self.assertEqual(snapshot["error"], "TimeoutError")
        self.producer.failure = None
        self.request("/resume", {})
        service.send_next(self.producer)
        self.assertEqual([e["n"] for e in self.producer.sent], [1, 1])
        self.assertEqual(service.state["cursor"], 1)

    def test_invalid_command_still_returns_400(self):
        with self.assertRaises(HTTPError) as error:
            self.request("/speed", {"rate": 0})
        self.assertEqual(error.exception.code, 400)
