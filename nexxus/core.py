from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


@dataclass(frozen=True)
class SectorEvent:
    event_id: str
    sector: str
    type: str
    entity: str
    facts: dict[str, Any]
    timestamp: datetime


@dataclass(frozen=True)
class InvestigationRequest:
    request_id: str
    event_id: str
    sectors: tuple[str, ...]
    questions: tuple[str, ...]


@dataclass(frozen=True)
class ResolutionProposal:
    proposal_id: str
    event_id: str
    problem: str
    context: dict[str, Any]
    actions: tuple[dict[str, Any], ...]
    sectors: tuple[str, ...]
    impact_risk: str
    approval_required: bool = True


@dataclass(frozen=True)
class HumanDecision:
    decision_id: str
    proposal_id: str
    status: Literal["approved", "rejected"]
    decided_by: str


@dataclass(frozen=True)
class ExecutionRequest:
    execution_id: str
    proposal_id: str
    decision_id: str
    requested_by: str


@dataclass(frozen=True)
class ExecutionResult:
    result_id: str
    execution_id: str
    proposal_id: str
    decision_id: str
    status: Literal["succeeded", "failed", "rejected"]
    details: dict[str, Any]


@dataclass
class Core:
    audit_log: list[dict[str, Any]] = field(default_factory=list)

    def execute(self, request: ExecutionRequest, proposal: ResolutionProposal, decision: HumanDecision) -> ExecutionResult:
        self.audit_log.append({"type": "execution_request", "execution_id": request.execution_id})
        if request.proposal_id != proposal.proposal_id or request.decision_id != decision.decision_id:
            return self._reject(request, "request does not match proposal/decision")
        if decision.proposal_id != proposal.proposal_id:
            return self._reject(request, "decision does not match proposal")
        if decision.status != "approved":
            return self._reject(request, "human approval required")
        if not decision.decided_by:
            return self._reject(request, "decision authority missing")
        if not proposal.actions:
            return self._reject(request, "proposal contains no action")
        result = ExecutionResult(
            result_id=f"result-{request.execution_id}",
            execution_id=request.execution_id,
            proposal_id=proposal.proposal_id,
            decision_id=decision.decision_id,
            status="succeeded",
            details={"actions": list(proposal.actions)},
        )
        self.audit_log.append({"type": "execution_result", "result_id": result.result_id, "execution_id": request.execution_id, "status": result.status})
        return result

    def _reject(self, request: ExecutionRequest, reason: str) -> ExecutionResult:
        result = ExecutionResult(
            result_id=f"result-{request.execution_id}",
            execution_id=request.execution_id,
            proposal_id=request.proposal_id,
            decision_id=request.decision_id,
            status="rejected",
            details={"reason": reason},
        )
        self.audit_log.append({"type": "execution_result", "result_id": result.result_id, "execution_id": request.execution_id, "status": result.status, "reason": reason})
        return result


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
