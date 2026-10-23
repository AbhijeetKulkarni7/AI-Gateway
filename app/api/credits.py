from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_principal
from app.credits.service import deduct_credits, get_remaining_credits
from app.database import get_db
from app.models import Principal
from datetime import datetime

from app.models import CreditRequest
from app.schemas import CreditApproval, CreditRequestCreate


router = APIRouter(
    prefix="/v1/credits",
    tags=["Credits"],
)


@router.get("/balance")
def get_balance(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    account = principal.credit_account

    if account is None:
        return {
            "allocated_credits": "0.0000",
            "used_credits": "0.0000",
            "remaining_credits": "0.0000",
            "status": "not_configured",
        }

    remaining = get_remaining_credits(account)

    return {
        "principal_id": principal.id,
        "allocated_credits": str(
            account.allocated_credits
        ),
        "used_credits": str(
            account.used_credits
        ),
        "remaining_credits": str(
            remaining
        ),
        "status": account.status,
    }


@router.post("/debug/spend")
def debug_spend(
    amount: float,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    account = principal.credit_account

    if account is None:
        raise HTTPException(
            status_code=404,
            detail="Credit account not found",
        )

    updated_account = deduct_credits(
        db=db,
        account=account,
        amount=Decimal(str(amount)),
        reason="Debug/test usage",
        reference_id="debug-request",
    )

    remaining = get_remaining_credits(updated_account)

    return {
        "spent": str(amount),
        "remaining_credits": str(remaining),
    }

@router.post("/requests")
def create_credit_request(
    request_data: CreditRequestCreate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    credit_request = CreditRequest(
        principal_id=principal.id,
        requested_amount=Decimal(str(request_data.requested_amount)),
        reason=request_data.reason,
        status="pending",
    )

    db.add(credit_request)
    db.commit()
    db.refresh(credit_request)

    return {
        "request_id": credit_request.id,
        "requested_amount": str(credit_request.requested_amount),
        "reason": credit_request.reason,
        "status": credit_request.status,
        "message": "Credit request submitted to administrator.",
    }

@router.get("/requests")
def get_my_credit_requests(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    requests = (
        db.query(CreditRequest)
        .filter(CreditRequest.principal_id == principal.id)
        .order_by(CreditRequest.created_at.desc())
        .all()
    )

    return [
        {
            "request_id": request.id,
            "requested_amount": str(request.requested_amount),
            "approved_amount": (
                str(request.approved_amount)
                if request.approved_amount is not None
                else None
            ),
            "reason": request.reason,
            "status": request.status,
            "created_at": request.created_at,
            "processed_at": request.processed_at,
        }
        for request in requests
    ]
