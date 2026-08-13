'Safe archive extraction shared by all untrusted import paths.'
from __future__ import annotations

import stat
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

MAX_ARCHIVE_FILES = 10000
MAX_ARCHIVE_MEMBER_SIZE = 268435456
MAX_ARCHIVE_TOTAL_SIZE = 1073741824

class UnsafeArchiveError(ValueError):
    pass

def _target(root, name):
    name = name.replace(chr(92), '/')
    path = PurePosixPath(name)
    if not name or name.startswith('/') or path.is_absolute() or any(x in ('', '.', '..') for x in path.parts) or ':' in path.parts[0]:
        raise UnsafeArchiveError(f'unsafe archive member path: {name!r}')
    target = (root / Path(*path.parts)).resolve()
    try: target.relative_to(root.resolve())
    except ValueError as exc: raise UnsafeArchiveError(f'archive member escapes destination: {name!r}') from exc
    return target

def _limits(entries, max_files, max_member_size, max_total_size):
    total = 0
    for count, (name, size) in enumerate(entries, 1):
        if count > max_files: raise UnsafeArchiveError('archive has too many entries')
        if size < 0 or size > max_member_size: raise UnsafeArchiveError(f'archive member too large: {name!r}')
        total += size
        if total > max_total_size: raise UnsafeArchiveError('archive uncompressed size limit exceeded')

def safe_extract_zip(zf, destination, *, max_files=MAX_ARCHIVE_FILES, max_member_size=MAX_ARCHIVE_MEMBER_SIZE, max_total_size=MAX_ARCHIVE_TOTAL_SIZE):
    root = Path(destination); infos = zf.infolist()
    _limits(((i.filename, i.file_size) for i in infos), max_files, max_member_size, max_total_size)
    checked = []
    for info in infos:
        target = _target(root, info.filename); mode = (info.external_attr >> 16) & 65535
        if stat.S_ISLNK(mode): raise UnsafeArchiveError(f'special ZIP member: {info.filename!r}')
        # Some ZIP writers (Python's writestr) set mode to just permission bits
        # (e.g. 0o600) without a file type (S_IFREG). Treat mode < 0o100000
        # as a regular file — only block symlinks and truly special types.
        if mode and mode >= 0o100000 and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise UnsafeArchiveError(f'special ZIP member: {info.filename!r}')
        checked.append((info, target))
    root.mkdir(parents=True, exist_ok=True); written = 0
    for info, target in checked:
        if info.is_dir(): target.mkdir(parents=True, exist_ok=True); continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info) as source, target.open('wb') as output:
            while True:
                chunk = source.read(1048576)
                if not chunk: break
                written += len(chunk)
                if written > max_total_size: raise UnsafeArchiveError('archive size limit exceeded while extracting')
                output.write(chunk)

def safe_extract_tar(tf, destination, *, max_files=MAX_ARCHIVE_FILES, max_member_size=MAX_ARCHIVE_MEMBER_SIZE, max_total_size=MAX_ARCHIVE_TOTAL_SIZE):
    root = Path(destination); members = tf.getmembers()
    _limits(((m.name, m.size) for m in members), max_files, max_member_size, max_total_size)
    checked = []
    for member in members:
        target = _target(root, member.name)
        if member.issym() or member.islnk() or member.isdev() or member.isfifo() or not (member.isfile() or member.isdir()): raise UnsafeArchiveError(f'special TAR member: {member.name!r}')
        checked.append((member, target))
    root.mkdir(parents=True, exist_ok=True); written = 0
    for member, target in checked:
        if member.isdir(): target.mkdir(parents=True, exist_ok=True); continue
        source = tf.extractfile(member)
        if source is None: raise UnsafeArchiveError(f'cannot read TAR member: {member.name!r}')
        target.parent.mkdir(parents=True, exist_ok=True)
        with source, target.open('wb') as output:
            while True:
                chunk = source.read(1048576)
                if not chunk: break
                written += len(chunk)
                if written > max_total_size: raise UnsafeArchiveError('archive size limit exceeded while extracting')
                output.write(chunk)
