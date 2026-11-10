import json
from typing import Any, Dict, List, Optional, Tuple
import urllib.error
import urllib.request

from media_stack.domain.entities.service_health import ServiceHealthResult
from media_stack.domain.repositories.service_health_gateway import (
    IServiceHealthGateway,
)
from media_stack.domain.value_objects.network import ServiceEndpointUrl
from media_stack.infrastructure.credential_store import ConfigFileCredentialStore


class HttpServiceHealthGateway(IServiceHealthGateway):
    """HTTP adapter implementing IServiceHealthGateway using Python standard urllib."""

    def __init__(
        self,
        credential_store: ConfigFileCredentialStore,
        jellyfin_url: str = "http://localhost:8096",
    ) -> None:
        self._creds = credential_store
        self._jellyfin_url = jellyfin_url.rstrip("/")

    @staticmethod
    def _http_get(
        url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 4
    ) -> Tuple[Any, Optional[int]]:
        req = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
                try:
                    return json.loads(body), resp.status
                except Exception:
                    return body, resp.status
        except urllib.error.HTTPError as e:
            return None, e.code
        except Exception:
            return None, None

    def check_all_services(self) -> List[ServiceHealthResult]:
        radarr_key = self._creds.get_arr_api_key("radarr")
        sonarr_key = self._creds.get_arr_api_key("sonarr")
        chaptarr_key = self._creds.get_arr_api_key("chaptarr")
        prowlarr_key = self._creds.get_arr_api_key("prowlarr")
        bazarr_key = self._creds.get_bazarr_api_key()
        jellyfin_key = self._creds.get_jellyfin_api_key()

        jf_headers: Dict[str, str] = {}
        if jellyfin_key:
            jf_headers = {
                "Authorization": f'MediaBrowser Token="{jellyfin_key.expose()}"',
                "X-Emby-Token": jellyfin_key.expose(),
            }

        probes: List[Tuple[str, str, Dict[str, str]]] = [
            ("Jellyfin", f"{self._jellyfin_url}/System/Info", jf_headers),
            ("Jellyseerr", "http://localhost:5055/api/v1/status", {}),
            (
                "Radarr",
                "http://localhost:7878/api/v3/system/status",
                {"X-Api-Key": radarr_key.expose()} if radarr_key else {},
            ),
            (
                "Sonarr",
                "http://localhost:8989/api/v3/system/status",
                {"X-Api-Key": sonarr_key.expose()} if sonarr_key else {},
            ),
            (
                "Chaptarr",
                "http://localhost:8787/api/v1/system/status",
                {"X-Api-Key": chaptarr_key.expose()} if chaptarr_key else {},
            ),
            ("Calibre-Web", "http://localhost:8083/login", {}),
            (
                "Prowlarr",
                "http://localhost:9696/api/v1/system/status",
                {"X-Api-Key": prowlarr_key.expose()} if prowlarr_key else {},
            ),
            (
                "Bazarr",
                "http://localhost:6767/api/system/status",
                {"X-Api-Key": bazarr_key.expose()} if bazarr_key else {},
            ),
            ("qBittorrent", "http://localhost:8080/api/v2/app/version", {}),
            ("Flaresolverr", "http://localhost:8191/health", {}),
        ]

        results: List[ServiceHealthResult] = []
        for name, url, headers in probes:
            _, status = self._http_get(url, headers=headers)
            results.append(
                ServiceHealthResult(
                    service_name=name,
                    url=ServiceEndpointUrl(url),
                    http_status=status,
                    is_online=status in (200, 204),
                )
            )
        return results

    def get_bazarr_providers_summary(self) -> List[str]:
        bazarr_key = self._creds.get_bazarr_api_key()
        if not bazarr_key:
            return []
        data, _ = self._http_get(
            "http://localhost:6767/api/providers",
            headers={"X-Api-Key": bazarr_key.expose()},
        )
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            return [f"{p['name']} ({p['status']})" for p in data["data"]]
        return []

    def trigger_jellyfin_library_refresh(self) -> bool:
        jellyfin_key = self._creds.get_jellyfin_api_key()
        headers = {"X-Emby-Token": jellyfin_key.expose()} if jellyfin_key else {}
        req = urllib.request.Request(
            f"{self._jellyfin_url}/Library/Refresh",
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status in (200, 204)
        except Exception:
            return False
