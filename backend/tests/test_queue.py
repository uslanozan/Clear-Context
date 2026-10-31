import threading
import time
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from clear_context.main import create_app
from clear_context.services.queue import InvestigationQueue


def test_queue_runs_at_most_the_worker_count_in_order():
    started, release, lock = [], threading.Event(), threading.Lock()
    active = {"now": 0, "most": 0}

    def run(investigation_id):
        with lock:
            started.append(investigation_id)
            active["now"] += 1
            active["most"] = max(active["most"], active["now"])
        release.wait(5)
        with lock:
            active["now"] -= 1

    queue = InvestigationQueue(run, workers=2)
    ids = [uuid4() for _ in range(5)]
    for investigation_id in ids:
        queue.submit(investigation_id)
    time.sleep(0.2)
    assert started == ids[:2]
    release.set()
    queue.pool.shutdown(wait=True)
    assert started == ids and active["most"] == 2


def test_closing_the_queue_does_not_start_waiting_jobs():
    started, release = [], threading.Event()

    def run(investigation_id):
        started.append(investigation_id)
        release.wait(5)

    queue = InvestigationQueue(run, workers=1)
    for _ in range(3):
        queue.submit(uuid4())
    time.sleep(0.1)
    queue.close()
    release.set()
    time.sleep(0.1)
    assert len(started) == 1


def test_queued_investigations_report_how_many_wait_ahead(settings):
    app = create_app(settings.model_copy(update={"max_concurrent_investigations": 1}))
    with TestClient(app) as client:
        # Nothing runs here: the jobs stay queued so their positions can be read.
        app.state.queue.close()
        app.state.queue.submit = lambda investigation_id, background=None: None
        ids = [
            client.post("/api/investigations", json={"text": f"Claim {n}."}).json()["id"]
            for n in range(3)
        ]
        positions = [client.get(f"/api/investigations/{i}").json()["queue_position"] for i in ids]
        assert positions == [0, 1, 2]
        repository = app.state.repository
        assert repository.queued_ids() == [UUID(i) for i in ids]
        listed = client.get("/api/investigations").json()
        assert all(item["queue_position"] is None for item in listed)
