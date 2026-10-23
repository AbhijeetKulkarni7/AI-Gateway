from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    teams: Mapped[list["Team"]] = relationship(
        back_populates="organization",
    )

    memberships: Mapped[list["OrganizationMembership"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    policy_documents: Mapped[list["PolicyDocument"]] = relationship(
        back_populates="organization",
    )

class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    routing_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    dlp_mode: Mapped[str] = mapped_column(
        String(20),
        default="block",
        nullable=False,
    )

    principals: Mapped[list["Principal"]] = relationship(
        back_populates="team"
    )
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=True,
        index=True,
    )

    organization: Mapped["Organization | None"] = relationship(
        back_populates="teams",
    )

class Principal(Base):
    __tablename__ = "principals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    external_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id"),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    routing_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    team: Mapped["Team"] = relationship(
        back_populates="principals"
    )

    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="principal"
    )

    credit_account: Mapped["CreditAccount | None"] = relationship(
    back_populates="principal",
    uselist=False,
)

class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "principal_id",
            name="uq_organization_membership",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    principal_id: Mapped[int] = mapped_column(
        ForeignKey("principals.id"),
        nullable=False,
        index=True,
    )

    role: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    organization: Mapped["Organization"] = relationship(
        back_populates="memberships",
    )

    principal: Mapped["Principal"] = relationship()


class PolicyDocument(Base):
    __tablename__ = "policy_documents"

    __table_args__ = (
        Index(
            "ix_policy_document_scope_status",
            "scope",
            "organization_id",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    # Allowed values will be validated by the API:
    # "system" or "organization"
    scope: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # NULL for system-wide policies.
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="draft",
        nullable=False,
    )

    created_by_principal_id: Mapped[int | None] = mapped_column(
        ForeignKey("principals.id"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    organization: Mapped["Organization | None"] = relationship(
        back_populates="policy_documents",
    )

    versions: Mapped[list["PolicyDocumentVersion"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="PolicyDocumentVersion.version_number",
    )


class PolicyDocumentVersion(Base):
    __tablename__ = "policy_document_versions"

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "version_number",
            name="uq_policy_document_version",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    document_id: Mapped[int] = mapped_column(
        ForeignKey("policy_documents.id"),
        nullable=False,
        index=True,
    )

    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    content_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    # Private server-side path; never expose directly to clients.
    storage_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )

    # Extracted text will later support RAG and citations.
    extracted_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    processing_status: Mapped[str] = mapped_column(
        String(20),
        default="uploaded",
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    uploaded_by_principal_id: Mapped[int | None] = mapped_column(
        ForeignKey("principals.id"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    document: Mapped["PolicyDocument"] = relationship(
        back_populates="versions",
    )
    

class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    principal_id: Mapped[int] = mapped_column(
        ForeignKey("principals.id"),
        nullable=False,
    )

    prefix: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )

    key_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    principal: Mapped["Principal"] = relationship(
        back_populates="api_keys"
    )

class Model(Base):
    __tablename__ = "models"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    input_rate: Mapped[float] = mapped_column(
        default=1.0,
        nullable=False,
    )

    output_rate: Mapped[float] = mapped_column(
        default=1.0,
        nullable=False,
    )

    policies: Mapped[list["ModelPolicy"]] = relationship(
        back_populates="model"
    )


class ModelPolicy(Base):
    __tablename__ = "model_policies"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id"),
        nullable=False,
    )

    model_id: Mapped[int] = mapped_column(
        ForeignKey("models.id"),
        nullable=False,
    )

    effect: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    model: Mapped["Model"] = relationship(
        back_populates="policies"
    )


from decimal import Decimal

from sqlalchemy import Numeric, Text

class CreditAccount(Base):
    __tablename__ = "credit_accounts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    principal_id: Mapped[int] = mapped_column(
        ForeignKey("principals.id"),
        unique=True,
        nullable=False,
    )

    allocated_credits: Mapped[Decimal] = mapped_column(
        Numeric(20, 10),
        default=Decimal("0.0000"),
        nullable=False,
    )

    used_credits: Mapped[Decimal] = mapped_column(
        Numeric(20, 10),
        default=Decimal("0.0000"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False,
    )

    principal: Mapped["Principal"] = relationship(
        back_populates="credit_account"
    )

    transactions: Mapped[list["CreditTransaction"]] = relationship(
        back_populates="account"
    )

class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    account_id: Mapped[int] = mapped_column(
        ForeignKey("credit_accounts.id"),
        nullable=False,
    )

    transaction_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 10),
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    reference_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    account: Mapped["CreditAccount"] = relationship(
        back_populates="transactions"
    )

class CreditRequest(Base):
    __tablename__ = "credit_requests"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    principal_id: Mapped[int] = mapped_column(
        ForeignKey("principals.id"),
        nullable=False,
    )

    requested_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=True,
    )

    approved_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
    )

    approved_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
class UsageRecord(Base):
    __tablename__ = "usage_records"

    id = Column(Integer, primary_key=True, index=True)

    principal_id = Column(
        Integer,
        ForeignKey("principals.id"),
        nullable=False,
        index=True,
    )

    team_id = Column(
        Integer,
        ForeignKey("teams.id"),
        nullable=True,
        index=True,
    )

    provider = Column(
        String(100),
        nullable=True,
    )

    model = Column(
        String(255),
        nullable=True,
    )

    prompt_tokens = Column(
        Integer,
        default=0,
        nullable=False,
    )

    completion_tokens = Column(
        Integer,
        default=0,
        nullable=False,
    )

    total_tokens = Column(
        Integer,
        default=0,
        nullable=False,
    )

    estimated_cost = Column(
        Numeric(20, 10),
        default=0,
        nullable=False,
    )

    request_status = Column(
        String(30),
        nullable=False,
    )

    dlp_blocked = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    secrets_redacted = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

