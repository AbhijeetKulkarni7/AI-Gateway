from datetime import datetime, timezone
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from decimal import Decimal

from sqlalchemy import case, func
from app.models import UsageRecord
from app.credits.service import create_credit_account
from app.auth.api_keys import generate_api_key
from app.config import settings
from app.database import get_db
from app.models import ApiKey, Principal, Team
from datetime import datetime
from decimal import Decimal

from app.credits.service import add_credits
from app.models import CreditRequest
from app.schemas import CreditApproval

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


def require_admin(
    x_admin_key: str | None,
):
    #print("DEBUG received:", repr(x_admin_key))
    #print("DEBUG expected:", repr(settings.admin_api_key))

    if x_admin_key is None:
        raise HTTPException(
            status_code=401,
            detail="Missing admin key",
        )

    if x_admin_key != settings.admin_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid admin key",
        )





@router.get("/usage")
def get_usage(
    x_admin_key: str | None = Header(
        default=None,
        alias="X-Admin-Key",
    ),
    db: Session = Depends(get_db),
):
    require_admin(x_admin_key)

    # ---------------------------------------------------------
    # User-wise usage
    # ---------------------------------------------------------

    user_usage = (
        db.query(
            UsageRecord.principal_id,
            Principal.name.label("user_name"),
            Team.name.label("team_name"),
            func.count(UsageRecord.id).label("request_count"),
            func.coalesce(
                func.sum(UsageRecord.prompt_tokens),
                0,
            ).label("prompt_tokens"),
            func.coalesce(
                func.sum(UsageRecord.completion_tokens),
                0,
            ).label("completion_tokens"),
            func.coalesce(
                func.sum(UsageRecord.total_tokens),
                0,
            ).label("total_tokens"),
            func.coalesce(
                func.sum(UsageRecord.estimated_cost),
                0,
            ).label("total_cost"),
        )
        .join(
            Principal,
            UsageRecord.principal_id == Principal.id,
        )
        .outerjoin(
            Team,
            UsageRecord.team_id == Team.id,
        )
        .group_by(
            UsageRecord.principal_id,
            Principal.name,
            Team.name,
        )
        .order_by(
            func.sum(UsageRecord.total_tokens).desc()
        )
        .all()
    )




    # ---------------------------------------------------------
    # Team-wise usage
    # ---------------------------------------------------------

    team_usage = (
        db.query(
            UsageRecord.team_id,
            Team.name.label("team_name"),
            func.count(UsageRecord.id).label("request_count"),
            func.coalesce(
                func.sum(UsageRecord.prompt_tokens),
                0,
            ).label("prompt_tokens"),
            func.coalesce(
                func.sum(UsageRecord.completion_tokens),
                0,
            ).label("completion_tokens"),
            func.coalesce(
                func.sum(UsageRecord.total_tokens),
                0,
            ).label("total_tokens"),
            func.coalesce(
                func.sum(UsageRecord.estimated_cost),
                0,
            ).label("total_cost"),
        )
        .outerjoin(
            Team,
            UsageRecord.team_id == Team.id,
        )
        .group_by(
            UsageRecord.team_id,
            Team.name,
        )
        .order_by(
            func.sum(UsageRecord.total_tokens).desc()
        )
        .all()
    )

    model_usage = (
        db.query(
            UsageRecord.provider,
            UsageRecord.model,
            func.count(UsageRecord.id).label("request_count"),
            func.coalesce(
                func.sum(UsageRecord.prompt_tokens), 0
            ).label("prompt_tokens"),
            func.coalesce(
                func.sum(UsageRecord.completion_tokens), 0
            ).label("completion_tokens"),
            func.coalesce(
                func.sum(UsageRecord.total_tokens), 0
            ).label("total_tokens"),
            func.coalesce(
                func.sum(UsageRecord.estimated_cost), 0
            ).label("total_cost"),
        )
        .group_by(
            UsageRecord.provider,
            UsageRecord.model,
        )
        .order_by(
            func.sum(UsageRecord.total_tokens).desc()
        )
        .all()
    )

