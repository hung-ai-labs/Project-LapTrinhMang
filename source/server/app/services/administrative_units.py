import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Province, Ward


class ProvinceRow(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=150)


class WardRow(ProvinceRow):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)

    province_id: str = Field(min_length=1, max_length=20)
    administrative_type: str | None = Field(default=None, min_length=1, max_length=32)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, decimal_places=5)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, decimal_places=5)

    @model_validator(mode="after")
    def validate_coordinate_pair(self) -> Self:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Latitude and longitude must both be present or absent")
        return self


class AdministrativeSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version: str = Field(min_length=1, max_length=64)
    provinces: list[ProvinceRow] = Field(min_length=1)
    wards: list[WardRow] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        province_ids = {row.id for row in self.provinces}
        ward_ids = {row.id for row in self.wards}
        if len(province_ids) != len(self.provinces) or len(ward_ids) != len(self.wards):
            raise ValueError("Duplicate administrative codes")
        if any(row.province_id not in province_ids for row in self.wards):
            raise ValueError("Ward references a province outside the snapshot")
        return self


def load_snapshot(snapshot_path: Path, manifest_path: Path) -> AdministrativeSnapshot:
    payload = snapshot_path.read_bytes()
    manifest = json.loads(manifest_path.read_text())
    if hashlib.sha256(payload).hexdigest() != manifest.get("snapshot_sha256"):
        raise ValueError("Snapshot SHA-256 does not match its manifest")
    snapshot = AdministrativeSnapshot.model_validate_json(payload)
    if manifest.get("dataset_version") != snapshot.dataset_version:
        raise ValueError("Snapshot version does not match its manifest")
    expected_counts = {"provinces": len(snapshot.provinces), "wards": len(snapshot.wards)}
    if manifest.get("counts") != expected_counts:
        raise ValueError("Snapshot record counts do not match its manifest")
    return snapshot


async def apply_snapshot(session: AsyncSession, snapshot: AdministrativeSnapshot) -> None:
    """Apply one complete catalog; the caller owns the transaction."""
    provinces = {row.id: row for row in await session.scalars(select(Province))}
    wards = {row.id: row for row in await session.scalars(select(Ward))}
    incoming_provinces = {row.id for row in snapshot.provinces}
    incoming_wards = {row.id for row in snapshot.wards}
    for row in snapshot.provinces:
        record = provinces.get(row.id)
        if record is None:
            record = Province(id=row.id)
            session.add(record)
        record.name = row.name
        record.dataset_version = snapshot.dataset_version
        record.is_active = True
    await session.flush()
    for row in snapshot.wards:
        record = wards.get(row.id)
        if record is None:
            record = Ward(id=row.id)
            session.add(record)
        for field, value in row.model_dump(exclude={"id"}).items():
            setattr(record, field, value)
        record.dataset_version = snapshot.dataset_version
        record.is_active = True
    for code, record in wards.items():
        if code not in incoming_wards:
            record.is_active = False
    for code, record in provinces.items():
        if code not in incoming_provinces:
            record.is_active = False
    await session.flush()
