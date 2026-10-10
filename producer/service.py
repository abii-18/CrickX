"""Private Docker-network replay controls; acknowledged sends and durable cursor."""
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from kafka import KafkaProducer
from prometheus_client import Counter, Gauge, start_http_server
from cricx.simulator import generate_match

STATE = Path(os.environ.get("SIMULATOR_STATE", "/state/run.json"))
LOCK = threading.RLock()
SENT = Counter("cricx_producer_acknowledged_total", "Kafka acknowledged deliveries")
ERRORS = Counter("cricx_producer_errors_total", "Failed sends; cursor remains unchanged")
ACTIVE = Gauge("cricx_producer_active", "Simulator running")


def save():
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state))
    temporary.replace(STATE)


state = json.loads(STATE.read_text()) if STATE.exists() else dict(running=False, cursor=0, events=[], rate=2, match_id=None, error=None)
# Explicit resume after restart; persisted IDs and cursor make retries idempotent.
state["running"] = False


class Handler(BaseHTTPRequestHandler):
    def respond(self, value, status=200):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        with LOCK:
            expected = len({(event["innings_number"], event["raw_delivery_sequence"]) for event in state["events"] if "raw_delivery_sequence" in event})
            self.respond({k: v for k, v in state.items() if k != "events"} | {"total": len(state["events"]), "expected_deliveries": expected})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 65536:
                raise ValueError("request too large")
            data = json.loads(self.rfile.read(length) or b"{}")
            with LOCK:
                if self.path == "/alerts":
                    notifications = state.get("alerts", [])
                    for alert in data.get("alerts", []):
                        notifications.append({"name": alert.get("labels", {}).get("alertname", "Unknown"),
                                              "status": alert.get("status", "unknown"),
                                              "summary": alert.get("annotations", {}).get("summary", ""),
                                              "received_at": datetime.now(timezone.utc).isoformat()})
                    state["alerts"] = notifications[-20:]
                elif self.path == "/new":
                    rate = float(data.get("rate", 2))
                    if not 0.1 <= rate <= 100:
                        raise ValueError("rate must be 0.1–100")
                    match = "sim-" + uuid.uuid4().hex[:12]
                    start = datetime.now(timezone.utc).isoformat()
                    overs = int(data.get("overs", 50))
                    events = generate_match(match, int(data.get("seed", 42)), start, overs)
                    state.update(match_id=match, events=events, cursor=0, rate=rate, running=True, error=None, overs=overs)
                elif self.path == "/speed":
                    rate = float(data["rate"])
                    if not 0.1 <= rate <= 100:
                        raise ValueError("rate must be 0.1–100")
                    state["rate"] = rate
                elif self.path == "/inject":
                    mode = data.get("mode")
                    if mode == "duplicate" and state["cursor"]:
                        state["events"].insert(state["cursor"], state["events"][state["cursor"] - 1].copy())
                    elif mode == "invalid":
                        state["events"].insert(state["cursor"], {"match_id": state["match_id"], "invalid_demo": True})
                    elif mode == "delay" and state["cursor"] + 2 < len(state["events"]):
                        # Hold a real delivery behind two successors. Identity/time unchanged.
                        held = state["events"].pop(state["cursor"])
                        state["events"].insert(state["cursor"] + 2, held)
                    else:
                        raise ValueError("No suitable delivery available for this injection")
                    state["running"] = state["cursor"] < len(state["events"])
                elif self.path == "/pause":
                    state["running"] = False
                elif self.path == "/resume":
                    state["running"] = state["cursor"] < len(state["events"])
                else:
                    raise ValueError("unknown command")
                save()
            self.respond({"ok": True})
        except (ValueError, TypeError, KeyError) as exc:
            self.respond({"error": str(exc)}, 400)


def replay():
    producer = None
    while True:
        if producer is None:
            try:
                producer = KafkaProducer(bootstrap_servers=os.environ.get("KAFKA_BOOTSTRAP", "kafka:29092"), acks="all", retries=5,
                                         value_serializer=lambda value: json.dumps(value).encode())
            except Exception as exc:
                ERRORS.inc()
                with LOCK:
                    state["error"] = type(exc).__name__
                    state["running"] = False
                    save()
                time.sleep(5)
                continue
        delay = 0.2
        with LOCK:
            ACTIVE.set(int(state["running"]))
            if state["running"]:
                event = state["events"][state["cursor"]]
                try:
                    producer.send("match-events", key=(event.get("match_id") or "invalid-demo").encode(), value=event).get(timeout=20)
                    SENT.inc()
                    state["cursor"] += 1
                    state["error"] = None
                    state["running"] = state["cursor"] < len(state["events"])
                    save()
                except Exception as exc:
                    ERRORS.inc()
                    state["error"] = type(exc).__name__
                    state["running"] = False
                    save()
                delay = 1 / state["rate"]
        time.sleep(delay)


if __name__ == "__main__":
    start_http_server(9102)
    threading.Thread(target=replay, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", 9700), Handler).serve_forever()
