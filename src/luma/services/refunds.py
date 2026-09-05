from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from luma.db.models.billing import Payment, Refund


class RefundValidationError(ValueError):
    """The requested refund violates the payment contract."""


async def create_pending_refund(
    session: AsyncSession,
    *,
    payment_id: UUID,
    public_reference: str,
    amount_cents: int,
    reason_code: str,
    idempotency_key: str,
) -> Refund:
    """Validate and reserve refundable value while holding the payment row lock."""

    existing = await session.scalar(select(Refund).where(Refund.idempotency_key == idempotency_key))
    if existing is not None:
        if (
            existing.payment_id != payment_id
            or existing.amount_cents != amount_cents
            or existing.reason_code != reason_code
        ):
            raise RefundValidationError("idempotency key was reused for a different refund")
        return existing

    if amount_cents <= 0:
        raise RefundValidationError("refund amount must be positive")

    payment = await session.scalar(
        select(Payment).where(Payment.id == payment_id).with_for_update()
    )
    if payment is None:
        raise RefundValidationError("payment does not exist")
    if payment.captured_amount_cents <= 0 or payment.status in {"created", "authorized", "voided"}:
        raise RefundValidationError("payment has no captured funds to refund")

    reserved_cents = await session.scalar(
        select(func.coalesce(func.sum(Refund.amount_cents), 0)).where(
            Refund.payment_id == payment_id,
            Refund.status.in_(("pending", "succeeded")),
        )
    )
    refundable_cents = payment.captured_amount_cents - int(reserved_cents or 0)
    if amount_cents > refundable_cents:
        raise RefundValidationError(
            f"refund amount exceeds remaining refundable amount ({refundable_cents} cents)"
        )

    refund = Refund(
        public_reference=public_reference,
        payment_id=payment_id,
        amount_cents=amount_cents,
        status="pending",
        reason_code=reason_code,
        idempotency_key=idempotency_key,
    )
    session.add(refund)
    await session.flush()
    return refund
