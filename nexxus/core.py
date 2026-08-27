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
    request_id: str
    proposal_id: str
    decision_id: str
    requested_by: str


@dataclass(frozen=True)
class ExecutionResult:
    request_id: str
    status: Literal["executed", "rejected"]
    details: dict[str, Any]


@dataclass
class Core:
    audit_log: list[dict[str, Any]] = field(default_factory=list)

    def execute(self, request: ExecutionRequest, proposal: ResolutionProposal, decision: HumanDecision) -> ExecutionResult:
        self.audit_log.append({"type": "execution_request", "request_id": request.request_id})

        if request.proposal_id != proposal.proposal_id or request.decision_id != decision.decision_id:
            return self._reject(request, "request does not match proposal/decision")
        if decision.status != "approved":
            return self._reject(request, "human approval required")
        if not decision.decided_by:
            return self._reject(request, "decision authority missing")
        if not proposal.actions:
            return self._reject(request, "proposal contains no action")

        result = ExecutionResult(request.request_id, "executed", {"actions": list(proposal.actions)})
        self.audit_log.append({"type": "execution_result", "request_id": request.request_id, "status": result.status})
        return result

    def _reject(self, request: ExecutionRequest, reason: str) -> ExecutionResult:
        result = ExecutionResult(request.request_id, "rejected", {"reason": reason})
        self.audit_log.append({"type": "execution_result", "request_id": request.request_id, "status": result.status, "reason": reason})
        return result


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
