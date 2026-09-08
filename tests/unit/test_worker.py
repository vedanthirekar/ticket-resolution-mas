from luma.agents.models import StructuredOutputError
from luma.domain.cases import FailureKind
from luma.worker import _failure_kind


def test_worker_retries_provider_and_transport_failures() -> None:
    assert _failure_kind(TimeoutError("request timed out")) is FailureKind.TRANSIENT
    assert _failure_kind(RuntimeError("503 temporarily unavailable")) is FailureKind.TRANSIENT
    assert _failure_kind(RuntimeError("429 quota exceeded")) is FailureKind.TRANSIENT
    assert _failure_kind(StructuredOutputError("invalid model output")) is FailureKind.TRANSIENT


def test_worker_does_not_retry_contract_failures() -> None:
    assert _failure_kind(ValueError("invalid case contract")) is FailureKind.PERMANENT
