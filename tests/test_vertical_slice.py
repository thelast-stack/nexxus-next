from nexxus.vertical_slice import run_vehicle_breakdown


def test_approved_flow_executes():
    *_, result = run_vehicle_breakdown("approved")
    assert result.status == "executed"
    assert result.details["actions"]


def test_rejected_human_decision_cannot_execute():
    *_, result = run_vehicle_breakdown("rejected")
    assert result.status == "rejected"
    assert result.details["reason"] == "human approval required"


def test_execution_request_cannot_forge_approval():
    _, _, proposal, decision, request, _ = run_vehicle_breakdown()
    from nexxus.core import Core, ExecutionRequest
    forged = ExecutionRequest(request.request_id, proposal.proposal_id, "different-decision", request.requested_by)
    result = Core().execute(forged, proposal, decision)
    assert result.status == "rejected"
    assert "does not match" in result.details["reason"]
