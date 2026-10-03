"""Download helpers for importer adapters. Every download is checked against a published integrity value where one exists,
and the SHA-256 of what was actually read is recorded in the output so the manifest can pin it."""
import base64
import hashlib
import io
import json
import tarfile
import urllib.request

REGISTRY = "https://registry.npmjs.org"
UA = {"User-Agent": "WorldOfIslam-importer/1.0 (+https://app.arfaat.com/worldofislam)"}


# Importers may only contact these hosts, over HTTPS. A URL that arrives inside downloaded metadata (an npm tarball link, a redirect) is checked
# against the same list, so a hostile registry entry cannot make the server fetch an internal address (SSRF).
ALLOWED_HOSTS = frozenset({"registry.npmjs.org", "raw.githubusercontent.com", "pypi.org", "files.pythonhosted.org", "overpass-api.de", "query.wikidata.org",
                           "www.wikidata.org", "openlibrary.org", "archive.org"})


def check_url(url: str) -> str:
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    if parts.scheme != "https" or (parts.hostname or "") not in ALLOWED_HOSTS or parts.username or parts.port not in (None, 443):
        raise ValueError(f"importers may only fetch https URLs on an approved host; refused: {parts.scheme}://{parts.hostname}")
    return url


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # a redirect target is checked like any other URL
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url: str, timeout: int = 120) -> bytes:
    check_url(url)
    opener = urllib.request.build_opener(_NoRedirect)
    with opener.open(urllib.request.Request(url, headers=UA), timeout=timeout) as response:
        return response.read()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def npm_package(name: str, version: str) -> tuple[dict, dict[str, bytes], str]:
    """Return (package.json, {path: bytes}, tarball sha256) for an exact npm version, verifying the registry's sha512 integrity."""
    meta = json.loads(fetch(f"{REGISTRY}/{name.replace('/', '%2F')}/{version}"))
    tarball = fetch(meta["dist"]["tarball"], timeout=300)
    integrity = meta["dist"].get("integrity", "")
    if integrity.startswith("sha512-"):
        if base64.b64encode(hashlib.sha512(tarball).digest()).decode() != integrity[7:]:
            raise SystemExit(f"integrity check failed for {name}@{version}: refusing to use the download")
    else:
        raise SystemExit(f"{name}@{version} publishes no sha512 integrity value; cannot verify the download")
    files: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as archive:
        for member in archive.getmembers():
            if member.isfile():
                files[member.name.split("/", 1)[1] if "/" in member.name else member.name] = archive.extractfile(member).read()  # type: ignore[union-attr]
    return json.loads(files["package.json"]), files, sha256(tarball)
