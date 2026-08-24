"""Extension manager: install, store, and assign extensions to profiles.

Supports:
- Unpacked directories
- .crx files
- Chrome Web Store IDs (download via CRX URL)

Extensions are stored centrally under data/extensions/<ext_id>/ and
assigned per-profile. The launcher passes --load-extension args.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import urllib.parse
import urllib.request
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .safe_archive import safe_extract_zip


log = logging.getLogger("antique.extension")


@dataclass
class Extension:
    """Metadata for an installed extension."""
    ext_id: str  # short unique id
    name: str
    version: str = "0.0.0"
    description: str = ""
    source_type: str = ""  # "crx", "unpacked", "webstore"
    path: str = ""  # absolute path to the unpacked extension directory
    manifest: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _generate_ext_id(name: str, path_hint: str = "") -> str:
    """Generate a short extension ID from name + path."""
    raw = f"{name}:{path_hint}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]


def _read_manifest(ext_dir: Path) -> Dict[str, Any]:
    """Read manifest.json from an extension directory."""
    manifest_path = ext_dir / "manifest.json"
    if not manifest_path.exists():
        raise ValueError(f"No manifest.json found in {ext_dir}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _extract_crx(crx_path: Path, dest_dir: Path) -> None:
    """Extract a .crx file (which is a zip with a header) to dest_dir."""
    content = crx_path.read_bytes()
    # CRX3 format: magic(4) + version(4) + header_size(4) + header + zip
    # CRX2 format: magic(4) + version(4) + pub_key_len(4) + sig_len(4) + pub_key + sig + zip
    # Both: find the PK zip magic
    zip_start = content.find(b"PK\x03\x04")
    if zip_start < 0:
        raise ValueError("Not a valid CRX file (no ZIP content found)")
    import io
    zip_data = io.BytesIO(content[zip_start:])
    with zipfile.ZipFile(zip_data) as zf:
        safe_extract_zip(zf, dest_dir)


class ExtensionStore:
    """Manages installed extensions on disk."""

    def __init__(self, data_root: Optional[Path] = None):
        self.data_root = data_root or Path(os.environ.get("ANTIDETECT_DATA_DIR", "data"))
        self.ext_dir = self.data_root / "extensions"
        self.ext_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.ext_dir / "_index.json"
        self._extensions: Dict[str, Extension] = {}
        self._load_index()

    def _load_index(self) -> None:
        if self._index_path.exists():
            try:
                data = json.loads(self._index_path.read_text(encoding="utf-8"))
                for item in data:
                    ext = Extension(**item)
                    self._extensions[ext.ext_id] = ext
            except (json.JSONDecodeError, TypeError):
                self._extensions = {}

    def _save_index(self) -> None:
        data = [ext.to_dict() for ext in self._extensions.values()]
        self._index_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def list(self) -> List[Extension]:
        return list(self._extensions.values())

    def get(self, ext_id: str) -> Optional[Extension]:
        return self._extensions.get(ext_id)

    def install_from_unpacked(
        self, source_dir: Path, name: Optional[str] = None,
        chrome_ext_id: Optional[str] = None,
    ) -> Extension:
        """Install an extension from an unpacked directory.

        Args:
            source_dir: Path to the unpacked extension directory.
            name: Override the extension name (defaults to manifest ``name``).
            chrome_ext_id: The original Chrome Web Store extension ID
                (32-char lowercase). When provided, stored in manifest as
                ``_chrome_ext_id`` for later lookups.
        """
        source_dir = Path(source_dir)
        if not source_dir.is_dir():
            raise ValueError(f"Not a directory: {source_dir}")
        manifest = _read_manifest(source_dir)
        ext_name = name or manifest.get("name", source_dir.name)
        ext_id = _generate_ext_id(ext_name, str(source_dir))

        # Copy to our storage
        dest = self.ext_dir / ext_id
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(source_dir, dest)

        # Store chrome_ext_id in manifest for reverse lookup
        if chrome_ext_id:
            manifest["_chrome_ext_id"] = chrome_ext_id

        ext = Extension(
            ext_id=ext_id,
            name=ext_name,
            version=manifest.get("version", "0.0.0"),
            description=manifest.get("description", ""),
            source_type="unpacked",
            path=str(dest),
            manifest=manifest,
        )
        self._extensions[ext_id] = ext
        self._save_index()
        return ext

    def install_from_crx(self, crx_path: Path, name: Optional[str] = None) -> Extension:
        """Install an extension from a .crx file."""
        crx_path = Path(crx_path)
        if not crx_path.exists():
            raise FileNotFoundError(f"CRX file not found: {crx_path}")

        # Extract to temp, read manifest, then move to final location
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp) / "ext"
            _extract_crx(crx_path, tmp_dir)
            manifest = _read_manifest(tmp_dir)
            ext_name = name or manifest.get("name", crx_path.stem)
            ext_id = _generate_ext_id(ext_name, str(crx_path))

            dest = self.ext_dir / ext_id
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(tmp_dir, dest)

        ext = Extension(
            ext_id=ext_id,
            name=ext_name,
            version=manifest.get("version", "0.0.0"),
            description=manifest.get("description", ""),
            source_type="crx",
            path=str(dest),
            manifest=manifest,
        )
        self._extensions[ext_id] = ext
        self._save_index()
        return ext

    def search_webstore(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search Chrome Web Store and return installable extension summaries.

        The Web Store has no supported public search API, so this uses its
        public search page and only extracts detail links. Network failures are
        surfaced to the API caller instead of returning fake results.
        """
        query = (query or "").strip()
        if not query:
            raise ValueError("search query is required")
        limit = max(1, min(int(limit), 50))
        url = "https://chromewebstore.google.com/search/" + urllib.parse.quote(query)
        request = urllib.request.Request(
            url,
            headers={"Accept": "text/html", "User-Agent": "antique-extension-search/1"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            html = response.read().decode("utf-8", errors="replace")

        results: List[Dict[str, Any]] = []
        seen = set()
        pattern = re.compile(r"/detail/([^/\\\"?]+)(?:/[^\\\"?]*)?")
        for match in pattern.finditer(html):
            ext_id = match.group(1)
            if not re.fullmatch(r"[a-z]{32}", ext_id) or ext_id in seen:
                continue
            seen.add(ext_id)
            start, end = max(0, match.start() - 300), min(len(html), match.end() + 500)
            context = re.sub(r"<[^>]+>", " ", html[start:end])
            context = re.sub(r"\\s+", " ", context).strip()
            results.append({
                "webstore_id": ext_id,
                "name": context[:160] or ext_id,
                "url": f"https://chromewebstore.google.com/detail/{ext_id}",
            })
            if len(results) >= limit:
                break
        return results

    def install_from_webstore(self, webstore_id: str, name: Optional[str] = None) -> Extension:
        """Download and install from Chrome Web Store.

        Uses the CRX download endpoint:
        https://clients2.google.com/service/update2/crx?response=redirect&prodversion=130.0&x=id%3D{id}%26installsource%3Dondemand%26uc
        """
        import tempfile
        import urllib.request

        url = (
            f"https://clients2.google.com/service/update2/crx"
            f"?response=redirect&prodversion=130.0"
            f"&x=id%3D{webstore_id}%26installsource%3Dondemand%26uc"
        )
        with tempfile.NamedTemporaryFile(suffix=".crx", delete=False) as tmp:
            try:
                urllib.request.urlretrieve(url, tmp.name)
                ext = self.install_from_crx(Path(tmp.name), name=name)
                ext.source_type = "webstore"
                self._extensions[ext.ext_id] = ext
                self._save_index()
                return ext
            finally:
                try:
                    os.unlink(tmp.name)
                except OSError:
                    pass

    def uninstall(self, ext_id: str) -> bool:
        """Remove an extension."""
        ext = self._extensions.pop(ext_id, None)
        if ext is None:
            return False
        dest = self.ext_dir / ext_id
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        self._save_index()
        return True

    def install_from_adspower_env(
        self,
        chrome_ext_id: str,
        name: Optional[str] = None,
        adspower_root: Optional[Path] = None,
    ) -> Optional[Extension]:
        """Install an extension from the AdsPower global extension store.

        AdsPower stores extension code under::

            C:\\.ADSPOWER_GLOBAL\\ext_env\\<serial>\\      (by serial number)
            C:\\.ADSPOWER_GLOBAL\\ext\\<chrome_ext_id>\\   (by Chrome ext ID)

        The ``record`` JSON file in ``ext_env/`` maps serial → Chrome ID.

        This method looks up ``ext/<chrome_ext_id>/`` first (direct),
        then scans ``ext_env/record`` for a matching ``unique_id``.

        Returns ``None`` if the extension is not found on disk.
        """
        adspower_root = Path(adspower_root or os.environ.get(
            "ADSPOWER_GLOBAL", r"C:\.ADSPOWER_GLOBAL"
        ))

        # 1. Try direct path: ext/<chrome_ext_id>/
        direct = adspower_root / "ext" / chrome_ext_id
        if direct.is_dir() and (direct / "manifest.json").exists():
            return self.install_from_unpacked(direct, name=name, chrome_ext_id=chrome_ext_id)

        # 2. Try ext_env/record mapping
        record_path = adspower_root / "ext_env" / "record"
        if record_path.exists():
            try:
                record = json.loads(record_path.read_text(encoding="utf-8"))
                for serial, info in record.items():
                    if info.get("unique_id", "") == chrome_ext_id:
                        env_dir = adspower_root / "ext_env" / serial
                        if env_dir.is_dir() and (env_dir / "manifest.json").exists():
                            ext_name = name or info.get("name", chrome_ext_id)
                            return self.install_from_unpacked(
                                env_dir, name=ext_name, chrome_ext_id=chrome_ext_id,
                            )
            except (json.JSONDecodeError, OSError):
                pass

        log.warning(
            "AdsPower extension %s not found in %s",
            chrome_ext_id, adspower_root,
        )
        return None

    def install_extensions_from_secure_prefs(
        self,
        default_dir: Path,
        adspower_root: Optional[Path] = None,
    ) -> List[Dict[str, Any]]:
        """Install all user extensions found in a profile's Secure Preferences.

        Reads the ``extensions.settings`` section of ``Secure Preferences``
        (or ``Preferences``), filters to user-installed extensions
        (location 8 = user, location 4 = external_registry), and installs
        each one from the AdsPower global store.

        System/component extensions (location 5: PDF viewer, Web Store,
        network speech, etc.) are skipped — they ship with Chromium.

        Returns a list of dicts::

            {
                "ext_id": "<chrome_ext_id>",
                "name": "MetaMask",
                "version": "12.10.2",
                "enabled": True,
                "installed": True,
                "antique_ext_id": "<internal_id>",
                "path": "<installed_path>",
            }
        """
        from .cookie import parse_extension_info_from_secure_prefs

        default_dir = Path(default_dir)
        exts = parse_extension_info_from_secure_prefs(default_dir)
        results: List[Dict[str, Any]] = []

        for ext_info in exts:
            # Skip system/component extensions (location 5)
            if ext_info["location"] in (5,):
                results.append({
                    "ext_id": ext_info["ext_id"],
                    "name": ext_info["name"],
                    "version": ext_info["version"],
                    "enabled": ext_info["enabled"],
                    "installed": False,
                    "reason": "system_extension",
                })
                continue

            # Skip if location indicates an internal AdsPower extension
            # with no manifest data at all (loc=0 and no path)
            if not ext_info["path"] and not ext_info.get("manifest"):
                # These extensions only have data in Local Extension Settings
                # but no code in Secure Preferences. Try AdsPower env by ID.
                pass  # fall through to install_from_adspower_env

            # Install from AdsPower env
            installed = self.install_from_adspower_env(
                ext_info["ext_id"],
                name=ext_info["name"],
                adspower_root=adspower_root,
            )

            if installed is not None:
                # Apply enabled/disabled state
                if not ext_info["enabled"]:
                    installed.enabled = False
                    self._extensions[installed.ext_id] = installed
                    self._save_index()

                results.append({
                    "ext_id": ext_info["ext_id"],
                    "name": ext_info["name"],
                    "version": ext_info["version"],
                    "enabled": ext_info["enabled"],
                    "installed": True,
                    "antique_ext_id": installed.ext_id,
                    "path": installed.path,
                })
            else:
                # Fallback: try installing directly from the path in prefs
                prefs_path = Path(ext_info["path"])
                if prefs_path.is_dir() and (prefs_path / "manifest.json").exists():
                    installed = self.install_from_unpacked(
                        prefs_path, name=ext_info["name"],
                        chrome_ext_id=ext_info["ext_id"],
                    )
                    if not ext_info["enabled"]:
                        installed.enabled = False
                        self._extensions[installed.ext_id] = installed
                        self._save_index()
                    results.append({
                        "ext_id": ext_info["ext_id"],
                        "name": ext_info["name"],
                        "version": ext_info["version"],
                        "enabled": ext_info["enabled"],
                        "installed": True,
                        "antique_ext_id": installed.ext_id,
                        "path": installed.path,
                    })
                else:
                    results.append({
                        "ext_id": ext_info["ext_id"],
                        "name": ext_info["name"],
                        "version": ext_info["version"],
                        "enabled": ext_info["enabled"],
                        "installed": False,
                        "reason": "not_found_on_disk",
                    })

        return results

    def get_extensions_for_profile(self, extension_ids: List[str]) -> List[str]:
        """Return list of paths for given extension IDs (for --load-extension).

        ``extension_ids`` can contain either antique internal IDs or Chrome
        extension IDs (32-char strings from AdsPower).  When a Chrome ID is
        passed, we look it up in the ``chrome_ext_id`` field of the stored
        Extension metadata.
        """
        paths = []
        for eid in extension_ids:
            # Direct lookup by antique internal ID
            ext = self._extensions.get(eid)
            # Try Chrome ext ID lookup
            if ext is None:
                for stored in self._extensions.values():
                    if stored.manifest.get("_chrome_ext_id") == eid:
                        ext = stored
                        break
            if ext and ext.enabled and Path(ext.path).exists():
                paths.append(ext.path)
        return paths

