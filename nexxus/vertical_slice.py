from .core import (
    Core, ExecutionRequest, HumanDecision, InvestigationRequest,
    ResolutionProposal, SectorEvent, utc_now,
)


def run_vehicle_breakdown(decision_status: str = "approved"):
    """Run the deliberately small experimental Vertical Slice #1."""
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
    result = Core().execute(request, proposal, decision)
    return event, investigation, proposal, decision, request, result
