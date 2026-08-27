from nexxus.core import (
    Core,
    ExecutionRequest,
    HumanDecision,
    InvestigationRequest,
    ResolutionProposal,
    SectorEvent,
    utc_now,
)


def make_flow(decision_status="approved"):
    event = SectorEvent(
        "evt-1", "transportes", "vehicle_breakdown", "vehicle-42",
        {"freight": "FR-100", "location": "Luanda"}, utc_now(),
    )
    investigation = InvestigationRequest(
        "inv-1", event.event_id, ("manutencao", "financeiro"),
        ("diagnosticar avaria", "avaliar impacto financeiro"),
    )
    proposal = ResolutionProposal(
        "prop-1", event.event_id, "Veículo indisponível durante frete",
        {"investigation": investigation.request_id},
        (
            {"type": "tow_vehicle", "vehicle": event.entity},
            {"type": "authorize_repair", "vehicle": event.entity},
        ),
        ("transportes", "manutencao", "financeiro"), "medium",
    )
    decision = HumanDecision("dec-1", proposal.proposal_id, decision_status, "director-1")
    request = ExecutionRequest("exec-1", proposal.proposal_id, decision.decision_id, "core-gateway")
    return event, investigation, proposal, decision, request


def test_approved_flow_executes_and_is_audited():
    _, _, proposal, decision, request = make_flow()
    core = Core()
    result = core.execute(request, proposal, decision)
    assert result.status == "executed"
    assert len(core.audit_log) == 2
    assert core.audit_log[-1]["status"] == "executed"


def test_rejected_human_decision_cannot_execute():
    _, _, proposal, decision, request = make_flow("rejected")
    result = Core().execute(request, proposal, decision)
    assert result.status == "rejected"
    assert result.details["reason"] == "human approval required"


def test_mismatched_decision_cannot_execute():
    _, _, proposal, decision, request = make_flow()
    forged_request = ExecutionRequest(
        request.request_id, proposal.proposal_id, "different-decision", request.requested_by
    )
    result = Core().execute(forged_request, proposal, decision)
    assert result.status == "rejected"
    assert "does not match" in result.details["reason"]
