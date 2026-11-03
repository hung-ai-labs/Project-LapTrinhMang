from pydantic import BaseModel, ConfigDict, Field

from app.schemas.geography import ProvinceOut, WardOut


class SaveAddressInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    ward_id: str = Field(min_length=1, max_length=20)
    address_text: str | None = Field(default=None, max_length=500)


class SavedAddressOut(BaseModel):
    address_text: str | None
    ward: WardOut | None
    province: ProvinceOut | None
