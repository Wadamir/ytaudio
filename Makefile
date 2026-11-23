# Define default shell environment
SHELL := /bin/bash

# Configuration and path variables
BOT_CONTAINER_NAME := tg-ytaudio-bot
DB_FILE_PATH := storage/db/bot.sqlite3

.PHONY: help up down restart status logs clean db-reset

# Display available automation commands by default
help:
	@echo "Available automation commands:"
	@echo "  make up       - Build and start all bot containers in background mode"
	@echo "  make down     - Stop and remove all running bot containers and networks"
	@echo "  make restart  - Completely restart bot infrastructure with fresh environment configurations"
	@echo "  make status   - Show actual status of infrastructure containers"
	@echo "  make logs     - Follow latest container runtime output streams"
	@echo "  make db-reset - Safely clear internal sqlite database state tables to refresh proxy routes"

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

# Remove internal database state structures forcing route re-indexing configuration flows
db-reset:
	@if [ -f $(DB_FILE_PATH) ]; then \
		docker compose down; \
		rm -f $(DB_FILE_PATH); \
		echo "Database file $(DB_FILE_PATH) successfully removed."; \
		docker compose up -d --build; \
	else \
		echo "Database file $(DB_FILE_PATH) does not exist. Starting environment normally..."; \
		docker compose up -d --build; \
	fi
