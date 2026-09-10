import json
import logging
import sys
import time
import uuid

from flask import Flask, g, jsonify, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

app = Flask(__name__)

tasks = {}
next_id = 1

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(message)s",
)

log = logging.getLogger("taskflow")

REQUESTS = Counter(
    "taskflow_requests_total",
    "HTTP requests",
    ["method", "path", "status"],
)


@app.before_request
def start_timer():
    g.start = time.time()
    g.trace_id = request.headers.get("X-Trace-Id", uuid.uuid4().hex[:8])


@app.after_request
def log_request(response):
    log.info(json.dumps({
        "level": "info",
        "event": "http.request",
        "method": request.method,
        "path": request.path,
        "status": response.status_code,
        "duration_ms": round((time.time() - g.start) * 1000, 1),
        "trace_id": g.trace_id,
    }))
    return response


@app.after_request
def count_request(response):
    REQUESTS.labels(
        request.method,
        request.path,
        response.status_code,
    ).inc()
    return response


@app.get("/health")
def health():
    return jsonify(status="ok", message="hello GITAM"), 200


@app.post("/tasks")
def create_task():
    global next_id
    data = request.get_json(silent=True) or {}
    title = data.get("title")

    if not title:
        return jsonify(error="title is required"), 400

    task = {"id": next_id, "title": title, "done": False}
    tasks[next_id] = task
    next_id += 1

    return jsonify(task), 201


@app.get("/tasks")
def list_tasks():
    return jsonify(list(tasks.values())), 200


@app.put("/tasks/<int:task_id>/complete")
def complete_task(task_id):
    task = tasks.get(task_id)

    if not task:
        return jsonify(error="not found"), 404

    task["done"] = True
    return jsonify(task), 200


@app.get("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
