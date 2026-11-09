"""State of the mock payment provider (development and tests only).

These rows simulate an external provider's records. They are kept in a dedicated
``mock_provider_records`` table so mock data can never be mistaken for real data.
"""

from enum import StrEnum

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, UniqueConstraint

from app.database.base import Timestamps, UUIDPrimaryKey


class MockRecordKind(StrEnum):
    PAYMENT = "PAYMENT"
    MERCHANT = "MERCHANT"
    SETTLEMENT = "SETTLEMENT"
    CHARGEBACK = "CHARGEBACK"


class MockProviderRecord(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "mock_provider_records"
    __table_args__ = (UniqueConstraint("kind", "external_id"),)

    kind: str = Field(max_length=20)
    external_id: str = Field(max_length=100)
    data: dict[str, object] = Field(sa_type=JSONB)
