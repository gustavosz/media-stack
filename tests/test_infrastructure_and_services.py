import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from media_stack.infrastructure.credential_store import ConfigFileCredentialStore
from media_stack.infrastructure.settings import AppSettings
from media_stack.infrastructure.stack_provisioner_adapter import (
    HttpAndFilesystemStackProvisioner,
)


class TestInfrastructureConfigAndCredentials(unittest.TestCase):
    def test_app_settings_loads_dotenv_and_resolves_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            env_file = root / ".env"
            env_file.write_text(
                "CONFIG_DIR=./custom_cfg\n"
                "DATA_DIR=/Volumes/ExternalSSD/media_data\n",
                encoding="utf-8",
            )

            clean_env = {
                k: v
                for k, v in os.environ.items()
                if k
                not in (
                    "PROJECT_DIR",
                    "CONFIG_DIR",
                    "DATA_DIR",
                    "EXTERNAL_DISK_MOUNT",
                )
            }
            with patch.dict(os.environ, clean_env, clear=True):
                settings = AppSettings.from_environment(explicit_project_dir=root)
                self.assertEqual(settings.project_dir, root)
                self.assertEqual(settings.config_dir, root / "custom_cfg")
                self.assertEqual(
                    settings.data_dir, Path("/Volumes/ExternalSSD/media_data")
                )
                self.assertEqual(
                    settings.external_disk_mount.path, Path("/Volumes/ExternalSSD")
                )

    def test_credential_store_parses_arr_xml_bazarr_yaml_and_jellyseerr_json(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_dir = Path(tmpdir)

            # 1. Radarr config.xml
            radarr_dir = cfg_dir / "radarr"
            radarr_dir.mkdir(parents=True)
            (radarr_dir / "config.xml").write_text(
                "<Config><ApiKey>radarr_secret_123456</ApiKey></Config>",
                encoding="utf-8",
            )

            # 2. Bazarr config.yaml
            bazarr_dir = cfg_dir / "bazarr" / "config"
            bazarr_dir.mkdir(parents=True)
            (bazarr_dir / "config.yaml").write_text(
                "auth:\n  apikey: bazarr_secret_987654\n",
                encoding="utf-8",
            )

            # 3. Jellyseerr settings.json
            jellyseerr_dir = cfg_dir / "jellyseerr"
            jellyseerr_dir.mkdir(parents=True)
            (jellyseerr_dir / "settings.json").write_text(
                '{"jellyfin": {"apiKey": "jf_secret_token_abcdef"}}',
                encoding="utf-8",
            )

            store = ConfigFileCredentialStore(cfg_dir)
            radarr_key = store.get_arr_api_key("radarr")
            bazarr_key = store.get_bazarr_api_key()
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("JELLYFIN_API_KEY", None)
                jf_key = store.get_jellyfin_api_key()

            self.assertIsNotNone(radarr_key)
            self.assertEqual(radarr_key.expose(), "radarr_secret_123456")  # type: ignore[union-attr]
            self.assertIsNotNone(bazarr_key)
            self.assertEqual(bazarr_key.expose(), "bazarr_secret_987654")  # type: ignore[union-attr]
            self.assertIsNotNone(jf_key)
            self.assertEqual(jf_key.expose(), "jf_secret_token_abcdef")  # type: ignore[union-attr]

    def test_provisioner_creates_storage_dirs_and_initializes_qbit_conf(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_dir = root / "data"
            cfg_dir = root / "config"
            store = ConfigFileCredentialStore(cfg_dir)
            provisioner = HttpAndFilesystemStackProvisioner(data_dir, cfg_dir, store)

            dir_step = provisioner.ensure_storage_directories()
            self.assertTrue(dir_step.succeeded)
            self.assertTrue((data_dir / "torrents" / "movies").is_dir())
            self.assertTrue((data_dir / "media" / "movies").is_dir())
            self.assertTrue((data_dir / "import_books").is_dir())

            qbit_step = provisioner.ensure_qbittorrent_config()
            self.assertTrue(qbit_step.succeeded)
            qbit_conf = (
                cfg_dir / "qbittorrent" / "qBittorrent" / "qBittorrent.conf"
            ).read_text(encoding="utf-8")
            self.assertIn("WebUI\\LocalHostAuth=false", qbit_conf)
            self.assertIn("Session\\DefaultSavePath=/data/torrents", qbit_conf)


class TestChaptarrProxyService(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        proxy_path = (
            Path(__file__).resolve().parent.parent
            / "services"
            / "chaptarr"
            / "proxy"
            / "main.py"
        )
        spec = importlib.util.spec_from_file_location("chaptarr_proxy", proxy_path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls.proxy_mod = mod

    def test_html_sanitizer_strips_tags_and_unescapes_entities(self) -> None:
        raw = "<p>Una <b>gran</b> novela &amp; historia.<br/>Segunda línea.</p>"
        cleaned = self.proxy_mod.HtmlSanitizer.clean(raw)
        self.assertEqual(cleaned, "Una gran novela & historia.\nSegunda línea.")

    def test_book_metadata_enricher_resolves_relative_covers_with_dynamic_host(
        self,
    ) -> None:
        enricher = self.proxy_mod.BookMetadataEnricher("http://mi-servidor.local:8787")
        payload = [
            {
                "title": "El Eternauta",
                "overview": "<i>Ciencia ficción</i> argentina.",
                "remoteCover": "/MediaCover/Books/1/cover.jpg",
            }
        ]
        enriched = enricher.enrich_payload(payload)
        book = enriched[0]
        self.assertEqual(book["overview"], "Ciencia ficción argentina.")
        self.assertEqual(
            book["remotePoster"],
            "http://mi-servidor.local:8787/MediaCover/Books/1/cover.jpg",
        )


class TestCalibreAutoImportService(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        importer_path = (
            Path(__file__).resolve().parent.parent
            / "services"
            / "calibre-web"
            / "auto-import"
            / "importer.py"
        )
        spec = importlib.util.spec_from_file_location("calibre_importer", importer_path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules["calibre_importer"] = mod
        spec.loader.exec_module(mod)
        cls.importer_mod = mod

    def test_smtp_credentials_value_object(self) -> None:
        creds = self.importer_mod.SmtpCredentials(
            server="smtp.gmail.com",
            port=587,
            login="user@gmail.com",
            password="secret",
            sender="user@gmail.com",
            recipient_kindle="user@kindle.com",
        )
        self.assertTrue(creds.can_send_to_kindle)

        no_kindle = self.importer_mod.SmtpCredentials(
            server="smtp.gmail.com",
            port=587,
            login="user@gmail.com",
            password="secret",
            sender="user@gmail.com",
            recipient_kindle=None,
        )
        self.assertFalse(no_kindle.can_send_to_kindle)

    def test_chaptarr_gateway_reads_api_key_from_xml(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            xml_file = Path(tmpdir) / "config.xml"
            xml_file.write_text(
                "<Config><ApiKey>chaptarr_dynamic_key_777</ApiKey></Config>",
                encoding="utf-8",
            )
            gateway = self.importer_mod.ChaptarrGateway(str(xml_file))
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("CHAPTARR_API_KEY", None)
                self.assertEqual(
                    gateway._resolve_api_key(), "chaptarr_dynamic_key_777"
                )


if __name__ == "__main__":
    unittest.main()
