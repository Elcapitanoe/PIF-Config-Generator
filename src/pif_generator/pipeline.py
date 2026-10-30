import logging
from pathlib import Path
from typing import Union

from .builder import Extractor, ProfileBuilder, PropParser
from .models import ChannelType, ExtendedPIFProfile, LegacyPIFProfile, OutputFormat

logger = logging.getLogger(__name__)


class PIFPipeline:
    def __init__(
        self,
        channel: ChannelType = ChannelType.STABLE,
        format_type: OutputFormat = OutputFormat.EXTENDED,
        output_dir: Path = Path("."),
    ):
        self.channel = channel
        self.format_type = format_type
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def process_prop_content(self, prop_content: str) -> Union[ExtendedPIFProfile, LegacyPIFProfile]:
        props = PropParser.parse(prop_content)
        if self.format_type == OutputFormat.LEGACY:
            return ProfileBuilder.build_legacy(props)
        return ProfileBuilder.build_extended(props)

    def process_zip_url(self, asset_name: str, url: str) -> Path:
        base_name = Path(asset_name).stem
        output_filename = f"{base_name}.json"
        dest_path = self.output_dir / output_filename

        logger.info("Fetching and extracting system.prop from %s", url)
        prop_content = Extractor.from_url(url)
        profile = self.process_prop_content(prop_content)

        dest_path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
        logger.info("Generated profile at %s", dest_path)
        return dest_path
