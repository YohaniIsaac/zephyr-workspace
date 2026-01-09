#!/usr/bin/env python3

"""
CMakeStyle compliance check.
Checks CMake files for style violations.
"""

import re

from . import utils
from .base import ComplianceTest


class CMakeStyle(ComplianceTest):
    """
    Checks CMake style in added/modified files.
    """

    name = "CMakeStyle"
    doc = "See https://docs.zephyrproject.org/latest/contribute/style/cmake.html for more details."
    path_hint = "<git-top>"

    def run(self, mode="default"):
        """
        Run the CMakeStyle check.

        Args:
            mode: Analysis mode - "path" (explicit paths), "diff" (git diff), or "default"
        """
        # Determine which files to check based on mode
        if mode in ("path", "default"):
            # PATH/DEFAULT MODE: Scan filesystem
            files = utils.files_from_paths()
        else:
            # DIFF MODE: Use git diff
            files = utils.get_files(filter="d")

        # Loop through files and check only CMake files
        for fname in files:
            if fname.endswith(".cmake") or fname.endswith("CMakeLists.txt"):
                self.check_style(fname)

    def check_style(self, fname):
        """Check style rules for a CMake file."""
        SPACE_BEFORE_OPEN_BRACKETS_CHECK = re.compile(r"^\s*if\s+\(")
        TAB_INDENTATION_CHECK = re.compile(r"^\t+")

        full_path = utils.GIT_TOP / fname

        with open(full_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f.readlines(), start=1):
                if TAB_INDENTATION_CHECK.match(line):
                    self.fmtd_failure(
                        "error",
                        "CMakeStyle",
                        fname,
                        line_num,
                        desc="Use spaces instead of tabs for indentation",
                    )

                if SPACE_BEFORE_OPEN_BRACKETS_CHECK.match(line):
                    self.fmtd_failure(
                        "error",
                        "CMakeStyle",
                        fname,
                        line_num,
                        desc="Remove space before '(' in if() statements",
                    )
