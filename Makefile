# Define default shell environment
SHELL := /bin/bash

# Configuration and path variables
BOT_CONTAINER_NAME := tg-ytaudio-bot
DB_FILE_PATH := storage/db/bot.sqlite3

.PHONY: help up down restart status logs clean db-reset virtues full-reset

# Display available automation commands by default
help:
	@echo "Available automation commands:"
	@echo "  make up         - Build and start all bot containers in background mode"
	@echo "  make down       - Stop and remove all running bot containers and networks"
	@echo "  make restart    - Completely restart bot infrastructure with fresh configurations"
	@echo "  make status     - Show actual status of infrastructure containers"
	@echo "  make logs       - Follow latest container runtime output streams"
	@echo "  make db-reset   - Safely clear internal database and force clean rebuild with no-cache flag"
	@echo "  make full-reset - Pull latest changes via git, reset database, and rebuild entire stack with no-cache"

# Build image and launch container infrastructure
up:
	docker compose up -d --build

# Bring down running container environments and clear networks
down:
	docker compose down

# Stop application instances, apply variable configurations and start cleanly
restart: down up

# Inspect current runtime status metrics of infrastructure containers
status:
	docker compose ps

# Follow container console log output streams live
logs:
	docker compose logs -f bot --tail 50

# Remove internal database state structures and perform a forced clean image rebuild without cache
db-reset:
	@if [ -f $(DB_FILE_PATH) ]; then \
		docker compose down; \
		rm -f $(DB_FILE_PATH); \
		echo "Database file $(DB_FILE_PATH) successfully removed."; \
		docker compose build --no-cache && docker compose up -d; \
	else \
		echo "Database file $(DB_FILE_PATH) does not exist. Executing forced clean re-build..."; \
		docker compose down; \
		docker compose build --no-cache && docker compose up -d; \
	fi

# Complete pipeline: fetch production changes, wipe state tables, and re-compile application layers cleanly
full-reset:
	@echo "Starting full repository update and environment rebuild workflow..."
	git pull --rebase
	@if [ -f $(DB_FILE_PATH) ]; then \
		docker compose down; \
		rm -f $(DB_FILE_PATH); \
		echo "Database state storage dropped successfully."; \
	else \
		docker compose down; \
	fi
	docker compose build --no-cache
	docker compose up -d
	@echo "Forced clean pipeline full-reset execution completed successfully."
