"""GRIDKEEP sovereignty policy evaluation service.

A stateless, deterministic evaluator: given a policy document and a
candidate workload/location, it runs a fixed constraint pipeline and
returns an ALLOW/DENY decision with reason codes (see evaluate.py), plus
static conflict detection between two policies (see conflicts.py). Policy
CRUD, versioning, and the dual-control publish/approve/rollback workflow
live in control-api, which calls this service -- see
docs/adr/0008-policy-engine-http-transport.md for why this integration is
plain HTTP/JSON rather than gRPC.
"""

__version__ = "0.1.0"
