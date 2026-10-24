import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pif_generator.builder import ProfileBuilder, PropParser
from pif_generator.models import ChannelType, ExtendedPIFProfile, LegacyPIFProfile
from pif_generator.pipeline import PIFPipeline


SAMPLE_PROP = """
ro.product.manufacturer=Google
ro.product.model=Pixel 9 Pro XL
ro.product.brand=google
ro.product.device=komodo
ro.product.system_ext.name=komodo_beta
ro.system_ext.build.id=CP41.260814.003.B1
ro.system_ext.build.fingerprint=google/komodo_beta/komodo:17/CP41.260814.003.B1/16166531:user/release-keys
ro.system_ext.build.type=user
ro.system_ext.build.tags=release-keys
ro.system_ext.build.version.release=17
ro.product.first_api_level=34
ro.debuggable=0
"""


class TestPIFBuilder(unittest.TestCase):
    def test_prop_parser(self):
        props = PropParser.parse(SAMPLE_PROP)
        self.assertEqual(props["ro.product.model"], "Pixel 9 Pro XL")
        self.assertEqual(props["ro.system_ext.build.id"], "CP41.260814.003.B1")
        self.assertEqual(props["ro.product.device"], "komodo")

    def test_build_extended_profile(self):
        props = PropParser.parse(SAMPLE_PROP)
        profile = ProfileBuilder.build_extended(props)
        self.assertIsInstance(profile, ExtendedPIFProfile)
        self.assertEqual(profile.ID, "CP41.260814.003.B1")
        self.assertEqual(profile.BRAND, "google")
        self.assertEqual(profile.DEVICE, "komodo")
        self.assertEqual(profile.MANUFACTURER, "Google")
        self.assertEqual(profile.MODEL, "Pixel 9 Pro XL")
        self.assertEqual(profile.PRODUCT, "komodo_beta")
        self.assertEqual(profile.SECURITY_PATCH, "2026-08-14")
        self.assertEqual(profile.DEVICE_INITIAL_SDK_INT, "34")
        self.assertEqual(profile.TYPE, "user")
        self.assertEqual(profile.TAG, "release-keys")
        self.assertEqual(profile.RELEASE, "17")
        self.assertFalse(profile.DEBUG)
        self.assertEqual(profile.spoofBuild, "1")
        self.assertEqual(profile.spoofProps, "1")
        self.assertEqual(profile.spoofVendingBuild, "1")
        self.assertEqual(profile.model_dump()["spoofProps"], "1")
        self.assertEqual(profile.model_dump()["spoofVendingBuild"], "1")

    def test_build_legacy_profile(self):
        props = PropParser.parse(SAMPLE_PROP)
        profile = ProfileBuilder.build_legacy(props)
        self.assertIsInstance(profile, LegacyPIFProfile)
        self.assertEqual(profile.MODEL, "Pixel 9 Pro XL")
        self.assertEqual(profile.FIRST_API_LEVEL, "34")
        self.assertEqual(profile.SECURITY_PATCH, "2026-08-14")

    def test_invalid_sdk_validation(self):
        props = PropParser.parse(SAMPLE_PROP)
        props["ro.product.first_api_level"] = "10"
        with self.assertRaises(Exception):
            ProfileBuilder.build_extended(props)

    def test_invalid_security_patch_validation(self):
        props = PropParser.parse(SAMPLE_PROP)
        props["ro.build.version.security_patch"] = "2026-13-40"
        with self.assertRaises(ValueError):
            ProfileBuilder.build_extended(props)

    @patch("pif_generator.pipeline.Extractor.from_url", return_value=SAMPLE_PROP)
    def test_zip_profiles_are_namespaced_by_channel(self, _from_url):
        with TemporaryDirectory() as tmp_dir:
            stable = PIFPipeline(channel=ChannelType.STABLE, output_dir=Path(tmp_dir))
            beta = PIFPipeline(channel=ChannelType.BETA, output_dir=Path(tmp_dir))

            stable_path = stable.process_zip_url("komodo.zip", "https://example.test/komodo.zip")
            beta_path = beta.process_zip_url("komodo.zip", "https://example.test/komodo.zip")

            self.assertEqual(stable_path.name, "stable_komodo.json")
            self.assertEqual(beta_path.name, "beta_komodo.json")
            self.assertNotEqual(stable_path, beta_path)


if __name__ == "__main__":
    unittest.main()
