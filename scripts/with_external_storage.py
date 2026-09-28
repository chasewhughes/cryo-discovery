#!/usr/bin/env python3
"""Run research commands with local cryo-adata storage (legacy command name)."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def storage_environment():
    storage = ROOT / 'cryo-adata'
    if not storage.resolve(strict=True).is_relative_to(ROOT):
        raise RuntimeError('Research storage must be inside the local repository')
    paths = {}
    for name in ('raw', 'downloads', 'tmp'):
        link = ROOT / 'data' / name
        target = storage / name
        if not link.is_symlink() or link.resolve(strict=True) != target.resolve(strict=True):
            raise RuntimeError(f'Local storage link is missing or changed: {name}')
        if not target.resolve().is_relative_to(ROOT):
            raise RuntimeError('Storage target is outside the local repository')
        if not target.is_dir() or not os.access(target, os.W_OK):
            raise RuntimeError(f'Local storage directory is not writable: {name}')
        paths[name] = str(target)
    env = os.environ.copy()
    env.update(CRYO_RAW_DIR=paths['raw'], CRYO_DOWNLOAD_DIR=paths['downloads'],
               TMPDIR=paths['tmp'], TEMP=paths['tmp'], TMP=paths['tmp'])
    return env


def main():
    try:
        env = storage_environment()
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print(f'Cryo storage unavailable ({type(exc).__name__}). Check local cryo-adata directories and data links.', file=sys.stderr)
        return 1
    args = sys.argv[1:]
    if args[:1] == ['--']:
        args = args[1:]
    if not args:
        print(json.dumps({key: env[key] for key in ('CRYO_RAW_DIR', 'CRYO_DOWNLOAD_DIR', 'TMPDIR')}, indent=2))
        return 0
    os.execvpe(args[0], args, env)


if __name__ == '__main__':
    sys.exit(main())
