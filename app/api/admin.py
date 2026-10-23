import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.api_keys import generate_api_key
from app.config import settings
from app.credits.service import add_credits, create_credit_account
from app.database import get_db
from app.models import (
    ApiKey,
    CreditRequest,
    Organization,
    OrganizationMembership,
    Principal,
    Team,
    UsageRecord,
)
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


# ============================================================
# Organization management schemas
# ============================================================

class OrganizationCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    slug: str = Field(min_length=2, max_length=100)


class OrganizationMembershipCreateRequest(BaseModel):
    principal_id: int = Field(gt=0)
    role: str = "org_viewer"


class PrincipalTeamUpdateRequest(BaseModel):
    team_id: int = Field(gt=0)


class PrincipalUpsertRequest(BaseModel):
    """Shared organization-scoped payload for platform-admin create/update."""
    organization_id: int = Field(gt=0)
    team_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=255)
    membership_role: str = "org_viewer"
    # Used as the initial allocation on create. For updates, the existing
    # allocation must be echoed unchanged; credit adjustments stay in Credits.
    initial_credits: Decimal | None = Field(default=Decimal("200.00"), ge=0)


class MembershipRoleUpdateRequest(BaseModel):
    role: str


class PrincipalStatusRequest(BaseModel):
    is_active: bool


# ============================================================
# Shared validation helpers for platform-admin user management
# ============================================================


def _resolve_org_team(db: Session, organization_id: int, team_id: int):
    organization = db.get(Organization, organization_id)
    if organization is None or not organization.is_active:
        raise HTTPException(status_code=404, detail="Active organization not found.")

    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found.")
    if team.organization_id != organization_id:
        raise HTTPException(
            status_code=409,
            detail="The selected team does not belong to the selected organization.",
        )
    return organization, team


def _validate_membership_role(role: str) -> str:
    if role not in {"org_admin", "org_viewer"}:
        raise HTTPException(
            status_code=422,
            detail="Membership role must be 'org_admin' or 'org_viewer'.",
        )
    return role


def _ensure_not_last_active_org_admin(
    db: Session,
    organization_id: int,
    membership: OrganizationMembership | None,
):
    if membership is None or not membership.is_active or membership.role != "org_admin":
        return
    active_admin_count = (
        db.query(func.count(OrganizationMembership.id))
        .join(Principal, Principal.id == OrganizationMembership.principal_id)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.role == "org_admin",
            OrganizationMembership.is_active.is_(True),
            Principal.is_active.is_(True),
        )
        .scalar()
        or 0
    )
    if active_admin_count <= 1:
        raise HTTPException(
            status_code=409,
            detail="Cannot revoke or deactivate the last active org_admin. Assign another org_admin first.",
        )


def _validate_email_available(
    db: Session,
    organization_id: int,
    email: str | None,
    exclude_principal_id: int | None = None,
):
    if not email:
        return
    query = (
        db.query(Principal)
        .join(Team, Principal.team_id == Team.id)
        .filter(
            Team.organization_id == organization_id,
            func.lower(Principal.email) == email.lower(),
        )
    )
    if exclude_principal_id is not None:
        query = query.filter(Principal.id != exclude_principal_id)
    if query.first():
        raise HTTPException(
            status_code=409,
            detail="A user with this email already exists in the organization.",
        )


# ============================================================
# Platform-admin organization management
# These endpoints require the existing platform admin key.
# ============================================================

