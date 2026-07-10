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
import shutil
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


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
        zf.extractall(dest_dir)


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

    def install_from_unpacked(self, source_dir: Path, name: Optional[str] = None) -> Extension:
        """Install an extension from an unpacked directory."""
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

    def get_extensions_for_profile(self, extension_ids: List[str]) -> List[str]:
        """Return list of paths for given extension IDs (for --load-extension)."""
        paths = []
        for eid in extension_ids:
            ext = self._extensions.get(eid)
            if ext and ext.enabled and Path(ext.path).exists():
                paths.append(ext.path)
        return paths
