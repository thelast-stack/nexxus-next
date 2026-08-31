import pytest

from nexxus.transport import TransportSalesState


def prepared_state():
    state = TransportSalesState()
    client = state.create_client("ACME Cargo", "+244 900 000 000", "NIF-001")
    request = state.create_request(
        client_id=client.client_id,
        cargo_description="Contentor alimentar",
        quantity=1,
        weight_kg=12000,
        volume_m3=30,
        cargo_type="contentor",
        origin="Luanda",
        destination="Lobito",
        distance_km=520,
    )
    return state, request


def test_unpaid_request_cannot_create_operation():
    state, request = prepared_state()
    state.create_proforma(request.request_id)
    with pytest.raises(ValueError, match="payment"):
        state.create_operation(request.request_id)


def test_paid_request_can_become_ready_with_available_resources():
    state, request = prepared_state()
    proforma = state.create_proforma(request.request_id)
    state.confirm_payment(proforma.proforma_id)
    operation = state.create_operation(request.request_id)

    state.assign_vehicle(operation.operation_id, "veh-001")
    state.assign_driver(operation.operation_id, "drv-001")

    assert operation.status == "READY_FOR_EXECUTION"
    assert operation.request_id == request.request_id
    assert operation.vehicle_id == "veh-001"
    assert operation.driver_id == "drv-001"
    assert state.vehicles["veh-001"].status == "ASSIGNED"
    assert state.drivers["drv-001"].status == "ASSIGNED"


def test_unavailable_vehicle_and_driver_cannot_be_assigned():
    state, request = prepared_state()
    proforma = state.create_proforma(request.request_id)
    state.confirm_payment(proforma.proforma_id)
    operation = state.create_operation(request.request_id)

    with pytest.raises(ValueError, match="vehicle is not available"):
        state.assign_vehicle(operation.operation_id, "veh-003")
    with pytest.raises(ValueError, match="driver is not available"):
        state.assign_driver(operation.operation_id, "drv-003")


def test_vehicle_capacity_is_checked():
    state, request = prepared_state()
    state.requests[request.request_id].weight_kg = 40000
    proforma = state.create_proforma(request.request_id)
    state.confirm_payment(proforma.proforma_id)
    operation = state.create_operation(request.request_id)
    with pytest.raises(ValueError, match="capacity"):
        state.assign_vehicle(operation.operation_id, "veh-001")
