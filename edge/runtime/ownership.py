"""Process-lifetime database ownership for supported POSIX prototype hosts."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def database_owner(path: Path | None) -> Iterator[None]:
    if path is None:
        yield
        return
    if os.name != "posix":
        raise RuntimeError("UNSUPPORTED_DATABASE_LOCK_PLATFORM")
    import fcntl

    resolved = path.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = resolved.with_name(resolved.name + ".owner.lock")
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("EDGE_DATABASE_ALREADY_OWNED") from None
        yield
    finally:
        # Do not unlink: another process may already have opened this inode.
        # Kernel ownership is released on close, including abrupt process death.
        os.close(descriptor)
