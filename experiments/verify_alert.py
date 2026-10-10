"""Run while Spark is deliberately stopped; requires an actual routed alert."""
import json
import time
from urllib.request import urlopen


if __name__ == "__main__":
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        with urlopen("http://simulator:9700", timeout=25) as response:
            state = json.load(response)
        alerts = [alert for alert in state.get("alerts", []) if alert["name"] == "CricXProcessorUnavailable" and alert["status"] == "firing"]
        if alerts:
            print(json.dumps(alerts[-1]))
            break
        time.sleep(2)
    else:
        raise TimeoutError("Actual processor-down alert was not routed to the dashboard")
