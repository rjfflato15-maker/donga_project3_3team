"""Shared input contract for direct reviews and final approval stages."""
from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    review_cycle: int | None = None
    submission_event_id: int | None = None
    decision: str
    note: str = Field(min_length=1, max_length=2000)
    revision: int
    fingerprint: str
    acknowledge_unverified: bool = False
