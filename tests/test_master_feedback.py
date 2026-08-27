from nexxus.core import Core
from nexxus.executor import simulate_failure
from nexxus.master_ai import MasterAI
from tests.test_vertical_slice import make_flow


def test_failed_execution_is_consumed_and_generates_contextual_followup():
    event, _, proposal, decision, request = make_flow("approved")
    authorization = Core().execute(request, proposal, decision)
    failed = simulate_failure(authorization)

    master = MasterAI()
    followup = master.handle_execution_result(failed)

    assert authorization.status == "succeeded"
    assert failed.status == "failed"
    assert followup is not None
    assert followup.problem == "Execução falhou após autorização humana"
    assert followup.context["source_execution_id"] == request.execution_id
    assert followup.context["source_result_id"] == failed.result_id
    assert followup.context["source_proposal_id"] == proposal.proposal_id
    assert followup.context["source_decision_id"] == decision.decision_id
    assert followup.context["failure"]["reason"] == "simulated executor failure"
    assert followup.actions[0]["execution_id"] == request.execution_id
    assert followup.approval_required is True
    assert followup.event_id == proposal.proposal_id


def test_master_does_not_create_followup_for_success_or_rejection():
    _, _, proposal, decision, request = make_flow("approved")
    success = Core().execute(request, proposal, decision)
    rejected = make_flow("rejected")
    rejected_result = Core().execute(rejected[4], rejected[2], rejected[3])

    master = MasterAI()
    assert master.handle_execution_result(success) is None
    assert master.handle_execution_result(rejected_result) is None
