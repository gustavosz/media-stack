from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple
import urllib.error
import urllib.request

from media_stack.domain.entities.bootstrap_step import BootstrapStepResult
from media_stack.domain.repositories.stack_provisioner import IStackProvisioner
from media_stack.infrastructure.credential_store import ConfigFileCredentialStore


class HttpAndFilesystemStackProvisioner(IStackProvisioner):
    """
    Concrete adapter implementing IStackProvisioner.
    Idempotently initializes storage directories, config files, and *Arr/Prowlarr/Bazarr/Calibre APIs.
    """

    REQUIRED_SUBDIRS = (
        "torrents/movies",
        "torrents/series",
        "torrents/books",
        "media/movies",
        "media/series",
        "media/books",
        "import_books",
    )

    def __init__(
        self,
        data_dir: Path,
        config_dir: Path,
        credential_store: ConfigFileCredentialStore,
    ) -> None:
        self._data_dir = data_dir
        self._config_dir = config_dir
        self._creds = credential_store

    @staticmethod
    def _api_request(
        url: str,
        api_key: str,
        method: str = "GET",
        payload: Optional[Dict[str, Any]] = None,
        timeout: int = 8,
    ) -> Tuple[Any, Optional[int]]:
        headers: Dict[str, str] = {"X-Api-Key": api_key}
        data_bytes: Optional[bytes] = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data_bytes = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            url, data=data_bytes, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
                try:
                    return json.loads(raw), resp.status
                except Exception:
                    return raw, resp.status
        except urllib.error.HTTPError as e:
            return None, e.code
        except Exception:
            return None, None

    def ensure_storage_directories(self) -> BootstrapStepResult:
        try:
            for sub in self.REQUIRED_SUBDIRS:
                (self._data_dir / sub).mkdir(parents=True, exist_ok=True)
            return BootstrapStepResult(
                step_name="Estructura de Directorios (DATA_DIR)",
                succeeded=True,
                details=f"7 subcarpetas verificadas en {self._data_dir} (listas para Hardlinks APFS)",
            )
        except Exception as e:
            return BootstrapStepResult(
                step_name="Estructura de Directorios (DATA_DIR)",
                succeeded=False,
                details=f"No se pudieron crear carpetas en {self._data_dir}: {e}",
            )

    def ensure_qbittorrent_config(self) -> BootstrapStepResult:
        conf_path = (
            self._config_dir / "qbittorrent" / "qBittorrent" / "qBittorrent.conf"
        )
        try:
            conf_path.parent.mkdir(parents=True, exist_ok=True)
            if not conf_path.is_file():
                default_conf = (
                    "[BitTorrent]\n"
                    "Session\\DefaultSavePath=/data/torrents\n"
                    "Session\\BTProtocol=TCP\n\n"
                    "[Preferences]\n"
                    "WebUI\\LocalHostAuth=false\n"
                    "WebUI\\AuthSubnetWhitelistEnabled=true\n"
                    "WebUI\\AuthSubnetWhitelist=0.0.0.0/0, ::/0\n"
                )
                conf_path.write_text(default_conf, encoding="utf-8")
                return BootstrapStepResult(
                    step_name="Configuración Base qBittorrent",
                    succeeded=True,
                    details="Archivo qBittorrent.conf inicializado con LocalHostAuth=false y /data/torrents",
                )

            content = conf_path.read_text(encoding="utf-8")
            modified = False
            if "WebUI\\LocalHostAuth=false" not in content:
                if "[Preferences]" in content:
                    content = content.replace(
                        "[Preferences]",
                        "[Preferences]\nWebUI\\LocalHostAuth=false\nWebUI\\AuthSubnetWhitelistEnabled=true\nWebUI\\AuthSubnetWhitelist=0.0.0.0/0, ::/0",
                        1,
                    )
                else:
                    content += (
                        "\n[Preferences]\n"
                        "WebUI\\LocalHostAuth=false\n"
                        "WebUI\\AuthSubnetWhitelistEnabled=true\n"
                        "WebUI\\AuthSubnetWhitelist=0.0.0.0/0, ::/0\n"
                    )
                modified = True

            if "Session\\DefaultSavePath=/data/torrents" not in content:
                if "[BitTorrent]" in content:
                    content = content.replace(
                        "[BitTorrent]",
                        "[BitTorrent]\nSession\\DefaultSavePath=/data/torrents",
                        1,
                    )
                else:
                    content += "\n[BitTorrent]\nSession\\DefaultSavePath=/data/torrents\n"
                modified = True

            if modified:
                conf_path.write_text(content, encoding="utf-8")

            return BootstrapStepResult(
                step_name="Configuración Base qBittorrent",
                succeeded=True,
                details="LocalHostAuth=false y DefaultSavePath=/data/torrents verificados",
            )
        except Exception as e:
            return BootstrapStepResult(
                step_name="Configuración Base qBittorrent",
                succeeded=False,
                details=f"Error verificando qBittorrent.conf: {e}",
            )

    def ensure_arr_root_folders(self) -> List[BootstrapStepResult]:
        specs = [
            ("Radarr", "radarr", "http://localhost:7878/api/v3/rootfolder", "/data/media/movies", {}),
            ("Sonarr", "sonarr", "http://localhost:8989/api/v3/rootfolder", "/data/media/series", {}),
            (
                "Chaptarr",
                "chaptarr",
                "http://localhost:8787/api/v1/rootfolder",
                "/data/media/books",
                {
                    "name": "Books",
                    "defaultMetadataProfileId": 1,
                    "defaultQualityProfileId": 1,
                    "isCalibreLibrary": False,
                },
            ),
        ]
        results: List[BootstrapStepResult] = []
        for label, folder_name, url, target_path, extra_fields in specs:
            key = self._creds.get_arr_api_key(folder_name)
            if not key:
                results.append(
                    BootstrapStepResult(
                        step_name=f"Root Folder ({label})",
                        succeeded=False,
                        details="API Key no encontrada (servicio aún no inicializado)",
                    )
                )
                continue

            existing, status = self._api_request(url, key.expose(), "GET")
            if status != 200 or not isinstance(existing, list):
                results.append(
                    BootstrapStepResult(
                        step_name=f"Root Folder ({label})",
                        succeeded=False,
                        details=f"API inaccesible (HTTP {status})",
                    )
                )
                continue

            already_has = any(
                isinstance(item, dict)
                and item.get("path", "").rstrip("/") == target_path.rstrip("/")
                for item in existing
            )
            if already_has:
                results.append(
                    BootstrapStepResult(
                        step_name=f"Root Folder ({label})",
                        succeeded=True,
                        details=f"Ya configurado ({target_path})",
                    )
                )
                continue

            payload = {"path": target_path, **extra_fields}
            _, post_status = self._api_request(url, key.expose(), "POST", payload)
            results.append(
                BootstrapStepResult(
                    step_name=f"Root Folder ({label})",
                    succeeded=post_status in (200, 201),
                    details=(
                        f"Creado exitosamente ({target_path})"
                        if post_status in (200, 201)
                        else f"Error al crear (HTTP {post_status})"
                    ),
                )
            )
        return results

    def ensure_arr_download_clients(self) -> List[BootstrapStepResult]:
        specs = [
            ("Radarr", "radarr", "http://localhost:7878/api/v3/downloadclient", "movieCategory", "movies"),
            ("Sonarr", "sonarr", "http://localhost:8989/api/v3/downloadclient", "tvCategory", "series"),
            ("Chaptarr", "chaptarr", "http://localhost:8787/api/v1/downloadclient", "bookCategory", "books"),
        ]
        results: List[BootstrapStepResult] = []
        for label, folder_name, url, category_field, category_val in specs:
            key = self._creds.get_arr_api_key(folder_name)
            if not key:
                results.append(
                    BootstrapStepResult(
                        step_name=f"Download Client ({label})",
                        succeeded=False,
                        details="API Key no disponible",
                    )
                )
                continue

            existing, status = self._api_request(url, key.expose(), "GET")
            if status != 200 or not isinstance(existing, list):
                results.append(
                    BootstrapStepResult(
                        step_name=f"Download Client ({label})",
                        succeeded=False,
                        details=f"API inaccesible (HTTP {status})",
                    )
                )
                continue

            has_qbit = any(
                isinstance(item, dict) and item.get("implementation") == "QBittorrent"
                for item in existing
            )
            if has_qbit:
                results.append(
                    BootstrapStepResult(
                        step_name=f"Download Client ({label})",
                        succeeded=True,
                        details="qBittorrent (gluetun:8080) ya vinculado",
                    )
                )
                continue

            payload = {
                "enable": True,
                "protocol": "torrent",
                "priority": 1,
                "name": "qBittorrent",
                "implementation": "QBittorrent",
                "configContract": "QBittorrentSettings",
                "fields": [
                    {"name": "host", "value": "gluetun"},
                    {"name": "port", "value": 8080},
                    {"name": "useSsl", "value": False},
                    {"name": category_field, "value": category_val},
                ],
            }
            _, post_status = self._api_request(url, key.expose(), "POST", payload)
            results.append(
                BootstrapStepResult(
                    step_name=f"Download Client ({label})",
                    succeeded=post_status in (200, 201),
                    details=(
                        "qBittorrent (gluetun:8080) registrado exitosamente"
                        if post_status in (200, 201)
                        else f"Error registrando cliente (HTTP {post_status})"
                    ),
                )
            )
        return results

    def ensure_prowlarr_integrations(self) -> List[BootstrapStepResult]:
        results: List[BootstrapStepResult] = []
        prowlarr_key = self._creds.get_arr_api_key("prowlarr")
        if not prowlarr_key:
            return [
                BootstrapStepResult(
                    step_name="Integraciones Prowlarr",
                    succeeded=False,
                    details="API Key de Prowlarr no disponible",
                )
            ]

        # 1. FlareSolverr Indexer Proxy
        proxy_url = "http://localhost:9696/api/v1/indexerproxy"
        proxies, status = self._api_request(proxy_url, prowlarr_key.expose(), "GET")
        if status == 200 and isinstance(proxies, list):
            has_flaresolverr = any(
                isinstance(p, dict) and p.get("implementation") == "FlareSolverr"
                for p in proxies
            )
            if has_flaresolverr:
                results.append(
                    BootstrapStepResult(
                        step_name="Prowlarr -> FlareSolverr",
                        succeeded=True,
                        details="Proxy FlareSolverr (http://flaresolverr:8191) ya vinculado",
                    )
                )
            else:
                proxy_payload = {
                    "name": "FlareSolverr",
                    "implementation": "FlareSolverr",
                    "configContract": "FlareSolverrSettings",
                    "fields": [
                        {"name": "host", "value": "http://flaresolverr:8191"},
                        {"name": "requestTimeout", "value": 60},
                    ],
                    "tags": [],
                }
                _, p_status = self._api_request(
                    proxy_url, prowlarr_key.expose(), "POST", proxy_payload
                )
                results.append(
                    BootstrapStepResult(
                        step_name="Prowlarr -> FlareSolverr",
                        succeeded=p_status in (200, 201),
                        details=(
                            "FlareSolverr vinculado exitosamente"
                            if p_status in (200, 201)
                            else f"Error vinculando FlareSolverr (HTTP {p_status})"
                        ),
                    )
                )

        # 2. Applications (Radarr, Sonarr, Chaptarr)
        apps_url = "http://localhost:9696/api/v1/applications"
        existing_apps, a_status = self._api_request(
            apps_url, prowlarr_key.expose(), "GET"
        )
        if a_status != 200 or not isinstance(existing_apps, list):
            return results

        app_specs = [
            (
                "Radarr",
                "radarr",
                "Radarr",
                "RadarrSettings",
                "http://radarr:7878",
                [2000, 2010, 2020, 2030, 2040, 2045, 2050, 2060],
            ),
            (
                "Sonarr",
                "sonarr",
                "Sonarr",
                "SonarrSettings",
                "http://sonarr:8989",
                [5000, 5010, 5020, 5030, 5040, 5045, 5050],
            ),
            (
                "Chaptarr",
                "chaptarr",
                "Readarr",
                "ReadarrSettings",
                "http://chaptarr:8789",
                [7000, 7010, 7020, 7030, 7040, 7050, 7060],
            ),
        ]

        for app_label, cfg_folder, impl, contract, base_url, cats in app_specs:
            already_linked = any(
                isinstance(a, dict) and a.get("name", "").lower() == app_label.lower()
                for a in existing_apps
            )
            if already_linked:
                results.append(
                    BootstrapStepResult(
                        step_name=f"Prowlarr -> {app_label}",
                        succeeded=True,
                        details=f"Sincronización completa activa ({base_url})",
                    )
                )
                continue

            target_key = self._creds.get_arr_api_key(cfg_folder)
            if not target_key:
                results.append(
                    BootstrapStepResult(
                        step_name=f"Prowlarr -> {app_label}",
                        succeeded=False,
                        details=f"API Key de {app_label} no encontrada",
                    )
                )
                continue

            app_payload = {
                "name": app_label,
                "implementation": impl,
                "configContract": contract,
                "syncLevel": "fullSync",
                "fields": [
                    {"name": "prowlarrUrl", "value": "http://prowlarr:9696"},
                    {"name": "baseUrl", "value": base_url},
                    {"name": "apiKey", "value": target_key.expose()},
                    {"name": "syncCategories", "value": cats},
                ],
                "tags": [],
            }
            _, post_code = self._api_request(
                apps_url, prowlarr_key.expose(), "POST", app_payload
            )
            results.append(
                BootstrapStepResult(
                    step_name=f"Prowlarr -> {app_label}",
                    succeeded=post_code in (200, 201),
                    details=(
                        f"Aplicación {app_label} vinculada en Prowlarr"
                        if post_code in (200, 201)
                        else f"Error vinculando {app_label} (HTTP {post_code})"
                    ),
                )
            )
        return results

    def ensure_bazarr_integrations(self) -> BootstrapStepResult:
        yaml_path = self._config_dir / "bazarr" / "config" / "config.yaml"
        if not yaml_path.is_file():
            return BootstrapStepResult(
                step_name="Integración Bazarr (Subtítulos)",
                succeeded=False,
                details="config.yaml de Bazarr aún no generado",
            )

        try:
            content = yaml_path.read_text(encoding="utf-8")
            radarr_key = self._creds.get_arr_api_key("radarr")
            sonarr_key = self._creds.get_arr_api_key("sonarr")
            modified = False

            if "use_radarr: false" in content and radarr_key:
                content = content.replace("use_radarr: false", "use_radarr: true", 1)
                content = re.sub(
                    r"(radarr:\s*\n(?:.*\n)*?\s*apikey:\s*)''",
                    f"\\g<1>{radarr_key.expose()}",
                    content,
                    count=1,
                )
                content = re.sub(
                    r"(radarr:\s*\n(?:.*\n)*?\s*ip:\s*)127\.0\.0\.1",
                    "\\g<1>radarr",
                    content,
                    count=1,
                )
                modified = True

            if "use_sonarr: false" in content and sonarr_key:
                content = content.replace("use_sonarr: false", "use_sonarr: true", 1)
                content = re.sub(
                    r"(sonarr:\s*\n(?:.*\n)*?\s*apikey:\s*)''",
                    f"\\g<1>{sonarr_key.expose()}",
                    content,
                    count=1,
                )
                content = re.sub(
                    r"(sonarr:\s*\n(?:.*\n)*?\s*ip:\s*)127\.0\.0\.1",
                    "\\g<1>sonarr",
                    content,
                    count=1,
                )
                modified = True

            if modified:
                yaml_path.write_text(content, encoding="utf-8")

            return BootstrapStepResult(
                step_name="Integración Bazarr (Subtítulos)",
                succeeded=True,
                details="Vinculación con Radarr y Sonarr verificada",
            )
        except Exception as e:
            return BootstrapStepResult(
                step_name="Integración Bazarr (Subtítulos)",
                succeeded=False,
                details=f"Error actualizando config.yaml de Bazarr: {e}",
            )

    def ensure_calibre_library_initialized(self) -> BootstrapStepResult:
        metadata_db = self._data_dir / "media" / "books" / "metadata.db"
        if metadata_db.is_file():
            return BootstrapStepResult(
                step_name="Biblioteca Calibre-Web (metadata.db)",
                succeeded=True,
                details=f"Base de datos activa en {metadata_db}",
            )

        try:
            res = subprocess.run(
                [
                    "docker",
                    "exec",
                    "calibre-web",
                    "calibredb",
                    "list",
                    "--library-path=/books",
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if res.returncode == 0 and metadata_db.is_file():
                return BootstrapStepResult(
                    step_name="Biblioteca Calibre-Web (metadata.db)",
                    succeeded=True,
                    details="Base de datos metadata.db inicializada automáticamente",
                )
            return BootstrapStepResult(
                step_name="Biblioteca Calibre-Web (metadata.db)",
                succeeded=False,
                details="Calibre-Web aún instalando binario calibredb",
            )
        except Exception as e:
            return BootstrapStepResult(
                step_name="Biblioteca Calibre-Web (metadata.db)",
                succeeded=False,
                details=f"Error inicializando metadata.db: {e}",
            )