#=========================================================================================
#                     DAILY USAGE                                                        ||
#========================================================================================
    daily_usage = (
        db.query(
            func.date(UsageRecord.created_at).label("usage_date"),
            func.count(UsageRecord.id).label("request_count"),
            func.coalesce(
                func.sum(UsageRecord.prompt_tokens), 0
            ).label("prompt_tokens"),
            func.coalesce(
                func.sum(UsageRecord.completion_tokens), 0
            ).label("completion_tokens"),
            func.coalesce(
                func.sum(UsageRecord.total_tokens), 0
            ).label("total_tokens"),
            func.coalesce(
                func.sum(UsageRecord.estimated_cost), 0
            ).label("total_cost"),
        )
        .group_by(
            func.date(UsageRecord.created_at)
        )
        .order_by(
            func.date(UsageRecord.created_at).desc()
        )
        .all()
    )
    # ---------------------------------------------------------
    # Organization-wide totals
    # ---------------------------------------------------------

    organization_usage = db.query(
        func.count(UsageRecord.id).label(
            "request_count"
        ),
        func.coalesce(
            func.sum(UsageRecord.prompt_tokens),
            0,
        ).label("prompt_tokens"),
        func.coalesce(
            func.sum(UsageRecord.completion_tokens),
            0,
        ).label("completion_tokens"),
        func.coalesce(
            func.sum(UsageRecord.total_tokens),
            0,
        ).label("total_tokens"),
        func.coalesce(
            func.sum(UsageRecord.estimated_cost),
            0,
        ).label("total_cost"),
    ).first()

    return {
        "organization": {
            "request_count": organization_usage.request_count,
            "prompt_tokens": organization_usage.prompt_tokens,
            "completion_tokens": organization_usage.completion_tokens,
            "total_tokens": organization_usage.total_tokens,
            "total_cost": str(
                organization_usage.total_cost
            ),
        },

        "users": [
            {
                "principal_id": row.principal_id,
                "user_name": row.user_name,
                "team_name": row.team_name,
                "request_count": row.request_count,
                "prompt_tokens": row.prompt_tokens,
                "completion_tokens": row.completion_tokens,
                "total_tokens": row.total_tokens,
                "total_cost": str(row.total_cost),
            }
            for row in user_usage
        ],

        "teams": [
            {
                "team_id": row.team_id,
                "team_name": row.team_name,
                "request_count": row.request_count,
                "prompt_tokens": row.prompt_tokens,
                "completion_tokens": row.completion_tokens,
                "total_tokens": row.total_tokens,
                "total_cost": str(row.total_cost),
            }
            for row in team_usage
        ],

        "models": [
            {
                "provider": row.provider,
                "model": row.model,
                "request_count": row.request_count,
                "prompt_tokens": row.prompt_tokens,
                "completion_tokens": row.completion_tokens,
                "total_tokens": row.total_tokens,
                "total_cost": str(row.total_cost),
            }
            for row in model_usage
        ],
        "daily": [
                {
                    "date": str(row.usage_date),
                    "request_count": row.request_count,
                    "prompt_tokens": row.prompt_tokens,
                    "completion_tokens": row.completion_tokens,
                    "total_tokens": row.total_tokens,
                    "total_cost": str(row.total_cost),
                }
                for row in daily_usage
            ],
    }



# ============================================================
# Monitoring
# ============================================================

