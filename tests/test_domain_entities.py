from pathlib import Path
import unittest

from media_stack.domain.entities.container import ContainerMountCheck, ContainerNode
from media_stack.domain.entities.external_disk import DiskConnectionState, ExternalDisk
from media_stack.domain.entities.media_item import MovieMediaAsset, SubtitleStream
from media_stack.domain.entities.service_health import ServiceHealthResult
from media_stack.domain.entities.vpn_tunnel import VpnTunnelStatus
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


class TestDomainEntities(unittest.TestCase):
    def test_container_node_running_state(self) -> None:
        running = ContainerNode(name="jellyfin", state="running")
        stopped = ContainerNode(name="radarr", state="exited")
        missing = ContainerNode(name="sonarr", state="missing")

        self.assertTrue(running.is_running)
        self.assertFalse(stopped.is_running)
        self.assertFalse(missing.is_running)

    def test_container_mount_check(self) -> None:
        active = ContainerMountCheck(
            container_name="jellyfin", mount_point="/data/media", is_accessible=True
        )
        stale = ContainerMountCheck(
            container_name="radarr",
            mount_point="/data",
            is_accessible=False,
            error_reason="Stale/Inaccesible",
        )
        self.assertTrue(active.is_accessible)
        self.assertFalse(stale.is_accessible)
        self.assertEqual(stale.error_reason, "Stale/Inaccesible")

    def test_external_disk_state_transitions(self) -> None:
        mount = VolumeMountPath(Path("/Volumes/Media"))
        disk = ExternalDisk(mount_path=mount, state=DiskConnectionState.CONNECTED)
        self.assertTrue(disk.is_connected)

        disk.mark_disconnected()
        self.assertFalse(disk.is_connected)
        self.assertEqual(disk.state, DiskConnectionState.DISCONNECTED)

        disk.mark_connected()
        self.assertTrue(disk.is_connected)
        self.assertEqual(disk.state, DiskConnectionState.CONNECTED)

    def test_vpn_tunnel_status_port_synchronization(self) -> None:
        synced = VpnTunnelStatus(
            public_ip=IpAddress("84.233.234.202"),
            country="AR",
            city="Buenos Aires",
            organization="Datacamp Limited",
            forwarded_port=PortNumber(63398),
            qbit_listen_port=PortNumber(63398),
        )
        self.assertTrue(synced.has_public_ip)
        self.assertTrue(synced.is_port_synced)

        desynced = VpnTunnelStatus(
            public_ip=IpAddress("84.233.234.202"),
            forwarded_port=PortNumber(63398),
            qbit_listen_port=PortNumber(51413),
        )
        self.assertFalse(desynced.is_port_synced)

        incomplete = VpnTunnelStatus(forwarded_port=PortNumber(63398))
        self.assertFalse(incomplete.has_public_ip)
        self.assertFalse(incomplete.is_port_synced)

    def test_service_health_result(self) -> None:
        res = ServiceHealthResult(
            service_name="Radarr",
            url=ServiceEndpointUrl("http://localhost:7878/api/v3/system/status"),
            http_status=200,
            is_online=True,
        )
        self.assertTrue(res.is_online)
        self.assertEqual(res.http_status, 200)

    def test_movie_media_asset_and_subtitle_streams(self) -> None:
        ext_sub = SubtitleStream(
            display_title="Spanish", codec="subrip", is_external=True
        )
        emb_sub = SubtitleStream(
            display_title="Latin American", codec="pgssub", is_external=False
        )
        self.assertEqual(ext_sub.format_description(), "Spanish - SUBRIP - Externo")
        self.assertEqual(emb_sub.format_description(), "Latin American - PGSSUB")

        movie = MovieMediaAsset(
            folder_name="Dune (2021)",
            video_filename="Dune.2021.mkv",
            size=FileSizeBytes(10 * 1024**3),
            link_count=InodeLinkCount(2),
            external_srt_files=("Dune.2021.es.srt",),
            jellyfin_title="Dune",
            jellyfin_spanish_streams=(ext_sub, emb_sub),
        )
        self.assertTrue(movie.has_video_file)
        self.assertTrue(movie.is_indexed_in_jellyfin)
        self.assertEqual(len(movie.jellyfin_spanish_streams), 2)

        empty_movie = MovieMediaAsset(folder_name="Empty Folder (2025)")
        self.assertFalse(empty_movie.has_video_file)
        self.assertFalse(empty_movie.is_indexed_in_jellyfin)


if __name__ == "__main__":
    unittest.main()
