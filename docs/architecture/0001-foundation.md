# Foundation architecture

The first implementation unit uses three deployable applications: Next.js web, FastAPI API and Celery worker. PostgreSQL is the future system of record, Redis is ephemeral coordination infrastructure, and MinIO provides local S3-compatible object storage.

Liveness reports only whether the API process can serve requests. Readiness verifies PostgreSQL, Redis and the configured S3 bucket. This prevents an orchestrator from sending traffic to a process whose dependencies are unavailable.

The backend network is internal. Only the web and API services join the frontend network. Database, Redis and object-store ports are not published to the host by default.
