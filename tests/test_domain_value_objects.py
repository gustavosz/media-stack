from dataclasses import FrozenInstanceError
from pathlib import Path
import unittest

from media_stack.domain.value_objects.credentials import ApiKey
from media_stack.domain.value_objects.network import (
    IpAddress,
    PortNumber,
    ServiceEndpointUrl,
)
from media_stack.domain.value_objects.storage import (
    FileSizeBytes,
    InodeLinkCount,
    VolumeMountPath,
)


class TestNetworkValueObjects(unittest.TestCase):
    def test_valid_port_number(self) -> None:
        port = PortNumber(8080)
        self.assertEqual(port.value, 8080)
        self.assertEqual(str(port), "8080")

    def test_port_number_boundaries(self) -> None:
        self.assertEqual(PortNumber(1).value, 1)
        self.assertEqual(PortNumber(65535).value, 65535)

    def test_invalid_port_number_raises_value_error(self) -> None:
        for invalid in (0, -1, 65536, 100000):
            with self.subTest(port=invalid):
                with self.assertRaises(ValueError):
                    PortNumber(invalid)

    def test_port_number_is_immutable(self) -> None:
        port = PortNumber(63398)
        with self.assertRaises(FrozenInstanceError):
            port.value = 9000  # type: ignore[misc]

    def test_ip_address_validation(self) -> None:
        ip = IpAddress("84.233.234.202")
        self.assertEqual(str(ip), "84.233.234.202")
        with self.assertRaises(ValueError):
            IpAddress("")
        with self.assertRaises(ValueError):
            IpAddress("   ")

    def test_service_endpoint_url_validation(self) -> None:
        url_http = ServiceEndpointUrl("http://localhost:8096/System/Info")
        url_https = ServiceEndpointUrl("https://api.example.com/status")
        self.assertEqual(str(url_http), "http://localhost:8096/System/Info")
        self.assertEqual(str(url_https), "https://api.example.com/status")

        with self.assertRaises(ValueError):
            ServiceEndpointUrl("ftp://localhost:21")
        with self.assertRaises(ValueError):
            ServiceEndpointUrl("localhost:8096")


class TestStorageValueObjects(unittest.TestCase):
    def test_volume_mount_path_extracts_macos_volume_from_data_dir(self) -> None:
        vo = VolumeMountPath.from_data_dir(Path("/Volumes/Media/data"))
        self.assertEqual(vo.path, Path("/Volumes/Media"))
        self.assertEqual(vo.name, "Media")
        self.assertEqual(str(vo), "/Volumes/Media")

    def test_volume_mount_path_respects_explicit_mount_override(self) -> None:
        vo = VolumeMountPath.from_data_dir(
            Path("/Volumes/Media/data"), explicit_mount="/Volumes/OtroDisco"
        )
        self.assertEqual(vo.path, Path("/Volumes/OtroDisco"))
        self.assertEqual(vo.name, "OtroDisco")

    def test_volume_mount_path_non_volumes_fallback(self) -> None:
        vo = VolumeMountPath.from_data_dir(Path("/mnt/storage/data"))
        self.assertEqual(vo.path, Path("/mnt/storage/data"))

    def test_inode_link_count(self) -> None:
        single = InodeLinkCount(1)
        linked = InodeLinkCount(2)
        self.assertFalse(single.is_hardlinked)
        self.assertTrue(linked.is_hardlinked)
        with self.assertRaises(ValueError):
            InodeLinkCount(-1)

    def test_file_size_bytes_conversion(self) -> None:
        two_gb = FileSizeBytes(2 * (1024**3))
        self.assertAlmostEqual(two_gb.gigabytes, 2.0)
        self.assertEqual(two_gb.format_gb(), "2.00 GB")
        with self.assertRaises(ValueError):
            FileSizeBytes(-100)


class TestCredentialValueObjects(unittest.TestCase):
    def test_api_key_masks_secret_in_string_representation(self) -> None:
        key = ApiKey("c550697f594b4a209f4856c379977280")
        self.assertEqual(key.expose(), "c550697f594b4a209f4856c379977280")
        self.assertNotIn("594b4a209f4856c3", repr(key))
        self.assertNotIn("594b4a209f4856c3", str(key))
        self.assertEqual(str(key), "ApiKey(c550...7280)")

    def test_short_api_key_masks_completely(self) -> None:
        key = ApiKey("short123")
        self.assertEqual(str(key), "ApiKey(****)")

    def test_empty_api_key_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            ApiKey("")
        with self.assertRaises(ValueError):
            ApiKey("   ")


if __name__ == "__main__":
    unittest.main()
