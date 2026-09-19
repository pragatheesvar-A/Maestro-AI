from app.services.websocket_manager import ConnectionManager


def test_decision_trace_404_when_task_never_optimized(client, auth_headers):
    resp = client.post("/tasks", json={"title": "Untouched task", "priority": "LOW", "estimated_hours": 4}, headers=auth_headers)
    task_id = resp.json()["id"]
    trace_resp = client.get(f"/allocation/{task_id}/decision-trace", headers=auth_headers)
    assert trace_resp.status_code == 404


def test_decision_trace_contains_rejected_candidates_with_scores(client, auth_headers):
    client.post("/employees", json={
        "name": "Dana", "email": "dana@test.local", "role": "Engineer",
        "skills": [{"skill_name": "Python", "proficiency": 0.9}],
    }, headers=auth_headers)
    client.post("/employees", json={
        "name": "Evan", "email": "evan@test.local", "role": "Engineer",
        "skills": [{"skill_name": "Python", "proficiency": 0.5}],
    }, headers=auth_headers)
    task_resp = client.post("/tasks", json={
        "title": "Data pipeline work", "priority": "MEDIUM", "estimated_hours": 6,
        "required_skills": [{"skill_name": "Python", "min_proficiency": 0.4}],
    }, headers=auth_headers)
    task_id = task_resp.json()["id"]

    client.post("/allocation/optimize", json={}, headers=auth_headers)

    trace_resp = client.get(f"/allocation/{task_id}/decision-trace", headers=auth_headers)
    assert trace_resp.status_code == 200
    trace = trace_resp.json()
    assert len(trace["candidates"]) == 2
    for c in trace["candidates"]:
        assert "skill_match" in c and "sla_risk" in c and "workload_utilization_after" in c


def test_websocket_connection_manager_broadcast_removes_dead_sockets():
    import asyncio

    class FakeSocket:
        def __init__(self, fail=False):
            self.fail = fail
            self.sent = []

        async def accept(self):
            pass

        async def send_text(self, msg):
            if self.fail:
                raise RuntimeError("closed")
            self.sent.append(msg)

    async def run():
        mgr = ConnectionManager()
        good = FakeSocket()
        bad = FakeSocket(fail=True)
        await mgr.connect(good)
        await mgr.connect(bad)
        await mgr.broadcast({"type": "TEST_EVENT", "value": 1})
        assert good.sent  # message delivered
        assert bad not in mgr.active  # dead socket pruned
        assert good in mgr.active

    asyncio.run(run())


def test_websocket_endpoint_sends_connected_message(client):
    with client.websocket_connect("/ws/allocation") as ws:
        data = ws.receive_json()
        assert data["type"] == "CONNECTED"
