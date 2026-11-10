from typing import Sequence

from media_stack.application.audit_report_dto import StackAuditReport
from media_stack.domain.entities.bootstrap_step import BootstrapStepResult


class ConsoleAuditPresenter:
    """Presenter that renders a StackAuditReport to the terminal with ANSI colors."""

    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    def _print_header(self, title: str) -> None:
        print(f"\n{self.BOLD}{self.CYAN}{'=' * 60}{self.RESET}")
        print(f"{self.BOLD}{self.CYAN}  {title}{self.RESET}")
        print(f"{self.BOLD}{self.CYAN}{'=' * 60}{self.RESET}")

    def render(self, report: StackAuditReport) -> None:
        print(f"\n{self.BOLD}🔍 INICIANDO AUDITORÍA DEL MEDIA STACK (DDD Engine){self.RESET}")

        # 1. Containers & Mounts
        self._print_header("1. ESTADO DE CONTENEDORES DOCKER")
        for c in report.containers:
            if c.is_running:
                print(
                    f"  {self.GREEN}✔{self.RESET} {c.name:<16} : {self.GREEN}{c.state}{self.RESET}"
                )
            else:
                print(
                    f"  {self.RED}✘{self.RESET} {c.name:<16} : {self.RED}{c.state}{self.RESET}"
                )

        print(f"\n  {self.BOLD}Puntos de montaje de almacenamiento (/data):{self.RESET}")
        for m in report.mount_checks:
            if m.is_accessible:
                print(
                    f"  {self.GREEN}✔{self.RESET} {m.container_name:<16} : "
                    f"{self.GREEN}Montura activa ({m.mount_point}){self.RESET}"
                )
            else:
                print(
                    f"  {self.RED}✘{self.RESET} {m.container_name:<16} : "
                    f"{self.RED}Montura caída/stale ({m.mount_point}){self.RESET}"
                )

        # 2. VPN & Port Forwarding
        self._print_header("2. VPN PROTONVPN Y SINCRONIZACIÓN DE PUERTO")
        vpn = report.vpn_status
        if vpn.has_public_ip:
            print(
                f"  {self.GREEN}✔{self.RESET} IP Pública VPN    : "
                f"{self.BOLD}{vpn.public_ip}{self.RESET} ({vpn.city}, {vpn.country}) - {vpn.organization}"
            )
        else:
            print(
                f"  {self.RED}✘{self.RESET} IP Pública VPN    : "
                f"{self.RED}No se pudo resolver salida a internet desde Gluetun{self.RESET}"
            )

        print(
            f"  {self.GREEN if vpn.forwarded_port else self.RED}"
            f"{'✔' if vpn.forwarded_port else '✘'}{self.RESET} Puerto ProtonVPN  : "
            f"{vpn.forwarded_port or 'No asignado'}"
        )
        print(
            f"  {self.GREEN if vpn.qbit_listen_port else self.RED}"
            f"{'✔' if vpn.qbit_listen_port else '✘'}{self.RESET} Puerto qBittorrent: "
            f"{vpn.qbit_listen_port or 'Inaccesible'}"
        )

        if vpn.is_port_synced:
            print(
                f"  {self.GREEN}✔{self.RESET} Sincronización   : "
                f"{self.GREEN}ÓPTIMA (qBittorrent escucha exactamente en el puerto forwarded){self.RESET}"
            )
        else:
            print(
                f"  {self.YELLOW}⚠{self.RESET} Sincronización   : "
                f"{self.YELLOW}DESFASE ({vpn.forwarded_port} != {vpn.qbit_listen_port}){self.RESET}"
            )

        # 3. Web Services & APIs
        self._print_header("3. ESTADO DE SERVICIOS Y APIS WEB")
        for s in report.service_results:
            if s.is_online:
                print(
                    f"  {self.GREEN}✔{self.RESET} {s.service_name:<14} : "
                    f"{self.GREEN}En línea (HTTP {s.http_status}){self.RESET}"
                )
            else:
                code_str = f"HTTP {s.http_status}" if s.http_status else "Inaccesible"
                print(
                    f"  {self.RED}✘{self.RESET} {s.service_name:<14} : "
                    f"{self.RED}{code_str}{self.RESET}"
                )

        if report.bazarr_providers:
            print(
                f"  {self.CYAN}ℹ Proveedores Bazarr:{self.RESET} "
                f"{', '.join(report.bazarr_providers)}"
            )

        # 4. Media Library, Hardlinks & Subtitles
        self._print_header("4. BIBLIOTECA MULTIMEDIA, HARDLINKS Y SUBTÍTULOS")
        if not report.movies_dir_exists:
            print(
                f"  {self.RED}✘ Directorio de medios no encontrado en {report.movies_dir_path}{self.RESET}"
            )
            return

        print(
            f"  Películas detectadas en disco: {self.BOLD}{len(report.movies)}{self.RESET}\n"
        )
        for movie in report.movies:
            print(f"  {self.BOLD}📁 {movie.folder_name}{self.RESET}")
            if not movie.has_video_file or not movie.size or not movie.link_count:
                print(
                    f"     {self.YELLOW}⚠ No se encontró archivo de video principal.{self.RESET}"
                )
                continue

            if movie.link_count.is_hardlinked:
                print(
                    f"     {self.GREEN}✔ Hardlink APFS :{self.RESET} Compartido con torrents "
                    f"({movie.link_count.count} enlaces). 0 bytes duplicados. ({movie.size.format_gb()})"
                )
            else:
                print(
                    f"     {self.YELLOW}ℹ Almacenamiento:{self.RESET} Archivo independiente "
                    f"(1 enlace, {movie.size.format_gb()})"
                )

            if movie.external_srt_files:
                for srt in movie.external_srt_files:
                    print(f"     {self.GREEN}✔ Subtítulo .srt:{self.RESET} {srt}")
            else:
                print(
                    f"     {self.CYAN}ℹ Sin archivos .srt externos (usa pistas incrustadas del contenedor){self.RESET}"
                )

            if movie.is_indexed_in_jellyfin:
                if movie.jellyfin_spanish_streams:
                    descs = [
                        st.format_description() for st in movie.jellyfin_spanish_streams
                    ]
                    print(
                        f"     {self.GREEN}✔ Jellyfin [{movie.jellyfin_title}]:{self.RESET} "
                        f"{len(descs)} pista(s) en español -> {', '.join(descs)}"
                    )
                else:
                    print(
                        f"     {self.YELLOW}⚠ Jellyfin [{movie.jellyfin_title}]:{self.RESET} "
                        f"Indexada, pero sin pistas marcadas como español."
                    )
            else:
                print(
                    f"     {self.RED}✘ Jellyfin:{self.RESET} Película aún no indexada en biblioteca."
                )
            print()

        print(f"{self.BOLD}{self.GREEN}✨ Auditoría completada.{self.RESET}\n")

    def render_bootstrap(self, steps: Sequence[BootstrapStepResult]) -> None:
        self._print_header("AUTO-APROVISIONAMIENTO E INTERCONEXIÓN DEL MEDIA STACK")
        for s in steps:
            icon = f"{self.GREEN}✔{self.RESET}" if s.succeeded else f"{self.YELLOW}⚠{self.RESET}"
            color = self.GREEN if s.succeeded else self.YELLOW
            print(f"  {icon} {s.step_name:<36} : {color}{s.details}{self.RESET}")
        print(f"\n{self.BOLD}{self.GREEN}✨ Bootstrap finalizado.{self.RESET}\n")