@router.post("/organizations", status_code=201)
def create_organization(
    request: OrganizationCreateRequest,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
):
    require_admin(x_admin_key)

    name = request.name.strip()
    slug = request.slug.strip().lower()

    if not name:
        raise HTTPException(status_code=422, detail="Organization name is required.")

    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise HTTPException(
            status_code=422,
            detail="Slug must contain lowercase letters, numbers, and single hyphens only.",
        )

    existing = (
        db.query(Organization)
        .filter(
            (Organization.slug == slug)
            | (func.lower(Organization.name) == name.lower())
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="An organization with this name or slug already exists.",
        )

    organization = Organization(
        name=name,
        slug=slug,
        is_active=True,
    )
    db.add(organization)
    db.commit()
    db.refresh(organization)

    return {
        "id": organization.id,
        "name": organization.name,
        "slug": organization.slug,
        "is_active": organization.is_active,
        "created_at": organization.created_at,
    }


@router.get("/organizations")
def list_organizations(
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
):
    require_admin(x_admin_key)

    organizations = (
        db.query(Organization)
        .order_by(Organization.id.asc())
        .all()
    )

    return [
        {
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "is_active": org.is_active,
            "team_count": len(org.teams or []),
            "created_at": org.created_at,
        }
        for org in organizations
    ]


@router.get("/organizations/{organization_id}")
def get_organization(
    organization_id: int,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
):
    require_admin(x_admin_key)

    organization = db.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found.")

    memberships = (
        db.query(OrganizationMembership)
        .filter(OrganizationMembership.organization_id == organization_id)
        .order_by(OrganizationMembership.id.asc())
        .all()
    )

    return {
        "id": organization.id,
        "name": organization.name,
        "slug": organization.slug,
        "is_active": organization.is_active,
        "teams": [
            {"id": team.id, "name": team.name}
            for team in (organization.teams or [])
        ],
        "memberships": [
            {
                "id": item.id,
                "principal_id": item.principal_id,
                "principal_name": item.principal.name if item.principal else None,
                "role": item.role,
                "is_active": item.is_active,
            }
            for item in memberships
        ],
    }


@router.post("/organizations/{organization_id}/memberships", status_code=201)
def create_organization_membership(
    organization_id: int,
    request: OrganizationMembershipCreateRequest,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
):
    require_admin(x_admin_key)

    if request.role not in {"org_admin", "org_viewer"}:
        raise HTTPException(
            status_code=422,
            detail="Role must be either 'org_admin' or 'org_viewer'.",
        )

    organization = db.get(Organization, organization_id)
    if organization is None or not organization.is_active:
        raise HTTPException(status_code=404, detail="Active organization not found.")

    principal = db.get(Principal, request.principal_id)
    if principal is None or not principal.is_active:
        raise HTTPException(status_code=404, detail="Active principal not found.")

    principal_org_id = (
        principal.team.organization_id
        if principal.team is not None
        else None
    )
    if principal_org_id != organization_id:
        raise HTTPException(
            status_code=409,
            detail=(
                "The principal's team must belong to this organization "
                "before assigning an organization role."
            ),
        )

    existing = (
        db.query(OrganizationMembership)
        .filter(OrganizationMembership.principal_id == principal.id)
        .first()
    )
    if existing:
        if existing.organization_id == organization_id:
            raise HTTPException(
                status_code=409,
                detail="This principal already has a membership in the organization.",
            )
        raise HTTPException(
            status_code=409,
            detail="A principal can belong to only one organization in this prototype.",
        )

    membership = OrganizationMembership(
        organization_id=organization_id,
        principal_id=principal.id,
        role=request.role,
        is_active=True,
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)

    return {
        "id": membership.id,
        "organization_id": membership.organization_id,
        "principal_id": membership.principal_id,
        "principal_name": principal.name,
        "role": membership.role,
        "is_active": membership.is_active,
    }


@router.get("/organizations/{organization_id}/memberships")
def list_organization_memberships(
    organization_id: int,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
):
    require_admin(x_admin_key)

    organization = db.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found.")

    memberships = (
        db.query(OrganizationMembership)
        .filter(OrganizationMembership.organization_id == organization_id)
        .order_by(OrganizationMembership.id.asc())
        .all()
    )

    return [
        {
            "id": item.id,
            "principal_id": item.principal_id,
            "principal_name": item.principal.name if item.principal else None,
            "principal_email": item.principal.email if item.principal else None,
            "role": item.role,
            "is_active": item.is_active,
        }
        for item in memberships
    ]


@router.delete("/organizations/{organization_id}/memberships/{principal_id}")
def delete_organization_membership(
    organization_id: int,
    principal_id: int,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
):
    require_admin(x_admin_key)

    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.principal_id == principal_id,
        )
        .first()
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Organization membership not found.")

    _ensure_not_last_active_org_admin(db, organization_id, membership)
    db.delete(membership)
    db.commit()
    return {
        "message": "Organization membership removed.",
        "organization_id": organization_id,
        "principal_id": principal_id,
    }





