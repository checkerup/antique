"""AdsPower cookie decryption and fingerprint extraction.

Decrypts cookies from the live AdsPower cache using:
1. DPAPI (Windows Data Protection API) to unwrap the AES key from Local State
2. AES-GCM (v10 prefix) to decrypt individual cookie values
3. XOR prefix detection to strip AdsPower's per-domain obfuscation prefix

Also extracts fingerprint data (User-Agent, languages, screen resolution)
from Chromium Preferences and HTTP cache artifacts.
"""
from __future__ import annotations

import base64
import json
import re
import sqlite3
import tempfile
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ── Windows-only imports ──────────────────────────────────────────────
try:
    import win32crypt  # type: ignore
    _HAS_WIN32 = True
except ImportError:
    _HAS_WIN32 = False

try:
    from Crypto.Cipher import AES  # type: ignore
    _HAS_PYCRYPTO = True
except ImportError:
    _HAS_PYCRYPTO = False


# ── Constants ──────────────────────────────────────────────────────────

#: Default AdsPower cache directory on Windows.
DEFAULT_CACHE_DIR = Path(r"C:/.ADSPOWER_GLOBAL/cache")

#: Chromium epoch offset: microseconds between 1601-01-01 and 1970-01-01.
_CHROMIUM_EPOCH_OFFSET = 11_644_473_600_000_000


# ── Public API ────────────────────────────────────────────────────────

def is_crypto_available() -> bool:
    """Return True if both win32crypt and PyCryptodome are importable."""
    return _HAS_WIN32 and _HAS_PYCRYPTO


def find_adspower_cache() -> Optional[Path]:
    """Auto-detect the AdsPower cache directory."""
    if DEFAULT_CACHE_DIR.is_dir():
        return DEFAULT_CACHE_DIR
    return None


def decrypt_profile_cookies(
    profile_cache_dir: Path,
) -> List[Dict[str, Any]]:
    """Decrypt all cookies for one AdsPower profile cache directory.

    Args:
        profile_cache_dir: e.g. ``C:/.ADSPOWER_GLOBAL/cache/j7ia02j_hgk0lp``

    Returns:
        List of cookie dicts with keys: name, value, domain, path,
        secure, httpOnly, sameSite, expires.
    """
    if not is_crypto_available():
        return []

    uid = profile_cache_dir.name.rsplit("_", 1)[0]

    # 1. Get AES key from Local State via DPAPI
    key = _get_aes_key(profile_cache_dir)
    if key is None:
        return []

    # 2. Open Cookies DB
    cookies_db = profile_cache_dir / "Default" / "Network" / "Cookies"
    if not cookies_db.exists():
        return []

    # Copy to temp to avoid DB lock
    tmp = Path(tempfile.gettempdir()) / f"antique_decrypt_{uid}.db"
    shutil.copy2(cookies_db, tmp)

    try:
        c = sqlite3.connect(str(tmp))
        c.text_factory = bytes  # Return raw bytes for all text columns

        rows = c.execute(
            """SELECT name, host_key, path, is_secure, is_httponly,
                      has_expires, expires_utc, samesite,
                      encrypted_value, value as plaintext_value
               FROM cookies"""
        ).fetchall()

        # Group decrypted values by domain for XOR prefix detection
        domain_decrypted: Dict[str, List[bytes]] = defaultdict(list)
        domain_rows: Dict[str, List[tuple]] = defaultdict(list)

        for row_raw in rows:
            host_key = _decode_text(row_raw[1])
            enc = row_raw[8] if isinstance(row_raw[8], bytes) else b""
            plain = _decode_text(row_raw[9])

            if enc and len(enc) > 3:
                try:
                    dec_bytes = _decrypt_v10(enc, key)
                except Exception:
                    dec_bytes = plain.encode("utf-8", errors="replace")
            else:
                dec_bytes = plain.encode("utf-8", errors="replace")

            domain_decrypted[host_key].append(dec_bytes)
            domain_rows[host_key].append(row_raw)

        # Process each domain: find prefix boundary, extract real values
        cookies: List[Dict[str, Any]] = []

        for host_key, dec_values in domain_decrypted.items():
            boundary = _find_prefix_boundary(dec_values)
            row_list = domain_rows[host_key]

            for idx, row_raw in enumerate(row_list):
                dec_bytes = dec_values[idx]
                real_bytes = dec_bytes[boundary:]

                # Verify pure ASCII
                try:
                    real_value = real_bytes.decode("ascii")
                except UnicodeDecodeError:
                    # Fallback: strip non-printable from start
                    m = re.search(rb"[\x20-\x7e]{5,}", dec_bytes)
                    if m:
                        real_value = dec_bytes[m.start():].decode(
                            "ascii", errors="replace"
                        )
                    else:
                        real_value = dec_bytes.decode("ascii", errors="replace")

                cookies.append({
                    "name": _decode_text(row_raw[0]),
                    "value": real_value,
                    "domain": host_key,
                    "path": _decode_text(row_raw[2]) or "/",
                    "secure": bool(row_raw[3]),
                    "httpOnly": bool(row_raw[4]),
                    "sameSite": _map_samesite(row_raw[7]),
                    "expires": _convert_expiry(row_raw[5], row_raw[6]),
                })

        c.close()
        return cookies
    finally:
        try:
            tmp.unlink()
        except Exception:
            pass


