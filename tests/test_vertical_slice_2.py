from nexxus.vertical_slice import run_vehicle_breakdown

def test_approved_flow_executes():
    *_, result = run_vehicle_breakdown("approved")
    assert result.status == "executed"

def test_rejected_human_decision_cannot_execute():
    *_, result = run_vehicle_breakdown("rejected")
    assert result.status == "rejected"
