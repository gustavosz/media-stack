# ==============================================================================
# MEDIA STACK — Interfaz Unificada de Operaciones
# ==============================================================================
PYTHONPATH := $(CURDIR)/src
PYTHON     := PYTHONPATH=$(PYTHONPATH) python3 -m media_stack

.PHONY: help up down restart ps logs audit sync-port daemon-install daemon-uninstall daemon-status

help: ## Muestra esta guía de comandos disponibles
	@echo ""
	@echo "🎬 Media Stack — Comandos Disponibles:"
	@echo "=================================================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""

up: ## Levanta todos los servicios del Media Stack en segundo plano
	docker compose up -d

down: ## Detiene todos los contenedores del Media Stack
	docker compose down

restart: ## Reinicia todos los contenedores del Media Stack
	docker compose restart

ps: ## Muestra el estado actual de los contenedores
	docker compose ps

logs: ## Muestra los logs en tiempo real de todos los servicios
	docker compose logs -f --tail=100

audit: ## Ejecuta la auditoría completa del stack (Contenedores, VPN, APIs, Hardlinks y Subtítulos)
	@$(PYTHON) audit

sync-port: ## Verifica y sincroniza el puerto NAT-PMP de ProtonVPN con qBittorrent
	@$(PYTHON) sync-port

daemon-install: ## Instala y activa el daemon de auto-recuperación de discos externos en macOS
	@$(PYTHON) daemon install

daemon-uninstall: ## Detiene y desinstala el daemon de auto-recuperación de discos en macOS
	@$(PYTHON) daemon uninstall

daemon-status: ## Verifica el estado actual del daemon de monitoreo de discos
	@$(PYTHON) daemon status