@router.get("/monitoring")
def get_monitoring(
    x_admin_key: str | None = Header(
        default=None,
        alias="X-Admin-Key",
    ),
    db: Session = Depends(get_db),
):
    require_admin(x_admin_key)

    # --------------------------------------------------------
    # Organization-wide monitoring
    # --------------------------------------------------------

    total_requests = (
        db.query(func.count(UsageRecord.id))
        .scalar()
        or 0
    )

    successful_requests = (
        db.query(func.count(UsageRecord.id))
        .filter(
            UsageRecord.request_status == "success"
        )
        .scalar()
        or 0
    )

    policy_blocked = (
        db.query(func.count(UsageRecord.id))
        .filter(
            UsageRecord.request_status == "policy_blocked"
        )
        .scalar()
        or 0
    )

    provider_errors = (
        db.query(func.count(UsageRecord.id))
        .filter(
            UsageRecord.request_status == "provider_error"
        )
        .scalar()
        or 0
    )

    credit_exhausted = (
        db.query(func.count(UsageRecord.id))
        .filter(
            UsageRecord.request_status == "credit_exhausted"
        )
        .scalar()
        or 0
    )

    credit_account_blocked = (
        db.query(func.count(UsageRecord.id))
        .filter(
            UsageRecord.request_status
            == "credit_account_blocked"
        )
        .scalar()
        or 0
    )

    secrets_redacted = (
        db.query(func.count(UsageRecord.id))
        .filter(
            UsageRecord.secrets_redacted.is_(True)
        )
        .scalar()
        or 0
    )

    # --------------------------------------------------------
    # Success rate
    # --------------------------------------------------------

    success_rate = (
        (successful_requests / total_requests) * 100
        if total_requests > 0
        else 0
    )

    # --------------------------------------------------------
    # User-wise monitoring
    # --------------------------------------------------------

    user_monitoring = (
        db.query(
            UsageRecord.principal_id,
            Principal.name.label("user_name"),
            Team.name.label("team_name"),

            func.count(
                UsageRecord.id
            ).label("total_requests"),

            func.sum(
                case(
                    (
                        UsageRecord.request_status
                        == "success",
                        1,
                    ),
                    else_=0,
                )
            ).label("successful"),

            func.sum(
                case(
                    (
                        UsageRecord.request_status
                        == "policy_blocked",
                        1,
                    ),
                    else_=0,
                )
            ).label("policy_blocked"),

            func.sum(
                case(
                    (
                        UsageRecord.request_status
                        == "provider_error",
                        1,
                    ),
                    else_=0,
                )
            ).label("provider_errors"),

            func.sum(
                case(
                    (
                        UsageRecord.request_status
                        == "credit_exhausted",
                        1,
                    ),
                    else_=0,
                )
            ).label("credit_exhausted"),

            func.sum(
                case(
                    (
                        UsageRecord.request_status
                        == "credit_account_blocked",
                        1,
                    ),
                    else_=0,
                )
            ).label("credit_account_blocked"),

            func.sum(
                case(
                    (
                        UsageRecord.secrets_redacted.is_(True),
                        1,
                    ),
                    else_=0,
                )
            ).label("secrets_redacted"),

            func.coalesce(
                func.sum(
                    UsageRecord.total_tokens
                ),
                0,
            ).label("total_tokens"),

            func.coalesce(
                func.sum(
                    UsageRecord.estimated_cost
                ),
                0,
            ).label("estimated_cost"),
        )
        .join(
            Principal,
            UsageRecord.principal_id
            == Principal.id,
        )
        .outerjoin(
            Team,
            UsageRecord.team_id
            == Team.id,
        )
        .group_by(
            UsageRecord.principal_id,
            Principal.name,
            Team.name,
        )
        .order_by(
            func.count(
                UsageRecord.id
            ).desc()
        )
        .all()
    )

    # --------------------------------------------------------
    # Build user response
    # --------------------------------------------------------

    users = []

    for row in user_monitoring:

        user_total = row.total_requests or 0
        user_successful = row.successful or 0

        user_success_rate = (
            (user_successful / user_total) * 100
            if user_total > 0
            else 0
        )

        users.append(
            {
                "principal_id": row.principal_id,
                "user_name": row.user_name,
                "team_name": row.team_name,

                "total_requests": user_total,
                "successful": user_successful,

                "policy_blocked": (
                    row.policy_blocked or 0
                ),

                "provider_errors": (
                    row.provider_errors or 0
                ),

                "credit_exhausted": (
                    row.credit_exhausted or 0
                ),

                "credit_account_blocked": (
                    row.credit_account_blocked or 0
                ),

                "secrets_redacted": (
                    row.secrets_redacted or 0
                ),

                "total_tokens": (
                    row.total_tokens or 0
                ),

                "estimated_cost": str(
                    row.estimated_cost or 0
                ),

                "success_rate": round(
                    user_success_rate,
                    2,
                ),
            }
        )



    # --------------------------------------------------------
    # Provider and model monitoring
    # --------------------------------------------------------

    provider_rows = (
        db.query(
            UsageRecord.provider,
            UsageRecord.model,

            func.count(
                UsageRecord.id
            ).label("total_requests"),

            func.sum(
                case(
                    (
                        UsageRecord.request_status == "success",
                        1,
                    ),
                    else_=0,
                )
            ).label("successful"),

            func.sum(
                case(
                    (
                        UsageRecord.request_status == "provider_error",
                        1,
                    ),
                    else_=0,
                )
            ).label("provider_errors"),

            func.coalesce(
                func.sum(UsageRecord.total_tokens), 0
            ).label("total_tokens"),

            func.coalesce(
                func.sum(UsageRecord.estimated_cost), 0
            ).label("estimated_cost"),
        )
        .group_by(
            UsageRecord.provider,
            UsageRecord.model,
        )
        .order_by(
            func.count(UsageRecord.id).desc()
        )
        .all()
    )

    providers = []

    for row in provider_rows:
        providers.append({
            "provider": row.provider or "unknown",
            "model": row.model or "unknown",
            "total_requests": row.total_requests or 0,
            "successful": row.successful or 0,
            "provider_errors": row.provider_errors or 0,
            "total_tokens": row.total_tokens or 0,
            "estimated_cost": str(row.estimated_cost or 0),
        })



    # --------------------------------------------------------
    # Daily trends: last 30 days
    # --------------------------------------------------------

    cutoff = datetime.utcnow() - timedelta(days=30)

    daily_rows = (
        db.query(
            func.date(
                UsageRecord.created_at
            ).label("date"),

            func.count(
                UsageRecord.id
            ).label("total_requests"),

            func.sum(
                case(
                    (
                        UsageRecord.request_status == "success",
                        1,
                    ),
                    else_=0,
                )
            ).label("successful"),

            func.sum(
                case(
                    (
                        UsageRecord.request_status == "provider_error",
                        1,
                    ),
                    else_=0,
                )
            ).label("provider_errors"),

            func.sum(
                case(
                    (
                        UsageRecord.request_status == "policy_blocked",
                        1,
                    ),
                    else_=0,
                )
            ).label("policy_blocked"),
        )
        .filter(
            UsageRecord.created_at >= cutoff
        )
        .group_by(
            func.date(UsageRecord.created_at)
        )
        .order_by(
            func.date(UsageRecord.created_at)
        )
        .all()
    )

    daily_trends = []

    for row in daily_rows:
        daily_trends.append({
            "date": str(row.date),
            "total_requests": row.total_requests or 0,
            "successful": row.successful or 0,
            "provider_errors": row.provider_errors or 0,
            "policy_blocked": row.policy_blocked or 0,
        })



    # --------------------------------------------------------
    # Return monitoring data
    # --------------------------------------------------------

    return {
        "organization": {
            "total_requests": total_requests,
            "successful": successful_requests,
            "policy_blocked": policy_blocked,
            "provider_errors": provider_errors,
            "credit_exhausted": credit_exhausted,
            "credit_account_blocked": (
                credit_account_blocked
            ),
            "secrets_redacted": secrets_redacted,
            "success_rate": round(
                success_rate,
                2,
            ),
        },

        "users": users,
        "providers": providers,
        "daily_trends": daily_trends,
    }







