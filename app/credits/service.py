from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session
from decimal import Decimal, InvalidOperation


from app.models import (
    CreditAccount,
    CreditTransaction,
    Principal,
)

def get_provider_cost(response):
    usage = getattr(response, "usage", None)

    if usage is None:
        return Decimal("0")

    estimated_cost = getattr(
        usage,
        "estimated_cost",
        None,
    )

    if estimated_cost is None:
        return Decimal("0")

    return Decimal(str(estimated_cost))

    

def create_credit_account(
    db: Session,
    principal: Principal,
    initial_amount: Decimal = Decimal("0.00"),
):
    account = CreditAccount(
        principal_id=principal.id,
        allocated_credits=initial_amount,
        used_credits=Decimal("0.00"),
        status="active",
    )

    db.add(account)

    if initial_amount > 0:
        transaction = CreditTransaction(
            account=account,
            transaction_type="allocation",
            amount=initial_amount,
            reason="Initial credit allocation",
        )

        db.add(transaction)

    db.commit()
    db.refresh(account)

    return account

def get_remaining_credits(
    account: CreditAccount,
) -> Decimal:

    return (
        account.allocated_credits
        - account.used_credits
    )

def check_credit_available(account, estimated_cost):
    if account.status == "blocked":
        raise HTTPException(
            status_code=403,
            detail={
                "code": "CREDIT_ACCOUNT_BLOCKED",
                "message": "Credit account is blocked by the administrator.",
            },
        )

    remaining = get_remaining_credits(account)

    if remaining < estimated_cost:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "CREDIT_EXHAUSTED",
                "message": (
                    "Insufficient credits. "
                    "Please request additional credits from the administrator."
                ),
                "remaining_credits": str(remaining),
                "estimated_cost": str(estimated_cost),
            },
        )

def deduct_credits(
    db,
    account,
    amount,
    reason,
    reference_id=None,
):
    if amount <= 0:
        raise ValueError("Credit deduction must be greater than zero.")

    check_credit_available(account, amount)

    account.used_credits += amount

    # Mark account as exhausted when no credits remain
    if get_remaining_credits(account) <= 0:
        account.status = "exhausted"

    transaction = CreditTransaction(
        account_id=account.id,
        transaction_type="usage",
        amount=-amount,
        reason=reason,
        reference_id=reference_id,
    )

    db.add(transaction)
    db.commit()
    db.refresh(account)

    return account

    
def add_credits(
    db: Session,
    account: CreditAccount,
    amount: Decimal,
    reason: str,
    approved_by: str,
):
    if amount <= 0:
        raise ValueError(
            "Credit allocation must be greater than zero."
        )

    account.allocated_credits += amount

    account.status = "active"

    transaction = CreditTransaction(
        account_id=account.id,
        transaction_type="allocation",
        amount=amount,
        reason=reason,
        reference_id=None,
    )

    db.add(transaction)
    db.commit()
    db.refresh(account)

    return account