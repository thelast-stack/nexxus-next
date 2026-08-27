from dataclasses import dataclass

from .core import ExecutionResult, ResolutionProposal


@dataclass(frozen=True)
class SectorPerspective:
    sector: str
    facts: dict[str, object]


class MasterAI:
    """Small deterministic experiment for cross-sector coordination and feedback."""

    def coordinate(self, event_id: str, perspectives: tuple[SectorPerspective, ...]) -> ResolutionProposal:
        by_sector = {p.sector: p for p in perspectives}
        required = {"transportes", "manutencao", "financeiro"}
        if not required.issubset(by_sector):
            raise ValueError("all three sector perspectives are required")
        transport = by_sector["transportes"].facts
        maintenance = by_sector["manutencao"].facts
        finance = by_sector["financeiro"].facts
        return ResolutionProposal(
            proposal_id="master-proposal-1",
            event_id=event_id,
            problem="Avaria de veículo afecta uma operação urgente e exige coordenação transversal",
            context={"transportes": transport, "manutencao": maintenance, "financeiro": finance},
            actions=(
                {"type": "coordinate_vehicle_repair", "vehicle": transport["vehicle_id"]},
                {"type": "manage_operational_impact", "operation": transport["operation_id"]},
            ),
            sectors=("transportes", "manutencao", "financeiro"),
            impact_risk="high",
            approval_required=True,
        )

    def handle_execution_result(self, result: ExecutionResult) -> ResolutionProposal | None:
        if result.status != "failed":
            return None
        return ResolutionProposal(
            proposal_id=f"followup-{result.execution_id}",
            event_id=result.proposal_id,
            problem="Execução falhou após autorização humana",
            context={"source_execution_id": result.execution_id, "source_result_id": result.result_id, "source_proposal_id": result.proposal_id, "source_decision_id": result.decision_id, "failure": result.details},
            actions=({"type": "investigate_execution_failure", "execution_id": result.execution_id},),
            sectors=("transportes",), impact_risk="unknown", approval_required=True,
        )
