"""Operational features for a serious local profile manager.

This module keeps the higher-level workflows small and testable: audit history,
profile templates, import previews, and encrypted snapshots.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .fingerprint import Fingerprint, generate_fingerprint
from .profile import ProfileStore


@dataclass
class ActivityEvent:
    user_id: str
    action: str
    detail: Dict[str, Any]
    created_at: str


def record_activity(store: ProfileStore, user_id: str, action: str, detail: Optional[Dict[str, Any]] = None) -> ActivityEvent:
    event = ActivityEvent(user_id, action, detail or {}, datetime.utcnow().isoformat())
    with store.engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO activity_events(user_id, action, detail, created_at) VALUES (?, ?, ?, ?)",
            (event.user_id, event.action, json.dumps(event.detail, ensure_ascii=False), event.created_at),
        )
    return event


def list_activity(store: ProfileStore, user_id: Optional[str] = None, limit: int = 100, action: Optional[str] = None) -> List[ActivityEvent]:
    sql = "SELECT user_id, action, detail, created_at FROM activity_events"
    clauses: List[str] = []
    args: List[Any] = []
    if user_id:
        clauses.append("user_id = ?"); args.append(user_id)
    if action:
        clauses.append("action = ?"); args.append(action)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC LIMIT ?"
    args.append(max(1, min(limit, 1000)))
    with store.engine.connect() as conn:
        rows = conn.exec_driver_sql(sql, tuple(args)).fetchall()
    return [ActivityEvent(r[0], r[1], json.loads(r[2] or "{}"), r[3]) for r in rows]


def export_activity(store: ProfileStore, destination: Path, user_id: Optional[str] = None, action: Optional[str] = None) -> Path:
    rows = [asdict(event) for event in list_activity(store, user_id=user_id, action=action, limit=1000)]
    destination = Path(destination)
    destination.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination


def preview_backup(root: Path) -> Dict[str, Any]:
    from .backup_import import load_adspower_profiles_index, prepare_backup_profile_payload
    metas = load_adspower_profiles_index(root)
    rows, errors = [], []
    for meta in metas:
        try:
            p = prepare_backup_profile_payload(root, meta)
            rows.append({
                "user_id": p["user_id"], "name": p["name"], "group_id": p["group_id"],
                "cookie_source": p["cookie_source"], "cookie_count": len(p["cookies"]),
                "has_full_state": p["has_full_state"], "proxy_type": p["proxy"].get("proxy_type"),
                "proxy_host": p["proxy"].get("proxy_host", ""), "ip_country": p["ip_country"],
            })
        except Exception as exc:
            errors.append({"user_id": str(meta.get("user_id", "")), "error": str(exc)})
    return {"source_path": str(root), "total": len(metas), "profiles": rows, "errors": errors}


def create_from_template(store: ProfileStore, template: Dict[str, Any], count: int, *, seed: Optional[str] = None) -> List[Any]:
    if count < 1 or count > 1000:
        raise ValueError("count must be between 1 and 1000")
    out = []
    for i in range(count):
        fp = generate_fingerprint(seed=f"{seed}:{i}" if seed else None, os_family=template.get("os_family", "windows"))
        patch = template.get("fingerprint_config") or {}
        for key, value in patch.items():
            if hasattr(fp, key):
                setattr(fp, key, value)
        name = str(template.get("name", "profile"))
        if count > 1:
            name = f"{name}-{i + 1:03d}"
        out.append(store.create(
            name=name,
            group_id=str(template.get("group_id", "0")),
            proxy=dict(template.get("proxy") or {}),
            fingerprint=fp,
            cookies=list(template.get("cookies") or []),
            tags=list(template.get("tags") or []),
            remark=str(template.get("remark", "")),
            account_status=str(template.get("account_status", "new")),
        ))
    return out


def _key(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 250_000, dklen=32)


def encrypted_snapshot(store: ProfileStore, destination: Path, password: str) -> Path:
    """Write a password-protected snapshot using AES-GCM when cryptography exists."""
    if not password:
        raise ValueError("password is required")
    profiles = [asdict(p) for p in store.list()]
    payload = json.dumps({"version": 1, "profiles": profiles}, default=str, ensure_ascii=False).encode()
    salt = secrets.token_bytes(16)
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = secrets.token_bytes(12)
        cipher = AESGCM(_key(password, salt)).encrypt(nonce, payload, b"antique-backup-v1")
        blob = {"format": "antique-encrypted-v1", "salt": base64.b64encode(salt).decode(), "nonce": base64.b64encode(nonce).decode(), "ciphertext": base64.b64encode(cipher).decode()}
    except ImportError as exc:
        raise RuntimeError("cryptography is required for encrypted backups") from exc
    destination = Path(destination)
    destination.write_text(json.dumps(blob), encoding="utf-8")
    return destination


def decrypt_snapshot(store: ProfileStore, source: Path, password: str, *, overwrite: bool = False) -> Dict[str, Any]:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    blob = json.loads(Path(source).read_text(encoding="utf-8"))
    if blob.get("format") != "antique-encrypted-v1":
        raise ValueError("unsupported backup format")
    try:
        payload = AESGCM(_key(password, base64.b64decode(blob["salt"]))).decrypt(base64.b64decode(blob["nonce"]), base64.b64decode(blob["ciphertext"]), b"antique-backup-v1")
        data = json.loads(payload)
    except Exception as exc:
        raise ValueError("invalid password or corrupted backup") from exc
    imported, skipped = [], []
    for raw in data.get("profiles", []):
        uid = raw["user_id"]
        existing = store.get(uid)
        if existing and not overwrite:
            skipped.append(uid)
            continue
        fp = Fingerprint(**{k: v for k, v in (raw.get("fingerprint") or {}).items() if k in {f.name for f in __import__('dataclasses').fields(Fingerprint)}})
        if existing:
            store.update(uid, name=raw["name"], group_id=raw.get("group_id"), proxy=raw.get("proxy"), fingerprint=fp, cookies=raw.get("cookies"), tags=raw.get("tags"), remark=raw.get("remark"), account_status=raw.get("account_status"))
        else:
            store.create(name=raw["name"], group_id=raw.get("group_id", "0"), proxy=raw.get("proxy"), fingerprint=fp, cookies=raw.get("cookies"), tags=raw.get("tags"), remark=raw.get("remark", ""), account_status=raw.get("account_status", "new"), user_id=uid)
        imported.append(uid)
    return {"imported_count": len(imported), "skipped_count": len(skipped), "imported_user_ids": imported, "skipped_user_ids": skipped}