@router.patch("/organizations/{organization_id}/memberships/{principal_id}")
def update_organization_membership_role(
    organization_id: int,
    principal_id: int,
    request: MembershipRoleUpdateRequest,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
):
    """Grant/demote organization-admin permission without changing chat access."""
    require_admin(x_admin_key)
    _validate_membership_role(request.role)

    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.principal_id == principal_id,
        )
        .first()
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Organization membership not found.")

    principal = db.get(Principal, principal_id)
    if principal is None:
        raise HTTPException(status_code=404, detail="Principal not found.")
    if not principal.is_active:
        raise HTTPException(status_code=409, detail="Reactivate the principal before changing its organization role.")
    if principal.team is None or principal.team.organization_id != organization_id:
        raise HTTPException(
            status_code=409,
            detail="The principal's current team must belong to this organization.",
        )

    if request.role != "org_admin":
        _ensure_not_last_active_org_admin(db, organization_id, membership)

    membership.role = request.role
    membership.is_active = True
    db.commit()
    db.refresh(membership)
    return {
        "id": membership.id,
        "organization_id": organization_id,
        "principal_id": principal_id,
        "principal_name": principal.name,
        "role": membership.role,
        "is_active": membership.is_active,
        "message": "Organization role updated. Chat access rules were not changed.",
    }


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

    principal_ids = [principal.id for principal in principals]
    membership_rows = (
        db.query(OrganizationMembership)
        .filter(OrganizationMembership.principal_id.in_(principal_ids))
        .all()
        if principal_ids else []
    )
    membership_by_principal = {row.principal_id: row for row in membership_rows}

    result = []

    for principal in principals:

        account = principal.credit_account
        membership = membership_by_principal.get(principal.id)
        organization = principal.team.organization if principal.team else None

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
                "organization_id": organization.id if organization else None,
                "organization_name": organization.name if organization else None,
                "membership_role": membership.role if membership else None,
                "membership_is_active": membership.is_active if membership else False,
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





@router.post("/teams", status_code=201)
def create_team(
    name: str,
    organization_id: int,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
):
    """Create a team only when its organization is explicitly selected."""
    require_admin(x_admin_key)

    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=422, detail="Team name is required.")

    organization = db.get(Organization, organization_id)
    if organization is None or not organization.is_active:
        raise HTTPException(status_code=404, detail="Active organization not found.")

    existing = db.query(Team).filter(Team.name == clean_name).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="A team with this name already exists. Team names must be unique.",
        )

    team = Team(
        name=clean_name,
        organization_id=organization.id,
        routing_enabled=False,
        dlp_mode="block",
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return {
        "id": team.id,
        "name": team.name,
        "organization_id": team.organization_id,
        "organization_name": organization.name,
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
                "organization_id": team.organization_id,
                "organization_name": (
                    team.organization.name if team.organization else None
                ),
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
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "This team is referenced by historical records and cannot be hard-deleted. "
                "Keep it for audit history; a future soft-delete field can archive it instead."
            ),
        )

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

