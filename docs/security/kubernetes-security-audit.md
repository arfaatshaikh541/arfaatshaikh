# Kubernetes-Security Audit

**Scope:** `internal/platform/clusteradapter` (the delegated, mocked interface to an operator's
Kubernetes cluster), the deployment-plan validation flow that calls it, the manifest-construction
code in `internal/modules/deployments`, and the non-root posture of this milestone's new production
Dockerfiles. **Method:** exhaustive review; every claim cites a real `file:line`.

## Architecture context (why this audit's scope is what it is)

This codebase has never integrated a real Kubernetes client (`client-go`) — `clusteradapter`'s own
package doc says so explicitly, and this has been an accepted, documented scope boundary since the
milestone that introduced it (Milestone 6). The only implementation of the `ClusterAdapter` interface
anywhere in this repository is an in-memory `Mock`. Every "deployment," "namespace," "network
policy," and "security context" this codebase creates is an opaque `map[string]any` passed through
that mock — never serialized into, or validated against, an actual Kubernetes API object schema. This
audit evaluates that reality directly, rather than auditing a Kubernetes integration that does not
exist.

## Finding (Medium-High): zero content validation on deployment manifests, resource quotas, network policies, or security contexts

Every one of `clusteradapter`'s exported methods (`CreateNamespace`, `ApplyResourceQuota`,
`ApplyNetworkPolicy`, `ApplySecurityContext`, `DeployWorkload`, `ScaleWorkload`, `PauseWorkload`,
`ResumeWorkload`, `RollbackWorkload`, `TerminateWorkload`) accepts its most important argument as an
untyped `map[string]any` and validates **only structural/protocol ordering** — a namespace must
exist before a quota/policy/security-context/deployment can reference it, a replica count must be
positive, a deployment must exist before it can be scaled/paused/resumed/rolled-back/terminated.

**No code anywhere in this codebase inspects the actual content of a manifest, resource quota,
network policy, or security context for anything security-relevant.** Confirmed by exhaustive grep
across `internal/modules/deployments` and `internal/platform/clusteradapter`: zero matches for
`privileged`, `hostNetwork`, `hostPID`, `hostIPC`, `hostPath`, `runAsNonRoot`,
`readOnlyRootFilesystem`, or `capabilities`. Concretely, this means:

- A workload's `security_requirements` (tenant-supplied JSON, captured at workload-version-draft
  time in `internal/modules/workloads`) flows unchanged through `buildManifest`
  (`internal/modules/deployments/service.go`) into the signed deployment manifest sent to the
  cluster agent, with no check anywhere that it doesn't request a privileged container, host
  namespace access, or a sensitive `hostPath` mount.
- The mock cluster agent's own local "plan validation" (`evaluatePlan` in `cmd/mockclusteragent`)
  checks only that the plan's declared cluster ID matches what the agent believes it is
  (`CLUSTER_ID_MISMATCH` if not) and that the underlying (also content-blind) adapter calls don't
  error — there is no semantic "reject an unsafe manifest" check anywhere in this codebase, despite
  "unsafe Kubernetes manifest" appearing explicitly as a named concern in the original approved
  architecture brief.
- `ApplyNetworkPolicy` stores its opaque map verbatim with no ingress/egress rule schema defined or
  validated anywhere — network isolation between workloads at the Kubernetes-manifest level is
  entirely unaddressed by this code (this codebase's *application-level* tenant/operator isolation,
  audited separately in `docs/security/tenant-isolation-audit.md`, is unrelated and does not
  substitute for pod-to-pod network policy at the cluster level).

**Why this is Medium-High, not Critical, today**: no real Kubernetes cluster is ever actually
provisioned or mutated by any code in this repository — every "deployment" is confined to the mock
adapter's in-memory state. There is no currently-exploitable path to a real privilege escalation
inside a real cluster, because there is no real cluster this code ever touches. The severity is
Medium-High because **this is a real architectural gap that must be closed before this system
integrates a real Kubernetes client**, not a hypothetical: the moment `clusteradapter.Mock` is
replaced with a `client-go`-backed implementation (the natural next step for a production rollout),
every tenant-supplied `security_requirements`/`resource_requirements` value would flow, unvalidated,
straight into a real `PodSpec` unless this gap is closed first.

**Recommendation:** before any real Kubernetes integration, add explicit Pod Security
Standards-equivalent validation at the point `buildManifest` assembles a manifest from tenant input
— reject (not merely warn on) `privileged: true`, any `hostNetwork`/`hostPID`/`hostIPC: true`,
any `hostPath` volume, and any container running as root unless an explicit, narrowly-scoped
exception mechanism (mirroring the images module's dual-control vulnerability-exception pattern) is
deliberately added. This validation belongs in application code (defense-in-depth, matching this
codebase's "verify before trusting" discipline everywhere else), in addition to — never instead of —
cluster-side enforcement (a real Kubernetes deployment should also run with Pod Security Admission
configured to the `restricted` profile as a second, independent layer).

## Pod security posture — not applicable yet, tracked above

Since no real manifest is ever constructed, there is no `runAsNonRoot`/capability-dropping/
`readOnlyRootFilesystem` configuration to evaluate on the application-workload side — this doesn't
exist as a gap distinct from the finding above; it's the same gap, restated. It will need to be
built as part of closing the finding above.

## This milestone's own container images — correct non-root posture

All four of this milestone's new production Dockerfiles run as non-root:

| Service | User |
|---|---|
| control-api | `nonroot:nonroot` (distroless, uid/gid 65532) |
| worker | `nonroot:nonroot` (distroless, uid/gid 65532) |
| policy-engine | `policyengine` (dedicated, uid/gid 65532) |
| web | `nextjs` (dedicated, uid 1001) |

This is the correct posture *for this codebase's own control-plane services* (a separate concern
from the finding above, which is about workloads *this platform deploys on behalf of tenants*, not
the platform's own containers).

## Helm chart status

`infrastructure/helm` is confirmed empty at the time of this audit — a scaffold directory with no
content, built out later in this same milestone (see `docs/deployment/production-deployment.md` and
the Helm charts themselves). Any future chart for the operator-facing cluster-agent component should
bake in the Pod Security Standards configuration this finding recommends (Pod Security Admission
labels at minimum), since the chart is the natural place to enforce it at the cluster level even
after the application-level validation above is added.

## Verdict

The most significant finding in this milestone's three technical audits: this codebase has **no
content validation whatsoever** on the Kubernetes-shaped data it accepts from tenants and would, in
its current form, pass a request for a privileged/host-namespace/hostPath-mounting container straight
through to a real cluster if one were ever wired up. Not currently exploitable (no real cluster
exists to exploit), but a concrete, must-fix-before-production architectural gap, clearly scoped and
recommended above. Every other Kubernetes-adjacent concern this audit checked (this milestone's own
container non-root posture, Helm scaffold status) is either already correct or appropriately deferred.
