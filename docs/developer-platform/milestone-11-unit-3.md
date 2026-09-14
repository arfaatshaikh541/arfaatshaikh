# Milestone 11 Unit 3: API Products, Versioning, SDKs, and Sandbox

This unit governs API product publication, immutable version lifecycle, documentation integrity, SDK release provenance, and bounded developer sandbox access.

## Safety boundaries

- Deprecated or retired API versions require at least 90 days of notice and a valid successor.
- Breaking changes cannot be hidden inside a current version.
- Documentation and packages require public HTTPS locations and SHA-256 fingerprints.
- SDK publication requires passing tests and verified provenance.
- Sandboxes permit bounded read-only scopes; assistant execution is excluded.

## Deployment limitations

Live package registries, generated SDKs, documentation hosting, distributed sandbox quotas, and browser developer-console testing remain deployment work.