@router.post("/principals", status_code=201)
def create_principal(
    request: PrincipalUpsertRequest,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
):
    """Create a principal under an organization with a selectable membership role.

    `Principal.type` stays `user`; membership permissions do not change chat login.
    """
    require_admin(x_admin_key)
    role = _validate_membership_role(request.membership_role)
    organization, team = _resolve_org_team(
        db, request.organization_id, request.team_id
    )

    clean_name = request.name.strip()
    clean_email = request.email.strip() if request.email else None
    if not clean_name:
        raise HTTPException(status_code=422, detail="Name is required.")
    if clean_email and (
        "@" not in clean_email
        or clean_email.startswith("@")
        or clean_email.endswith("@")
    ):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    _validate_email_available(db, organization.id, clean_email)

    initial_credits = (
        Decimal(str(request.initial_credits))
        if request.initial_credits is not None
        else Decimal("200.00")
    )

    principal = Principal(
        type="user",  # Keep existing chat-facing principal type unchanged.
        name=clean_name,
        email=clean_email,
        team_id=team.id,
        is_active=True,
        routing_enabled=True,
    )
    db.add(principal)
    try:
        db.flush()
        membership = OrganizationMembership(
            organization_id=organization.id,
            principal_id=principal.id,
            role=role,
            is_active=True,
        )
        db.add(membership)
        db.commit()
        db.refresh(principal)
    except Exception:
        db.rollback()
        raise

    create_credit_account(
        db=db,
        principal=principal,
        initial_amount=initial_credits,
    )

    return {
        "principal_id": principal.id,
        "name": principal.name,
        "email": principal.email,
        "type": principal.type,
        "team_id": principal.team_id,
        "team_name": team.name,
        "organization_id": organization.id,
        "organization_name": organization.name,
        "membership_role": role,
        "is_active": principal.is_active,
        "initial_credits": str(initial_credits),
    }


@router.put("/principals/{principal_id}")
def update_principal(
    principal_id: int,
    request: PrincipalUpsertRequest,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
):
    """Update user identity/team/organization/role with the same core payload as create."""
    require_admin(x_admin_key)
    principal = db.get(Principal, principal_id)
    if principal is None:
        raise HTTPException(status_code=404, detail="Principal not found.")

    role = _validate_membership_role(request.membership_role)
    organization, team = _resolve_org_team(
        db, request.organization_id, request.team_id
    )
    clean_name = request.name.strip()
    clean_email = request.email.strip() if request.email else None
    if not clean_name:
        raise HTTPException(status_code=422, detail="Name is required.")
    if clean_email and (
        "@" not in clean_email
        or clean_email.startswith("@")
        or clean_email.endswith("@")
    ):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    _validate_email_available(
        db, organization.id, clean_email, exclude_principal_id=principal.id
    )

    membership = (
        db.query(OrganizationMembership)
        .filter(OrganizationMembership.principal_id == principal.id)
        .first()
    )
    if membership is not None:
        if (
            membership.organization_id != organization.id
            or role != "org_admin"
        ):
            _ensure_not_last_active_org_admin(
                db, membership.organization_id, membership
            )

    # Keep credit accounting in the existing Credits flow. The common payload
    # echoes current allocation; do not silently modify balances through profile edit.
    requested_credits = request.initial_credits
    current_credits = (
        Decimal(str(principal.credit_account.allocated_credits))
        if principal.credit_account is not None else None
    )
    if (
        requested_credits is not None
        and current_credits is not None
        and Decimal(str(requested_credits)) != current_credits
    ):
        raise HTTPException(
            status_code=422,
            detail="Credit allocation must be changed through the Credits section, not the user profile form.",
        )

    principal.name = clean_name
    principal.email = clean_email
    principal.team_id = team.id

    if membership is None:
        membership = OrganizationMembership(
            organization_id=organization.id,
            principal_id=principal.id,
            role=role,
            is_active=True,
        )
        db.add(membership)
    else:
        membership.organization_id = organization.id
        membership.role = role
        membership.is_active = bool(principal.is_active)

    try:
        db.commit()
        db.refresh(principal)
    except Exception:
        db.rollback()
        raise

    if principal.credit_account is None:
        create_credit_account(
            db=db,
            principal=principal,
            initial_amount=(
                Decimal(str(requested_credits))
                if requested_credits is not None
                else Decimal("200.00")
            ),
        )

    return {
        "principal_id": principal.id,
        "name": principal.name,
        "email": principal.email,
        "type": principal.type,
        "team_id": principal.team_id,
        "team_name": team.name,
        "organization_id": organization.id,
        "organization_name": organization.name,
        "membership_role": membership.role,
        "is_active": principal.is_active,
        "message": "User updated. Chat-facing principal type and chat endpoint access were not changed.",
    }