def extract_fingerprint(profile_cache_dir: Path) -> Dict[str, Any]:
    """Extract fingerprint-relevant data from an AdsPower profile cache dir.

    Reads User-Agent from HTTP cache files, languages/screen from
    Chromium Preferences, and lists installed extensions.

    Returns a dict of fingerprint override fields.
    """
    prefs_path = profile_cache_dir / "Default" / "Preferences"
    prefs: Dict[str, Any] = {}
    if prefs_path.exists():
        try:
            prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # User-Agent from HTTP cache
    ua = _extract_ua_from_cache(profile_cache_dir)

    # Screen resolution from window_placement
    wp = prefs.get("browser", {}).get("window_placement", {})
    screen_w = wp.get("work_area_right", 0) - wp.get("work_area_left", 0)
    screen_h = wp.get("work_area_bottom", 0) - wp.get("work_area_top", 0)

    # Languages
    accept_lang = prefs.get("intl", {}).get("accept_languages", "en-US,en")
    selected_lang = prefs.get("intl", {}).get("selected_languages", "en-US,en")

    # Extensions
    extensions: List[Dict[str, Any]] = []
    ext_dir = profile_cache_dir / "Default" / "Extensions"
    if ext_dir.exists():
        for ext_id_dir in ext_dir.iterdir():
            if not ext_id_dir.is_dir():
                continue
            versions = [v for v in ext_id_dir.iterdir() if v.is_dir()]
            if not versions:
                continue
            latest = sorted(versions)[-1]
            ext_name = ext_id_dir.name
            manifest_path = latest / "manifest.json"
            if manifest_path.exists():
                try:
                    m = json.loads(manifest_path.read_text(encoding="utf-8"))
                    ext_name = m.get("name", ext_id_dir.name)
                    if ext_name.startswith("__MSG_"):
                        ext_name = _resolve_ext_name(latest, ext_name)
                except Exception:
                    pass
            extensions.append({
                "id": ext_id_dir.name,
                "name": ext_name,
                "version": latest.name.replace("_0", ""),
                "path": str(latest),
            })

    return {
        "user_agent": ua,
        "accept_language": accept_lang,
        "languages": [l.strip() for l in accept_lang.split(",")],
        "locale": selected_lang.split(",")[0] if selected_lang else "en-US",
        "screen_width": screen_w or 1536,
        "screen_height": screen_h or 816,
        "avail_screen_width": screen_w or 1536,
        "avail_screen_height": (screen_h - 40) if screen_h else 776,
        "extensions": extensions,
    }


def copy_profile_state(
    profile_cache_dir: Path,
    target_dir: Path,
) -> Dict[str, int]:
    """Copy LocalStorage, IndexedDB, History, and Extensions to target.

    Returns a dict of copied file/dir counts.
    """
    src_default = profile_cache_dir / "Default"
    dst_default = target_dir / "Default"
    counts: Dict[str, int] = {}

    items = [
        ("Local Storage", "Local Storage"),
        ("IndexedDB", "IndexedDB"),
        ("Extensions", "Extensions"),
        ("Local Extension Settings", "Local Extension Settings"),
    ]

    for src_name, dst_name in items:
        src = src_default / src_name
        dst = dst_default / dst_name
        if src.exists() and not dst.exists():
            try:
                dst_default.mkdir(parents=True, exist_ok=True)
                shutil.copytree(src, dst)
                counts[src_name] = sum(1 for _ in dst.rglob("*"))
            except Exception:
                counts[src_name] = 0
        elif src.exists():
            counts[src_name] = -1  # Already exists

    # History is a single file
    hist_src = src_default / "History"
    hist_dst = dst_default / "History"
    if hist_src.exists() and not hist_dst.exists():
        try:
            dst_default.mkdir(parents=True, exist_ok=True)
            shutil.copy2(hist_src, hist_dst)
            counts["History"] = 1
        except Exception:
            counts["History"] = 0
    elif hist_src.exists():
        counts["History"] = -1

    return counts


# ── Internal helpers ───────────────────────────────────────────────────

