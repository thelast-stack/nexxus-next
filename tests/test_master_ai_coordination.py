from nexxus.core import SectorEvent, utc_now
from nexxus.master_ai import MasterAI, SectorPerspective


def test_master_ai_combines_three_sector_perspectives_into_one_proposal():
    event = SectorEvent("evt-cross-1", "transportes", "vehicle_breakdown", "vehicle-42", {"urgent": True}, utc_now())
    perspectives = (
        SectorPerspective("transportes", {"vehicle_id": "vehicle-42", "operation_id": "freight-77", "urgent": True}),
        SectorPerspective("manutencao", {"diagnosis": "motor failure", "repair_estimate_hours": 6}),
        SectorPerspective("financeiro", {"alternative_cost": 1800, "currency": "EUR"}),
    )
    proposal = MasterAI().coordinate(event.event_id, perspectives)

    assert proposal.event_id == event.event_id
    assert proposal.sectors == ("transportes", "manutencao", "financeiro")
    assert proposal.context["transportes"]["vehicle_id"] == "vehicle-42"
    assert proposal.context["manutencao"]["diagnosis"] == "motor failure"
    assert proposal.context["financeiro"]["alternative_cost"] == 1800
    assert len(proposal.actions) == 2
    assert proposal.approval_required is True


def test_master_ai_does_not_execute_coordination_proposal():
    perspectives = (
        SectorPerspective("transportes", {"vehicle_id": "vehicle-42", "operation_id": "freight-77", "urgent": True}),
        SectorPerspective("manutencao", {"diagnosis": "motor failure", "repair_estimate_hours": 6}),
        SectorPerspective("financeiro", {"alternative_cost": 1800, "currency": "EUR"}),
    )
    proposal = MasterAI().coordinate("evt-cross-1", perspectives)
    assert not hasattr(proposal, "execution_result")
    assert proposal.approval_required is True
