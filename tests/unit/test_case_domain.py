from __future__ import annotations

from luma.domain.cases import ALLOWED_CASE_TRANSITIONS, CaseStatus
from luma.services.auth import hash_password, verify_password


def test_case_lifecycle_has_no_customer_wait_state() -> None:
    assert "waiting_for_customer" not in {status.value for status in CaseStatus}
    assert CaseStatus.PROCESSING in ALLOWED_CASE_TRANSITIONS[CaseStatus.QUEUED]
    assert CaseStatus.HUMAN_INVESTIGATION in ALLOWED_CASE_TRANSITIONS[CaseStatus.PROCESSING]
    assert CaseStatus.RESOLVED in ALLOWED_CASE_TRANSITIONS[CaseStatus.HUMAN_INVESTIGATION]
    assert ALLOWED_CASE_TRANSITIONS[CaseStatus.RESOLVED] == frozenset()


def test_password_hash_is_salted_and_verifiable() -> None:
    first = hash_password("a-secure-test-password")
    second = hash_password("a-secure-test-password")

    assert first != second
    assert verify_password("a-secure-test-password", first)
    assert not verify_password("wrong-password", first)
