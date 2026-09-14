# Backup and restore foundation

Production deployments must use encrypted PostgreSQL backups, object-storage versioning and separately protected encryption keys. A release is not considered operationally ready until a restore has been rehearsed into an isolated environment, migrations have been checked, record counts have been reconciled and application smoke tests have passed.

No successful live restore rehearsal is claimed from the development sandbox.
