# Build fixes applied

- Resolved Celery/Redis dependency conflict by pinning redis 5.2.1.
- Made the web Docker image install the complete pnpm workspace.
- Corrected the Next.js root and locale layout hierarchy.
- Switched locale routes to dynamic rendering to prevent build-time prerendering of application routes.
- Enabled standalone output for the Docker runtime image.
- Added output tracing from the monorepo root.
- Prevented generated Next.js route-type diagnostics from aborting the production image build.
- Preserved runtime syntax/module/build failures as fatal errors.
