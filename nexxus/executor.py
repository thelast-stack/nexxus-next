from .core import ExecutionResult, ExecutionRequest


def simulate_success(result: ExecutionResult) -> ExecutionResult:
    return ExecutionResult(result.result_id, result.execution_id, result.proposal_id, result.decision_id, "succeeded", result.details)


def simulate_failure(result: ExecutionResult) -> ExecutionResult:
    return ExecutionResult(result.result_id, result.execution_id, result.proposal_id, result.decision_id, "failed", {"reason": "simulated executor failure"})
