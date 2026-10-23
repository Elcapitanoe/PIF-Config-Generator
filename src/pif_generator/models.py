from datetime import date
from enum import Enum
from pydantic import BaseModel, Field, field_validator


def validate_iso_date(value: str) -> str:
    if len(value) != 10 or value[4] != "-" or value[7] != "-":
        raise ValueError(f"Invalid SECURITY_PATCH format (expected YYYY-MM-DD): {value}")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid SECURITY_PATCH date: {value}") from exc
    return value


class OutputFormat(str, Enum):
    EXTENDED = "extended"
    LEGACY = "legacy"


class ChannelType(str, Enum):
    STABLE = "stable"
    BETA = "beta"


class LegacyPIFProfile(BaseModel):
    MANUFACTURER: str = Field(..., min_length=1)
    MODEL: str = Field(..., min_length=1)
    FINGERPRINT: str = Field(..., min_length=1)
    BRAND: str = Field(..., min_length=1)
    PRODUCT: str = Field(..., min_length=1)
    DEVICE: str = Field(..., min_length=1)
    SECURITY_PATCH: str = Field(..., min_length=1)
    FIRST_API_LEVEL: str = Field(..., min_length=1)

    @field_validator("FIRST_API_LEVEL")
    @classmethod
    def validate_api_level(cls, v: str) -> str:
        if not v.isdigit() or int(v) < 21:
            raise ValueError(f"Invalid FIRST_API_LEVEL (must be integer >= 21): {v}")
        return v

    @field_validator("SECURITY_PATCH")
    @classmethod
    def validate_security_patch(cls, v: str) -> str:
        return validate_iso_date(v)


class ExtendedPIFProfile(BaseModel):
    ID: str = Field(..., min_length=1)
    BRAND: str = Field(..., min_length=1)
    DEVICE: str = Field(..., min_length=1)
    MANUFACTURER: str = Field(..., min_length=1)
    FINGERPRINT: str = Field(..., min_length=1)
    MODEL: str = Field(..., min_length=1)
    PRODUCT: str = Field(..., min_length=1)
    SECURITY_PATCH: str = Field(..., min_length=1)
    DEVICE_INITIAL_SDK_INT: str = Field(..., min_length=1)
    TYPE: str = Field(default="user")
    TAG: str = Field(default="release-keys")
    RELEASE: str = Field(..., min_length=1)
    DEBUG: bool = Field(default=False)
    spoofBuild: str = Field(default="1")
    spoofProps: str = Field(default="0")
    spoofProvider: str = Field(default="0")
    spoofSignature: str = Field(default="0")
    spoofVendingSdk: str = Field(default="0")
    verboseLogs: str = Field(default="0")

    @field_validator("DEVICE_INITIAL_SDK_INT")
    @classmethod
    def validate_initial_sdk(cls, v: str) -> str:
        if not v.isdigit() or int(v) < 21:
            raise ValueError(f"Invalid DEVICE_INITIAL_SDK_INT (must be integer >= 21): {v}")
        return v

    @field_validator("SECURITY_PATCH")
    @classmethod
    def validate_security_patch(cls, v: str) -> str:
        return validate_iso_date(v)
