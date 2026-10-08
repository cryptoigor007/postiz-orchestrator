# Runbook: Rollback
1. Restore SQLite from backups/pre_migration_*
2. Pin schema_version if needed
3. engines remain module:youtube / module:telegram
4. No Postiz transport to restore