@router.patch("/principals/{principal_id}/status")
def update_principal_status(
    principal_id: int,
    request: PrincipalStatusRequest,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
):
    """Activate/deactivate a user without deleting usage or credit history."""
    require_admin(x_admin_key)
    principal = db.get(Principal, principal_id)
    if principal is None:
        raise HTTPException(status_code=404, detail="Principal not found.")

    membership = (
        db.query(OrganizationMembership)
        .filter(OrganizationMembership.principal_id == principal.id)
        .first()
    )
    if not request.is_active:
        if membership is not None:
            _ensure_not_last_active_org_admin(
                db, membership.organization_id, membership
            )
            membership.is_active = False
        principal.is_active = False
        revoked_at = datetime.utcnow()
        for key in principal.api_keys or []:
            if key.revoked_at is None:
                key.revoked_at = revoked_at
    else:
        principal.is_active = True
        # Revoked keys stay revoked intentionally; issue a fresh key after reactivation.
        if membership is not None:
            membership.is_active = True

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "principal_id": principal.id,
        "is_active": principal.is_active,
        "message": (
            "User activated. Previously revoked API keys remain revoked; issue a new key."
            if request.is_active
            else "User deactivated and active API keys revoked. Usage and credit history were retained."
        ),
    }


@router.patch("/principals/{principal_id}/team")
def reassign_principal_team(
    principal_id: int,
    request: PrincipalTeamUpdateRequest,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
):
    """Reassign a principal to a team owned by an active organization.

    This is a platform-admin operation. It does not delete or recreate the
    principal, API keys, credit account, or historical usage records.
    """
    require_admin(x_admin_key)

    principal = db.get(Principal, principal_id)
    if principal is None:
        raise HTTPException(status_code=404, detail="Principal not found.")

    target_team = db.get(Team, request.team_id)
    if target_team is None:
        raise HTTPException(status_code=404, detail="Destination team not found.")

    if target_team.organization_id is None:
        raise HTTPException(
            status_code=409,
            detail="The destination team is not associated with an organization.",
        )

    target_organization = db.get(Organization, target_team.organization_id)
    if target_organization is None or not target_organization.is_active:
        raise HTTPException(
            status_code=409,
            detail="The destination team's organization is missing or inactive.",
        )

    previous_team_id = principal.team_id
    previous_team = principal.team
    previous_organization_id = (
        previous_team.organization_id if previous_team is not None else None
    )

    # Never silently transfer organization-level privileges when moving a user.
    # If the principal already has a membership in a different organization,
    # an administrator must remove that membership first.
    existing_membership = (
        db.query(OrganizationMembership)
        .filter(OrganizationMembership.principal_id == principal.id)
        .first()
    )
    if (
        existing_membership is not None
        and existing_membership.organization_id != target_team.organization_id
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "The principal already has a membership in another organization. "
                "Remove that membership before moving the principal to this team."
            ),
        )

    principal.team_id = target_team.id
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(principal)

    return {
        "message": "Principal team updated successfully.",
        "principal_id": principal.id,
        "principal_name": principal.name,
        "previous_team_id": previous_team_id,
        "previous_organization_id": previous_organization_id,
        "team_id": target_team.id,
        "team_name": target_team.name,
        "organization_id": target_organization.id,
        "organization_name": target_organization.name,
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