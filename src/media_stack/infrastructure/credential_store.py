import json
import os
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree

from media_stack.domain.value_objects.credentials import ApiKey


class ConfigFileCredentialStore:
    """Infrastructure helper that extracts service API keys from runtime config files."""

    def __init__(self, config_dir: Path) -> None:
        self._config_dir = config_dir

    def get_arr_api_key(self, service_folder: str) -> Optional[ApiKey]:
        xml_path = self._config_dir / service_folder / "config.xml"
        if not xml_path.is_file():
            return None
        try:
            tree = ElementTree.parse(xml_path)
            elem = tree.getroot().find("ApiKey")
            if elem is not None and elem.text and elem.text.strip():
                return ApiKey(elem.text.strip())
        except Exception:
            pass
        return None

    def get_bazarr_api_key(self) -> Optional[ApiKey]:
        yaml_path = self._config_dir / "bazarr" / "config" / "config.yaml"
        if not yaml_path.is_file():
            return None
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                for line in f:
                    if "apikey:" in line:
                        raw = line.split("apikey:")[-1].strip()
                        if raw:
                            return ApiKey(raw)
        except Exception:
            pass
        return None

    def get_jellyfin_api_key(self) -> Optional[ApiKey]:
        env_token = os.getenv("JELLYFIN_API_KEY")
        if env_token and env_token.strip():
            return ApiKey(env_token.strip())

        jellyseerr_path = self._config_dir / "jellyseerr" / "settings.json"
        if jellyseerr_path.is_file():
            try:
                with open(jellyseerr_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    jf_section = data.get("jellyfin")
                    if isinstance(jf_section, dict):
                        raw = jf_section.get("apiKey")
                        if raw and str(raw).strip():
                            return ApiKey(str(raw).strip())
            except Exception:
                pass

        return None
