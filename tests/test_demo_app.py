import json
import threading
import urllib.request
from http.server import HTTPServer

from nexxus.demo_app import DemoState, Handler


def test_demo_state_runs_real_coordination_and_requires_human_approval():
    state = DemoState()
    state.activate_breakdown()
    assert state.event.event_id == "evt-demo-1"
    assert state.proposal.event_id == state.event.event_id
    assert state.proposal.sectors == ("transportes", "manutencao", "financeiro")
    assert state.proposal.context["manutencao"]["diagnosis"] == "falha do motor"
    assert state.proposal.context["financeiro"]["alternative_cost"] == 1800
    assert state.request is None

    state.decide("rejected")
    assert state.result.status == "rejected"
    assert state.result.proposal_id == state.proposal.proposal_id


def test_demo_state_approved_flow_produces_execution_result_and_master_interpretation():
    state = DemoState()
    state.activate_breakdown()
    state.decide("approved")
    assert state.result.status == "succeeded"
    state.execute_failure()
    assert state.result.status == "failed"
    assert state.result.execution_id == state.request.execution_id
    assert state.master_interpretation.startswith("Execução exec-demo-1 falhou")


def test_demo_http_interface_reflects_live_state():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with urllib.request.urlopen(base + "/") as response:
            assert response.status == 200
            assert b"NEXXUS NEXT" in response.read()
        req = urllib.request.Request(base + "/api/breakdown", method="POST")
        with urllib.request.urlopen(req) as response:
            data = json.load(response)
        assert data["event"]["event_id"] == "evt-demo-1"
        assert data["proposal"]["sectors"] == ["transportes", "manutencao", "financeiro"]
    finally:
        server.shutdown()
        server.server_close()