@router.get("/principals")
def get_principals(
    page: int = 1,
    page_size: int = 10,
    search: str | None = None,
    x_admin_key: str | None = Header(
        default=None,
        alias="X-Admin-Key",
    ),
    db: Session = Depends(get_db),
):
    require_admin(x_admin_key)

    # ---------------------------------------------------------
    # Validate pagination
    # ---------------------------------------------------------

    if page < 1:
        raise HTTPException(
            status_code=400,
            detail="Page must be greater than or equal to 1.",
        )

    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=400,
            detail="Page size must be between 1 and 100.",
        )

    # ---------------------------------------------------------
    # Base query
    # ---------------------------------------------------------

    query = db.query(Principal)

    # ---------------------------------------------------------
    # Search
    #
    # Search by:
    # - name
    # - email
    # - external_id
    # ---------------------------------------------------------

    if search:
        search_value = f"%{search.strip()}%"

        query = query.filter(
            (Principal.name.ilike(search_value))
            | (Principal.email.ilike(search_value))
            | (Principal.external_id.ilike(search_value))
        )

    # ---------------------------------------------------------
    # Total matching users
    # ---------------------------------------------------------

    total = query.count()

    # ---------------------------------------------------------
    # Pagination
    # ---------------------------------------------------------

    offset = (page - 1) * page_size

    principals = (
        query
        .order_by(Principal.id.asc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    # ---------------------------------------------------------
    # Calculate total pages
    # ---------------------------------------------------------

    total_pages = (
        (total + page_size - 1) // page_size
        if total > 0
        else 0
    )

    # ---------------------------------------------------------
    # Build response
    # ---------------------------------------------------------

    result = []

    for principal in principals:

        account = principal.credit_account

        allocated = (
            account.allocated_credits
            if account
            else Decimal("0")
        )

        used = (
            account.used_credits
            if account
            else Decimal("0")
        )

        remaining = allocated - used

        result.append(
            {
                "principal_id": principal.id,
                "name": principal.name,
                "email": principal.email,
                "type": principal.type,
                "team_id": principal.team_id,
                "team_name": (
                    principal.team.name
                    if principal.team
                    else None
                ),
                "is_active": principal.is_active,
                "routing_enabled": principal.routing_enabled,
                "allocated_credits": str(allocated),
                "used_credits": str(used),
                "remaining_credits": str(remaining),
            }
        )

    # ---------------------------------------------------------
    # Return paginated response
    # ---------------------------------------------------------

    return {
        "items": result,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "search": search,
    }





@router.post("/teams")
def create_team(
    name: str,
    x_admin_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    require_admin(x_admin_key)

    existing = (
        db.query(Team)
        .filter(Team.name == name)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Team already exists",
        )

    team = Team(
        name=name,
        routing_enabled=False,
        dlp_mode="block",
    )

    db.add(team)
    db.commit()
    db.refresh(team)

    return {
        "id": team.id,
        "name": team.name,
    }



@router.get("/teams")
def get_teams(
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    db=Depends(get_db),
):
    require_admin(x_admin_key)

    teams = (
        db.query(Team)
        .order_by(Team.id.asc())
        .all()
    )

    result = []

    for team in teams:
        users = team.principals or []

        result.append(
            {
                "team_id": team.id,
                "team_name": team.name,
                "routing_enabled": team.routing_enabled,
                "dlp_mode": team.dlp_mode,
                "user_count": len(users),
                "users": [
                    {
                        "principal_id": user.id,
                        "name": user.name,
                        "email": user.email,
                        "type": user.type,
                        "is_active": user.is_active,
                    }
                    for user in users
                ],
            }
        )

    return result


@router.delete("/teams/{team_id}")
def delete_team(
    team_id: int,
    x_admin_key: str | None = Header(
        default=None,
        alias="X-Admin-Key",
    ),
    db=Depends(get_db),
):
    require_admin(x_admin_key)

    team = db.get(Team, team_id)

    if team is None:
        raise HTTPException(
            status_code=404,
            detail="Team not found",
        )

    # Do not delete a team that still has users.
    if team.principals:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot delete team because users are "
                "still assigned to this team. "
                "Move or remove the users first."
            ),
        )

    db.delete(team)
    db.commit()

    return {
        "message": "Team deleted successfully",
        "team_id": team_id,
    }

@router.get("/credit-requests")
def get_credit_requests(
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
):
    require_admin(x_admin_key)

    requests = (
        db.query(CreditRequest)
        .order_by(CreditRequest.created_at.desc())
        .all()
    )

    return [
        {
            "request_id": request.id,
            "principal_id": request.principal_id,
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

@router.post("/credit-requests/{request_id}/approve")
def approve_credit_request(
    request_id: int,
    approval: CreditApproval,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
):
    require_admin(x_admin_key)

    credit_request = db.get(CreditRequest, request_id)

    if credit_request is None:
        raise HTTPException(
            status_code=404,
            detail="Credit request not found",
        )

    if credit_request.status != "pending":
        raise HTTPException(
            status_code=400,
            detail="Only pending credit requests can be approved.",
        )

    principal = db.get(Principal, credit_request.principal_id)

    if principal is None:
        raise HTTPException(
            status_code=404,
            detail="Principal not found",
        )

    account = principal.credit_account

    if account is None:
        raise HTTPException(
            status_code=404,
            detail="Credit account not found",
        )

    approved_amount = (
        Decimal(str(approval.approved_amount))
        if approval.approved_amount is not None
        else Decimal("100.00")
    )

    add_credits(
        db=db,
        account=account,
        amount=approved_amount,
        reason=f"Approved credit request #{credit_request.id}",
        approved_by=x_admin_key,
    )

    credit_request.status = "approved"
    credit_request.approved_amount = approved_amount
    credit_request.approved_by = "admin"
    credit_request.processed_at = datetime.utcnow()

    db.commit()
    db.refresh(credit_request)

    return {
        "request_id": credit_request.id,
        "status": credit_request.status,
        "requested_amount": str(credit_request.requested_amount),
        "approved_amount": str(credit_request.approved_amount),
        "message": "Credits approved and added to the user's account.",
    }

@router.post("/credit-requests/{request_id}/reject")
def reject_credit_request(
    request_id: int,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
):
    require_admin(x_admin_key)

    credit_request = db.get(CreditRequest, request_id)

    if credit_request is None:
        raise HTTPException(
            status_code=404,
            detail="Credit request not found",
        )

    if credit_request.status != "pending":
        raise HTTPException(
            status_code=400,
            detail="Only pending credit requests can be rejected.",
        )

    credit_request.status = "rejected"
    credit_request.approved_by = "admin"
    credit_request.processed_at = datetime.utcnow()

    db.commit()
    db.refresh(credit_request)

    return {
        "request_id": credit_request.id,
        "status": credit_request.status,
        "message": "Credit request rejected.",
    }

@router.post("/principals")
def create_principal(
    team_id: int,
    name: str,
    principal_type: str = "user",
    email: str | None = None,
    initial_credits: float = 200.0,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
):
    require_admin(x_admin_key)

    team = db.get(Team, team_id)

    if team is None:
        raise HTTPException(
            status_code=404,
            detail="Team not found",
        )

    principal = Principal(
        type=principal_type,
        name=name,
        email=email,
        team_id=team_id,
        is_active=True,
        routing_enabled=True,
    )

    db.add(principal)
    db.commit()
    db.refresh(principal)

    create_credit_account(
        db=db,
        principal=principal,
        initial_amount=Decimal(str(initial_credits)),
    )

    return {
        "principal_id": principal.id,
        "name": principal.name,
        "team_id": principal.team_id,
        "initial_credits": str(initial_credits),
    }

@router.post("/principals/{principal_id}/keys")
def issue_api_key(
    principal_id: int,
    x_admin_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    require_admin(x_admin_key)

    principal = (
        db.query(Principal)
        .filter(Principal.id == principal_id)
        .first()
    )

    if principal is None:
        raise HTTPException(
            status_code=404,
            detail="Principal not found",
        )

    raw_key, prefix, key_hash = generate_api_key()

    api_key = ApiKey(
        principal_id=principal.id,
        prefix=prefix,
        key_hash=key_hash,
    )

    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return {
        "id": api_key.id,
        "api_key": raw_key,
        "warning": "Store this key securely. It will not be shown again.",
    }


@router.delete("/keys/{key_id}")
def revoke_api_key(
    key_id: int,
    x_admin_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    require_admin(x_admin_key)

    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.id == key_id)
        .first()
    )

    if api_key is None:
        raise HTTPException(
            status_code=404,
            detail="API key not found",
        )

    api_key.revoked_at = datetime.now(timezone.utc).replace(
        tzinfo=None
    )

    db.commit()

    return {
        "message": "API key revoked",
        "key_id": key_id,
    }