#!/usr/bin/env python3

"""
Utility functions for compliance checks.
"""

import shlex
import subprocess
import sys
from pathlib import Path

# Global variables (set by _main())
WORKSPACE_BASE = None
ZEPHYR_BASE = None
GIT_TOP = None
COMMIT_RANGE = None
TARGET_PATHS = []

# Directories to ignore when scanning filesystem
IGNORE_PATH_PARTS = {
    '.git',
    'build',
    'deps',
    'build_sca',
    'buildsca',
    '.cache',
    'sca_logs',
    'venv',
    '.venv',
    '.ruff_cache',
}


def init_globals(git_top, commit_range, target_paths, workspace_base, zephyr_base):
    """
    initialize global variables used by utility functions.

    this must be called by the orchestrator before any checks run.
    """
    global GIT_TOP, COMMIT_RANGE, TARGET_PATHS, WORKSPACE_BASE, ZEPHYR_BASE
    GIT_TOP = git_top
    COMMIT_RANGE = commit_range
    TARGET_PATHS = target_paths
    WORKSPACE_BASE = workspace_base
    ZEPHYR_BASE = zephyr_base


def resolve_path_hint(hint):
    """Resolve magic path hint strings."""
    hints = {
        "<workspace-base>": WORKSPACE_BASE,
        "<zephyr-base>": ZEPHYR_BASE,
        "<git-top>": GIT_TOP,
    }
    return hints.get(hint, hint)


def cmd2str(cmd):
    # Formats the command-line arguments in the iterable 'cmd' into a string,
    # for error messages and the like

    return " ".join(shlex.quote(word) for word in cmd)


def err(msg):
    cmd = sys.argv[0]  # Empty if missing
    if cmd:
        cmd += ": "
    sys.exit(f"{cmd} error: {msg}")


def git(*args, cwd=None, ignore_non_zero=False):
    """Helper for running a Git command. Returns the rstrip()ed stdout output."""
    git_cmd = ("git",) + args
    try:
        cp = subprocess.run(git_cmd, capture_output=True, cwd=cwd)
    except OSError as e:
        err(f"failed to run '{cmd2str(git_cmd)}': {e}")

    if not ignore_non_zero and (cp.returncode or cp.stderr):
        err(
            f"'{cmd2str(git_cmd)}' exited with status {cp.returncode} and/or "
            f"wrote to stderr.\n"
            f"==stdout==\n"
            f"{cp.stdout.decode('utf-8')}\n"
            f"==stderr==\n"
            f"{cp.stderr.decode('utf-8')}\n"
        )

    return cp.stdout.decode("utf-8").rstrip()


def files_from_paths():
    """
    Expand TARGET_PATHS into a list of files (relative to GIT_TOP).

    Scans directories recursively and collects all files, excluding
    paths that contain parts in IGNORE_PATH_PARTS.

    Returns:
        Sorted list of file paths relative to GIT_TOP
    """
    root = Path(GIT_TOP).resolve()
    out = set()

    for p in TARGET_PATHS:
        pp = Path(p)
        abs_p = (root / pp).resolve() if not pp.is_absolute() else pp.resolve()

        if abs_p.is_dir():
            # Recursively scan directory
            for f in abs_p.rglob('*'):
                if not f.is_file():
                    continue
                # Skip files in ignored directories
                if any(part in IGNORE_PATH_PARTS for part in f.parts):
                    continue
                try:
                    out.add(str(f.relative_to(root)))
                except ValueError:
                    out.add(str(f))
        elif abs_p.is_file():
            # Single file
            if any(part in IGNORE_PATH_PARTS for part in abs_p.parts):
                continue
            try:
                out.add(str(abs_p.relative_to(root)))
            except ValueError:
                out.add(str(abs_p))

    return sorted(out)


def get_files(filter=None, paths=None):
    """Get modified files from git diff."""
    filter_arg = (f"--diff-filter={filter}",) if filter else ()
    paths_arg = ("--", *paths) if paths else ()
    out = git("diff", "--name-only", *filter_arg, COMMIT_RANGE, *paths_arg)
    files = out.splitlines()
    for file in list(files):
        if not (GIT_TOP / file).exists():
            # Drop submodule directories from the list.
            files.remove(file)
    return files


def filter_python_files(files):
    """
    Filter Python files from a list of filenames.

    Uses python-magic to detect Python scripts even without .py extension
    (e.g., scripts with #!/usr/bin/env python3).

    Args:
        files: List of file paths relative to GIT_TOP

    Returns:
        List of Python file paths
    """
    try:
        import magic
    except ImportError:
        # Fallback: only check .py extension if magic is not available
        return [f for f in files if f.endswith('.py')]

    py_files = []
    for fname in files:
        full_path = GIT_TOP / fname
        if not full_path.exists():
            continue

        # Check extension or mime type
        if fname.endswith('.py'):
            py_files.append(fname)
        else:
            try:
                mime = magic.from_file(str(full_path), mime=True)
                if mime == "text/x-python":
                    py_files.append(fname)
            except Exception:
                # If magic fails, skip this file
                continue

    return py_files


def find_zephyr_app_root(rel_path):
    p = (GIT_TOP / rel_path).resolve()
    d = p if p.is_dir() else p.parent

    while True:
        if (d / "prj.conf").is_file():
            return d
        if d == GIT_TOP:
            return None
        d = d.parent
