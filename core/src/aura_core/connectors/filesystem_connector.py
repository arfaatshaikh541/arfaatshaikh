"""Local filesystem connector. No credentials needed, but sandboxed to a
single root directory — every path is resolved and checked to be inside
that root before any read/write/list, closing the obvious path-traversal
hole (`../../etc/passwd`) a naive implementation would have.
"""
from __future__ import annotations

from pathlib import Path

from ..governance.action_broker import ActionRequest, HandlerResult
from ..status import CapabilityStatus
from .base import Connector, ConnectorManifest


class PathEscapesSandboxError(RuntimeError):
    pass


class FilesystemConnector(Connector):
    def __init__(self, root_dir: str) -> None:
        self._root = Path(root_dir).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self.manifest = ConnectorManifest(
            name="filesystem",
            auth_method="none",
            capabilities=["filesystem.read_file", "filesystem.write_file", "filesystem.list_dir"],
            notes=f"sandboxed to {self._root}",
        )

    def _resolve(self, relative_path: str) -> Path:
        candidate = (self._root / relative_path).resolve()
        if candidate != self._root and self._root not in candidate.parents:
            raise PathEscapesSandboxError(f"'{relative_path}' resolves outside the sandbox root")
        return candidate

    def health_check(self) -> HandlerResult:
        if self._root.exists() and self._root.is_dir():
            return HandlerResult(CapabilityStatus.LIVE, f"sandbox root {self._root} is accessible")
        return HandlerResult(CapabilityStatus.UNAVAILABLE, f"sandbox root {self._root} is not accessible")

    def read_file(self, request: ActionRequest) -> HandlerResult:
        try:
            path = self._resolve(request.params["path"])
            if not path.exists():
                return HandlerResult(CapabilityStatus.DEGRADED, f"'{request.params['path']}' does not exist")
            return HandlerResult(CapabilityStatus.LIVE, path.read_text())
        except PathEscapesSandboxError as exc:
            return HandlerResult(CapabilityStatus.BLOCKED_BY_POLICY, str(exc))

    def write_file(self, request: ActionRequest) -> HandlerResult:
        try:
            path = self._resolve(request.params["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(request.params["content"])
            return HandlerResult(CapabilityStatus.LIVE, f"wrote {len(request.params['content'])} bytes to {request.params['path']}")
        except PathEscapesSandboxError as exc:
            return HandlerResult(CapabilityStatus.BLOCKED_BY_POLICY, str(exc))

    def list_dir(self, request: ActionRequest) -> HandlerResult:
        try:
            path = self._resolve(request.params.get("path", "."))
            if not path.is_dir():
                return HandlerResult(CapabilityStatus.DEGRADED, f"'{request.params.get('path', '.')}' is not a directory")
            entries = sorted(p.name for p in path.iterdir())
            return HandlerResult(CapabilityStatus.LIVE, "\n".join(entries))
        except PathEscapesSandboxError as exc:
            return HandlerResult(CapabilityStatus.BLOCKED_BY_POLICY, str(exc))

    def handlers(self) -> dict:
        return {
            "filesystem.read_file": self.read_file,
            "filesystem.write_file": self.write_file,
            "filesystem.list_dir": self.list_dir,
        }
