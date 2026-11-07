import io
import re
import zipfile
from dataclasses import dataclass
from typing import Dict

import requests

from .models import ExtendedPIFProfile, LegacyPIFProfile


@dataclass(frozen=True)
class _SharedBuildProperties:
    fingerprint: str
    build_id: str
    product: str
    device: str
    api_level: str
    security_patch: str


class PropParser:
    @staticmethod
    def parse(content: str) -> Dict[str, str]:
        props: Dict[str, str] = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            props[key.strip()] = val.strip()
        return props

    @staticmethod
    def extract_first(props: Dict[str, str], *keys: str, default: str = "") -> str:
        for k in keys:
            val = props.get(k, "").strip()
            if val:
                return val
        return default


class ProfileBuilder:
    _LEGACY_FINGERPRINT_KEYS = (
        "ro.system_ext.build.fingerprint",
        "ro.system.build.fingerprint",
        "ro.build.fingerprint",
        "ro.product.build.fingerprint",
        "ro.bootimage.build.fingerprint",
        "ro.vendor.build.fingerprint",
    )
    _EXTENDED_FINGERPRINT_KEYS = _LEGACY_FINGERPRINT_KEYS + ("ro.system_dlkm.build.fingerprint",)
    _LEGACY_BUILD_ID_KEYS = (
        "ro.system_ext.build.id",
        "ro.system.build.id",
        "ro.build.id",
        "ro.vendor.build.id",
    )
    _EXTENDED_BUILD_ID_KEYS = _LEGACY_BUILD_ID_KEYS + ("ro.system_dlkm.build.id",)
    _DEVICE_KEYS = (
        "ro.product.system_ext.device",
        "ro.product.system.device",
        "ro.product.device",
        "ro.build.product",
        "ro.product.board",
    )
    _API_LEVEL_KEYS = (
        "ro.product.first_api_level",
        "ro.board.first_api_level",
        "ro.board.api_level",
        "ro.system_ext.build.version.sdk",
        "ro.system.build.version.sdk",
        "ro.build.version.sdk",
    )

    @classmethod
    def _shared_build_properties(
        cls, props: Dict[str, str], *, extended: bool
    ) -> _SharedBuildProperties:
        fingerprint_keys = cls._EXTENDED_FINGERPRINT_KEYS if extended else cls._LEGACY_FINGERPRINT_KEYS
        build_id_keys = cls._EXTENDED_BUILD_ID_KEYS if extended else cls._LEGACY_BUILD_ID_KEYS
        product_keys = (
            (
                "ro.product.system_ext.name",
                "ro.product.system.name",
                "ro.product.name",
                "ro.build.product",
                "ro.product.system_ext.device",
                "ro.product.device",
                "ro.product.board",
            )
            if extended
            else (
                "ro.product.system_ext.name",
                "ro.product.system.name",
                "ro.build.product",
                "ro.product.device",
                "ro.product.name",
                "ro.product.board",
            )
        )
        fingerprint = PropParser.extract_first(props, *fingerprint_keys)
        build_id = PropParser.extract_first(props, *build_id_keys)
        product = PropParser.extract_first(props, *product_keys)
        device = PropParser.extract_first(props, *cls._DEVICE_KEYS)
        api_level = PropParser.extract_first(props, *cls._API_LEVEL_KEYS, default="0")
        security_patch = cls.extract_security_patch(props, fingerprint, build_id)
        return _SharedBuildProperties(
            fingerprint=fingerprint,
            build_id=build_id,
            product=product,
            device=device,
            api_level=api_level,
            security_patch=security_patch,
        )

    @staticmethod
    def extract_security_patch(props: Dict[str, str], fingerprint: str, build_id: str) -> str:
        direct_patch = PropParser.extract_first(
            props,
            "ro.build.version.security_patch",
            "ro.vendor.build.security_patch",
            "ro.system.build.version.security_patch",
        )
        if direct_patch and len(direct_patch) == 10:
            return direct_patch

        # Parse YYMMDD from build identifiers.
        date_pattern = r"\.(\d{2})(\d{2})(\d{2})\."
        if build_id:
            match = re.search(date_pattern, build_id)
            if match:
                y, m, d = match.groups()
                return f"20{y}-{m}-{d}"

        if fingerprint:
            fp_match = re.search(r"/([A-Z0-9]+\.\d{6}\.[^/]+)/", fingerprint)
            if fp_match:
                match = re.search(date_pattern, fp_match.group(1))
                if match:
                    y, m, d = match.groups()
                    return f"20{y}-{m}-{d}"

        return direct_patch

    @classmethod
    def build_legacy(cls, props: Dict[str, str]) -> LegacyPIFProfile:
        build = cls._shared_build_properties(props, extended=False)

        return LegacyPIFProfile(
            MANUFACTURER=PropParser.extract_first(props, "ro.product.manufacturer", default="Google"),
            MODEL=PropParser.extract_first(props, "ro.product.model", default="Unknown"),
            FINGERPRINT=build.fingerprint,
            BRAND=PropParser.extract_first(props, "ro.product.brand", default="google"),
            PRODUCT=build.product,
            DEVICE=build.device,
            SECURITY_PATCH=build.security_patch,
            FIRST_API_LEVEL=str(int(build.api_level)),
        )

    @classmethod
    def build_extended(cls, props: Dict[str, str]) -> ExtendedPIFProfile:
        build = cls._shared_build_properties(props, extended=True)
        brand = PropParser.extract_first(
            props,
            "ro.product.system_ext.brand",
            "ro.product.system.brand",
            "ro.product.brand",
            default="google",
        )
        manufacturer = PropParser.extract_first(
            props,
            "ro.product.system_ext.manufacturer",
            "ro.product.system.manufacturer",
            "ro.product.manufacturer",
            default="Google",
        )
        model = PropParser.extract_first(
            props,
            "ro.product.system_ext.model",
            "ro.product.system.model",
            "ro.product.model",
            default="Unknown",
        )
        build_type = PropParser.extract_first(
            props,
            "ro.system_ext.build.type",
            "ro.system.build.type",
            "ro.build.type",
            default="user",
        )
        build_tags = PropParser.extract_first(
            props,
            "ro.system_ext.build.tags",
            "ro.system.build.tags",
            "ro.build.tags",
            default="release-keys",
        )
        release = PropParser.extract_first(
            props,
            "ro.system_ext.build.version.release",
            "ro.system.build.version.release",
            "ro.build.version.release",
            "ro.build.version.release_or_codename",
        )
        debuggable = PropParser.extract_first(props, "ro.debuggable", default="0")
        is_debug = build_type in ["userdebug", "eng"] or debuggable == "1"
        return ExtendedPIFProfile(
            ID=build.build_id,
            BRAND=brand,
            DEVICE=build.device,
            MANUFACTURER=manufacturer,
            FINGERPRINT=build.fingerprint,
            MODEL=model,
            PRODUCT=build.product,
            SECURITY_PATCH=build.security_patch,
            DEVICE_INITIAL_SDK_INT=str(int(build.api_level)),
            TYPE=build_type,
            TAG=build_tags,
            RELEASE=release,
            DEBUG=is_debug,
        )


class Extractor:
    @staticmethod
    def from_zip_bytes(content: bytes) -> str:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            for name in archive.namelist():
                if name.endswith("system.prop"):
                    return archive.read(name).decode("utf-8")
        raise FileNotFoundError("Target 'system.prop' not found in ZIP archive")

    @classmethod
    def from_url(cls, url: str, timeout: int = 120) -> str:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return cls.from_zip_bytes(response.content)
