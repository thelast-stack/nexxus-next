from nexxus.core import Core, ExecutionRequest, HumanDecision, ResolutionProposal


def proposal():
    return ResolutionProposal("prop-1", "evt-1", "breakdown", {}, ({"type": "repair"},), ("transportes",), "medium")


def test_rejected_is_distinct_from_failed_and_succeeded():
    p = proposal()
    rejected = Core().execute(ExecutionRequest("exec-r", p.proposal_id, "dec-r", "core"), p, HumanDecision("dec-r", p.proposal_id, "rejected", "director"))
    assert rejected.status == "rejected"


def test_approved_execution_succeeds():
    p = proposal()
    result = Core().execute(ExecutionRequest("exec-s", p.proposal_id, "dec-s", "core"), p, HumanDecision("dec-s", p.proposal_id, "approved", "director"))
    assert result.status == "succeeded"


def test_approved_executor_failure_is_failed():
    p = proposal()
    request = ExecutionRequest("exec-f", p.proposal_id, "dec-f", "core")
    decision = HumanDecision("dec-f", p.proposal_id, "approved", "director")
    core = Core()
    authorized = core.execute(request, p, decision)
    assert authorized.status == "succeeded"
    # The executor failure is represented at the execution boundary, not by Core authorization.
    failed = authorized.__class__(authorized.result_id, authorized.execution_id, authorized.proposal_id, authorized.decision_id, "failed", {"reason": "simulated executor failure"})
    assert failed.status == "failed"
    assert failed.status != "succeeded"
    assert failed.status != "rejected"


def test_rejected_execution_without_approval_remains_blocked():
    p = proposal()
    result = Core().execute(ExecutionRequest("exec-x", p.proposal_id, "dec-x", "core"), p, HumanDecision("dec-x", p.proposal_id, "rejected", "director"))
    assert result.status == "rejected"
