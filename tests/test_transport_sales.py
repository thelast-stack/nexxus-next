import json
import threading
from http.server import HTTPServer
import urllib.request

from nexxus.demo_app import Handler
from nexxus.transport import TransportSalesState


def build_request(state):
    client = state.create_client("ACME Cargo", "+244 900 000 000", "NIF-001")
    request = state.create_request(
        client_id=client.client_id,
        cargo_description="Contentor alimentar",
        quantity=1,
        weight_kg=12000,
        volume_m3=30,
        cargo_type="carga geral",
        origin="Luanda",
        destination="Lobito",
        priority="high",
    )
    return request


def test_request_and_proforma_are_linked_and_payment_blocks_operation():
    state = TransportSalesState()
    request = build_request(state)
    proforma = state.create_proforma(request.request_id)

    assert proforma.request_id == request.request_id
    assert proforma.client_id == request.client_id
    assert proforma.status == "payment_pending"
    assert proforma.total > 0
    assert state.operation_eligibility(request.request_id) is False

    state.confirm_payment(proforma.proforma_id)
    assert state.proformas[proforma.proforma_id].status == "paid"
    assert state.operation_eligibility(request.request_id) is True


def test_request_requires_client_and_required_fields():
    state = TransportSalesState()
    try:
        state.create_request(
            cargo_description="Carga",
            quantity=1,
            weight_kg=100,
            volume_m3=1,
            cargo_type="geral",
            origin="Luanda",
            destination="Lobito",
        )
        assert False, "request without client must fail"
    except ValueError as exc:
        assert "client" in str(exc)


def test_transport_http_flow_returns_live_state():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        body = json.dumps({"name": "ACME", "contact": "900", "identification": "NIF-9"}).encode()
        req = urllib.request.Request(base + "/api/transport/client", data=body, method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as response:
            data = json.load(response)
        assert data["transport"]["selected_client"]["name"] == "ACME"

        body = json.dumps({"cargo_description": "Carga", "quantity": 2, "weight_kg": 1000, "volume_m3": 4, "cargo_type": "geral", "origin": "Luanda", "destination": "Benguela"}).encode()
        req = urllib.request.Request(base + "/api/transport/request", data=body, method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as response:
            data = json.load(response)
        assert data["transport"]["request"]["request_id"] == "req-001"

        body = json.dumps({"request_id": "req-001"}).encode()
        req = urllib.request.Request(base + "/api/transport/proforma", data=body, method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as response:
            data = json.load(response)
        assert data["transport"]["proforma"]["status"] == "payment_pending"
        assert data["transport"]["operation_eligible"] is False
    finally:
        server.shutdown()
        server.server_close()
