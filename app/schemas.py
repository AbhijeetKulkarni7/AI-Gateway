from pydantic import BaseModel, Field


class CreditRequestCreate(BaseModel):
    requested_amount: float = Field(gt=0)
    reason: str | None = None


class CreditApproval(BaseModel):
    approved_amount: float | None = Field(default=None, gt=0)