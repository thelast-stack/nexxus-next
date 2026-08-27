from .core import ExecutionResult, ResolutionProposal


class MasterAI:
    """Minimal deterministic experiment for consuming execution feedback."""

    def handle_execution_result(self, result: ExecutionResult) -> ResolutionProposal | None:
        if result.status != "failed":
            return None

        return ResolutionProposal(
            proposal_id=f"followup-{result.execution_id}",
            event_id=result.proposal_id,
            problem="Execução falhou após autorização humana",
            context={
                "source_execution_id": result.execution_id,
                "source_result_id": result.result_id,
                "source_proposal_id": result.proposal_id,
                "source_decision_id": result.decision_id,
                "failure": result.details,
            },
            actions=({"type": "investigate_execution_failure", "execution_id": result.execution_id},),
            sectors=("transportes",),
            impact_risk="unknown",
            approval_required=True,
        )
