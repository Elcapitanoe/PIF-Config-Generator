from datetime import date
from enum import Enum
from typing import Dict, List, Optional

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


class GeneratorMetadata(BaseModel):
    name: str
    repository: str
    version: str
    commit: Optional[str] = None
    workflow_run_url: Optional[str] = None


class ReleaseMetadata(BaseModel):
    tag: str
    name: str
    url: str
    published_at: Optional[str] = None
    prerelease: bool = False


class ReleaseIndexFile(BaseModel):
    filename: str
    url: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    content_type: str
    channel: Optional[str] = None
    codename: Optional[str] = None
    device_name: Optional[str] = None
    manufacturer: Optional[str] = None


class ChannelReleaseIndex(BaseModel):
    release: ReleaseMetadata
    files: List[ReleaseIndexFile]


class ReleaseIndex(BaseModel):
    schema_version: int = 2
    generator: GeneratorMetadata
    channels: Dict[str, ChannelReleaseIndex]


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
    spoofProps: str = Field(default="1")
    spoofProvider: str = Field(default="0")
    spoofSignature: str = Field(default="0")
    spoofVendingSdk: str = Field(default="0")
    spoofVendingBuild: str = Field(default="1")
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
