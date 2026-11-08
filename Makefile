.PHONY: backup-postgres

# Operator-run pg_dump. DATABASE_URL is required and is not stored here.
backup-postgres:
	@test -n "$(DATABASE_URL)" || (echo "Set DATABASE_URL. This target does not embed credentials." >&2; exit 1)
	./scripts/backup_postgres.sh
