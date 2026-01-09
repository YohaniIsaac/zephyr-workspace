#!/usr/bin/env python3

"""
Checkpatch compliance check.
Runs checkpatch.pl from Zephyr and reports found issues.
"""

import re
import subprocess

from . import utils
from .base import ComplianceTest


class CheckPatch(ComplianceTest):
    """
    Runs checkpatch and reports found issues.
    """

    name = "Checkpatch"
    doc = "See https://docs.zephyrproject.org/latest/contribute/guidelines.html#coding-style for more details."
    path_hint = "<git-top>"

    def run(self, mode="default"):
        """
        Run the checkpatch check.

        Args:
            mode: Analysis mode - "path" (explicit paths), "diff" (git diff), or "default"
        """
        checkpatch = utils.ZEPHYR_BASE / 'scripts' / 'checkpatch.pl'
        if not checkpatch.exists():
            self.skip(f'{checkpatch} not found')
            return

        cmd_base = [str(checkpatch)]

        if mode in ("path", "default"):
            # PATH/DEFAULT MODE: Analyze files directly
            exts = ('.c', '.h', '.cpp', '.hpp', '.cc', '.S', '.s', '.inc')
            files = []

            for f in utils.files_from_paths():
                if f.endswith(exts):
                    files.append(f)

            if not files:
                return

            cmd = cmd_base + ['--no-tree', '--terse', '--file'] + files
            try:
                subprocess.run(
                    cmd,
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

        # DIFF MODE: Use git diff
        cmd = cmd_base + ['--mailback', '--no-tree', '-']
        with subprocess.Popen(
            ('git', 'diff', '--no-ext-diff', utils.COMMIT_RANGE), stdout=subprocess.PIPE, cwd=utils.GIT_TOP
        ) as diff:
            try:
                subprocess.run(
                    cmd,
                    check=True,
                    stdin=diff.stdout,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    shell=False,
                    cwd=utils.GIT_TOP,
                )
            except subprocess.CalledProcessError as ex:
                output = ex.output.decode("utf-8", errors="replace")
                regex = (
                    r'^\s*\S+:(\d+):\s*(ERROR|WARNING):(.+?):(.+)(?:\n|\r\n?)+'
                    r'^\s*#(\d+):\s*FILE:\s*(.+):(\d+):'
                )

                matches = re.findall(regex, output, re.MULTILINE)

                # Add a guard here for excessive number of errors, do not try and
                # process each one of them and instead push this as one failure.
                if len(matches) > 500:
                    self.failure(output)
                    return

                for m in matches:
                    self.fmtd_failure(m[1].lower(), m[2], m[5], m[6], col=None, desc=m[3])

                # If the regex has not matched add the whole output as a failure
                if len(matches) == 0:
                    self.failure(output)
