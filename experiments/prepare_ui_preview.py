"""Publish a partial ODI and pause for a readable in-progress dashboard demo."""
import json
import os
import time
import psycopg
from urllib.request import Request, urlopen


def api(path="", data=None):
    request = Request("http://simulator:9700" + path, data=json.dumps(data).encode() if data is not None else None,
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=25) as response:
        return json.load(response)


if __name__ == "__main__":
    api("/new", {"overs": 50, "seed": 42, "rate": 25})
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        status = api()
        if status["cursor"] >= 110:
            api("/pause", {})
            api("/speed", {"rate": 2})
            current = api()
            print(json.dumps({key: current[key] for key in ("match_id", "cursor", "total", "rate", "running")}))
            commit_deadline = time.monotonic() + 60
            while time.monotonic() < commit_deadline:
                with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
                    count = conn.execute("SELECT count(*) FROM delivery_events WHERE match_id=%s", (current["match_id"],)).fetchone()[0]
                    card = conn.execute("SELECT runs,wickets,legal_balls FROM innings_scorecard WHERE match_id=%s", (current["match_id"],)).fetchone()
                if count == current["cursor"]:
                    print(f"Preview committed: {card}")
                    break
                time.sleep(1)
            else:
                raise TimeoutError("Preview deliveries did not commit")
            break
        time.sleep(.2)
    else:
        api("/pause", {})
        raise TimeoutError("Preview replay did not progress")