def _get_aes_key(profile_cache_dir: Path) -> Optional[bytes]:
    """Get the AES-GCM key from Local State via DPAPI."""
    ls_path = profile_cache_dir / "Local State"
    if not ls_path.exists():
        return None
    try:
        ls = json.loads(ls_path.read_text(encoding="utf-8"))
        enc_key_b64 = ls.get("os_crypt", {}).get("encrypted_key", "")
        if not enc_key_b64:
            return None
        enc_key = base64.b64decode(enc_key_b64)
        if enc_key.startswith(b"DPAPI"):
            enc_key = enc_key[5:]
        return win32crypt.CryptUnprotectData(enc_key, None, None, None, 0)[1]
    except Exception:
        return None


def _decrypt_v10(enc_value: bytes, key: bytes) -> bytes:
    """Decrypt a v10-prefixed AES-GCM cookie value."""
    if enc_value[:3] == b"v10":
        iv = enc_value[3:15]
        ciphertext = enc_value[15:-16]
        tag = enc_value[-16:]
        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
        return cipher.decrypt_and_verify(ciphertext, tag)
    elif enc_value[:3] == b"v11":
        # v11 = DPAPI directly (older Chrome)
        return win32crypt.CryptUnprotectData(enc_value[3:], None, None, None, 0)[1]
    return enc_value


def _find_prefix_boundary(decrypted_values: List[bytes]) -> int:
    """Find prefix boundary by XOR-ing pairs of cookies from the same domain.

    The prefix is identical for all cookies of the same domain, so XOR
    of two DIFFERENT cookies will be 0x00 for the prefix part and non-zero
    for the real value part.

    Uses the MODE (most common boundary) to filter out outliers from
    identical cookie pairs (e.g. SID and __Secure-1PSID have the same value).
    """
    if len(decrypted_values) < 2:
        d = decrypted_values[0]
        m = re.search(rb"[\x20-\x7e]{5,}", d)
        return m.start() if m else 0

    boundaries: List[int] = []
    for i in range(len(decrypted_values)):
        for j in range(i + 1, len(decrypted_values)):
            d1, d2 = decrypted_values[i], decrypted_values[j]
            min_len = min(len(d1), len(d2))
            boundary = min_len
            for k in range(min_len):
                if d1[k] ^ d2[k] != 0:
                    boundary = k
                    break
            # Skip pairs where boundary = min_len (identical cookies)
            if boundary < min_len:
                boundaries.append(boundary)

    if not boundaries:
        d = decrypted_values[0]
        m = re.search(rb"[\x20-\x7e]{5,}", d)
        return m.start() if m else 0

    counts = Counter(boundaries)
    return counts.most_common(1)[0][0]


def _extract_ua_from_cache(profile_cache_dir: Path) -> Optional[str]:
    """Extract User-Agent from HTTP cache files."""
    cache_dir = profile_cache_dir / "Default" / "Cache" / "Cache_Data"
    if not cache_dir.exists():
        return None
    ua_pattern = re.compile(
        rb"(Mozilla/5\.0[^:\r\n<>\"']+(?:Chrome|Safari)[^\r\n<>\"']*)"
    )
    for f in cache_dir.iterdir():
        if not f.is_file():
            continue
        try:
            data = f.read_bytes()
            for m in ua_pattern.finditer(data):
                ua = m.group(0).decode("ascii", errors="replace")
                if "Chrome" in ua:
                    return ua[:200]
        except Exception:
            continue
    return None


def _resolve_ext_name(ext_dir: Path, msg_name: str) -> str:
    """Resolve a __MSG_...__ extension name from _locales."""
    key = msg_name.replace("__MSG_", "").replace("__", "")
    locale_dir = ext_dir / "_locales" / "en"
    if locale_dir.exists():
        msg_file = locale_dir / "messages.json"
        if msg_file.exists():
            try:
                msgs = json.loads(msg_file.read_text(encoding="utf-8"))
                if key in msgs:
                    return msgs[key].get("message", msg_name)
            except Exception:
                pass
    return msg_name


def _decode_text(val: Any) -> str:
    """Decode a bytes/text value from SQLite text_factory=bytes."""
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return str(val or "")


def _map_samesite(val: Any) -> str:
    """Map Chromium sameSite int to CDP string."""
    if val is None:
        return "Lax"
    if val == 0:
        return "None"
    if val == 1:
        return "Lax"
    if val == 2:
        return "Strict"
    return "Lax"


def _convert_expiry(has_expires: Any, expires_utc: Any) -> float:
    """Convert Chromium UTC to Unix epoch."""
    if not has_expires or not expires_utc or expires_utc <= 0:
        return -1
    unix_expires = (expires_utc - _CHROMIUM_EPOCH_OFFSET) / 1_000_000
    return unix_expires if unix_expires > 0 else -1
