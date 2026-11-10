from __future__ import annotations

import argparse
import sys

from media_stack.interface.console_audit_presenter import ConsoleAuditPresenter
from media_stack.interface.container import DependencyContainer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="media_stack",
        description="CLI de Administración y Monitoreo del Media Stack (DDD Architecture)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: audit
    subparsers.add_parser(
        "audit",
        help="Ejecuta una auditoría completa de contenedores, VPN, APIs, hardlinks y subtítulos.",
    )

    # Subcommand: watch-disk
    subparsers.add_parser(
        "watch-disk",
        help="Inicia el bucle de monitoreo y auto-recuperación del disco externo.",
    )

    # Subcommand: sync-port
    subparsers.add_parser(
        "sync-port",
        help="Verifica y sincroniza el puerto NAT-PMP de ProtonVPN con qBittorrent.",
    )

    # Subcommand: daemon
    daemon_parser = subparsers.add_parser(
        "daemon",
        help="Gestiona el servicio de auto-recuperación en segundo plano (macOS LaunchAgent).",
    )
    daemon_parser.add_argument(
        "action",
        choices=["install", "uninstall", "status"],
        help="Acción a realizar sobre el daemon de macOS.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    di = DependencyContainer()

    if args.command == "audit":
        use_case = di.build_audit_use_case()
        report = use_case.execute()
        ConsoleAuditPresenter().render(report)
        return 0

    if args.command == "watch-disk":
        use_case = di.build_monitor_disk_use_case()
        use_case.run_forever()
        return 0

    if args.command == "sync-port":
        use_case = di.build_sync_vpn_port_use_case()
        return 0 if use_case.execute() else 1

    if args.command == "daemon":
        use_case = di.build_manage_daemon_use_case()
        if args.action == "install":
            plist_path = use_case.install()
            print(f"✅ Daemon instalado y activado exitosamente en: {plist_path}")
            print(f"   Logs: {di.settings.disk_watcher_log}")
            return 0
        if args.action == "uninstall":
            removed = use_case.uninstall()
            if removed:
                for p in removed:
                    print(f"✅ Daemon detenido y eliminado: {p}")
            else:
                print("ℹ️ El daemon no se encontraba instalado.")
            return 0
        if args.action == "status":
            status_line = use_case.status()
            if status_line:
                print(f"✅ Daemon activo en launchctl: {status_line}")
            else:
                print("ℹ️ El daemon no está registrado actualmente en launchctl.")
            return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
