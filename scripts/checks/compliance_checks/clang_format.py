#!/usr/bin/env python3

"""
ClangFormat compliance check.
Checks if clang-format reports any formatting issues.
"""

import shutil
import subprocess
from pathlib import Path

import unidiff

from . import utils
from .base import ComplianceTest


class ClangFormat(ComplianceTest):
    """
    Check if clang-format reports any issues.
    """

    name = "ClangFormat"
    doc = "See https://clang.llvm.org/docs/ClangFormat.html for more details."
    path_hint = "<git-top>"

    def _process_patch_error(self, file: str, patch: unidiff.PatchedFile):
        """Process unidiff patch and report formatting issues."""
        for hunk in patch:
            before = next(i for i, v in enumerate(hunk) if str(v).startswith(("-", "+")))
            after = next(i for i, v in enumerate(reversed(hunk)) if str(v).startswith(("-", "+")))
            msg = "".join([str(line) for line in hunk[before : -after or None]])

            self.fmtd_failure(
                "notice",
                "You may want to run clang-format on this change",
                file,
                line=hunk.source_start + hunk.source_length - after,
                desc=f"\r\n{msg}",
            )

    def run(self, mode="default"):
        """
        Run the clang-format check.

        Args:
            mode: Analysis mode - "path" (explicit paths), "diff" (git diff), or "default"
        """
        exts = {".c", ".h"}

        if mode in ("path", "default"):
            # PATH/DEFAULT MODE: Analyze files directly using clang-format --dry-run
            clang_format = shutil.which("clang-format")
            if not clang_format:
                self.skip("clang-format not found in PATH")
                return

            for f in utils.files_from_paths():
                if Path(f).suffix not in exts:
                    continue
                try:
                    subprocess.run(
                        [clang_format, "--dry-run", "--Werror", "--style=file", f],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        shell=False,
                        cwd=utils.GIT_TOP,
                    )
                except subprocess.CalledProcessError as ex:
                    output = ex.output.decode("utf-8", errors="replace")
                    self.failure(output)
            return
        # DIFF MODE: Use clang-format-diff.py
        exe = shutil.which("clang-format-diff.py")
        if not exe:
            self.skip("clang-format-diff.py not found in PATH")
            return

        if not utils.COMMIT_RANGE:
            self.skip("No commit range specified for diff mode")
            return

        for file in utils.get_files(filter="d"):
            if Path(file).suffix not in exts:
                continue

            diff = subprocess.Popen(
                ("git", "diff", "-U0", "--no-color", "--no-ext-diff", utils.COMMIT_RANGE, "--", file),
                stdout=subprocess.PIPE,
                cwd=utils.GIT_TOP,
            )
            try:
                subprocess.run(
                    (exe, "-p1"),
                    check=True,
                    stdin=diff.stdout,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    shell=False,
                    cwd=utils.GIT_TOP,
                )

            except subprocess.CalledProcessError as ex:
                patchset = unidiff.PatchSet.from_string(ex.output, encoding="utf-8")
                for patch in patchset:
                    self._process_patch_error(file, patch)
