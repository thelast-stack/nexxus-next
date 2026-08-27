from nexxus.core import Core, ExecutionRequest, HumanDecision, InvestigationRequest, ResolutionProposal, SectorEvent, utc_now


def make_flow(decision_status="approved"):
    event = SectorEvent("evt-1", "transportes", "vehicle_breakdown", "vehicle-42", {"freight": "FR-100", "location": "Luanda"}, utc_now())
    investigation = InvestigationRequest("inv-1", event.event_id, ("manutencao", "financeiro"), ("diagnosticar avaria", "avaliar impacto financeiro"))
    proposal = ResolutionProposal("prop-1", event.event_id, "Veículo indisponível durante frete", {"investigation": investigation.request_id}, ({"type": "tow_vehicle", "vehicle": event.entity}, {"type": "authorize_repair", "vehicle": event.entity}), ("transportes", "manutencao", "financeiro"), "medium")
    decision = HumanDecision("dec-1", proposal.proposal_id, decision_status, "director-1")
    request = ExecutionRequest("exec-1", proposal.proposal_id, decision.decision_id, "core-gateway")
    return event, investigation, proposal, decision, request


def test_approved_flow_executes_and_is_traceable():
    event, investigation, proposal, decision, request = make_flow()
    result = Core().execute(request, proposal, decision)
    assert result.status == "executed"
    assert investigation.event_id == event.event_id
    assert proposal.event_id == event.event_id
    assert decision.proposal_id == proposal.proposal_id
    assert request.proposal_id == proposal.proposal_id
    assert request.decision_id == decision.decision_id
    assert result.execution_id == request.execution_id
    assert result.result_id == f"result-{request.execution_id}"


def test_rejected_human_decision_cannot_execute():
    _, _, proposal, decision, request = make_flow("rejected")
    result = Core().execute(request, proposal, decision)
    assert result.status == "rejected"
    assert result.details["reason"] == "human approval required"


def test_execution_without_approval_is_blocked():
    _, _, proposal, decision, request = make_flow("rejected")
    result = Core().execute(request, proposal, decision)
    assert result.status == "rejected"


def test_mismatched_decision_is_blocked():
    _, _, proposal, decision, request = make_flow()
    forged_request = ExecutionRequest(request.execution_id, proposal.proposal_id, "different-decision", request.requested_by)
    result = Core().execute(forged_request, proposal, decision)
    assert result.status == "rejected"
    assert "does not match" in result.details["reason"]


def test_approved_result_contains_context_for_master_ai():
    event, _, proposal, decision, request = make_flow()
    result = Core().execute(request, proposal, decision)
    context = {"event_id": event.event_id, "proposal_id": proposal.proposal_id, "decision_id": decision.decision_id, "execution_id": request.execution_id, "result_id": result.result_id, "status": result.status}
    assert context == {"event_id": "evt-1", "proposal_id": "prop-1", "decision_id": "dec-1", "execution_id": "exec-1", "result_id": "result-exec-1", "status": "executed"}
