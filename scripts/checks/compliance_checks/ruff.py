#!/usr/bin/env python3

"""
Ruff compliance check.
Runs ruff check and ruff format on Python files.
"""

import json
import logging
import subprocess

from . import utils
from .base import ComplianceTest

logger = logging.getLogger(__name__)


class Ruff(ComplianceTest):
    """
    Runs ruff check (linter) and ruff format (formatter) on Python files.
    """

    name = "Ruff"
    doc = "See https://docs.astral.sh/ruff/ for more details"
    path_hint = "<git-top>"

    def run(self, mode="default"):
        """
        Run the Ruff check.

        Args:
            mode: Analysis mode - "path" (explicit paths), "diff" (git diff), or "default"
        """
        # Get Python files based on mode
        if mode == "diff":
            # DIFF MODE: Analyze only modified Python files from git diff
            logging.info("Ruff: analyzing modified files from git diff")
            files = utils.get_files(filter="d")
            py_files = utils.filter_python_files(files)
        else:
            # PATH/DEFAULT MODE: Scan directories for Python files
            if mode == "path":
                logging.info(f"Ruff: analyzing {', '.join(utils.TARGET_PATHS)}")
            else:
                logging.info("Ruff: analyzing main_node/ and secondary_node/ (default)")
            all_files = utils.files_from_paths()
            py_files = utils.filter_python_files(all_files)

        if not py_files:
            logging.info("Ruff: No Python files found to analyze")
            return

        # Part 1: Run ruff check (linter)
        self._run_ruff_check(py_files)

        # Part 2: Run ruff format --diff (formatter)
        self._run_ruff_format(py_files)

    def _run_ruff_check(self, py_files):
        """Run ruff check on Python files."""
        # Path to ruff configuration file
        ruff_config = utils.GIT_TOP / ".ruff.toml"

        ruffcmd = [
            "ruff",
            "check",
            "--config",
            str(ruff_config),
            "--output-format=json",
        ] + py_files

        logging.debug(f"Running: {' '.join(ruffcmd)}")

        try:
            subprocess.run(
                ruffcmd,
                check=True,
                capture_output=True,
                cwd=utils.GIT_TOP,
            )
        except subprocess.CalledProcessError as ex:
            output = ex.output.decode("utf-8")

            # Try to parse JSON output
            try:
                messages = json.loads(output)
            except json.JSONDecodeError as e:
                # If JSON parsing fails, output is likely an error message
                logging.error(f"Failed to parse ruff JSON output: {e}")
                logging.error(f"Raw output: {output[:500]}")  # First 500 chars
                self.failure(f"Ruff check execution failed:\n{output}")
                return

            for m in messages:
                self.fmtd_failure(
                    "error",
                    f'Ruff ({m.get("code")})',
                    m.get("filename"),
                    line=m.get("location", {}).get("row"),
                    col=m.get("location", {}).get("column"),
                    end_line=m.get("end_location", {}).get("row"),
                    end_col=m.get("end_location", {}).get("column"),
                    desc=f'{m.get("message")} - see {m.get("url")}',
                )

    def _run_ruff_format(self, py_files):
        """Run ruff format --diff to check formatting."""
        # Path to ruff configuration file
        ruff_config = utils.GIT_TOP / ".ruff.toml"

        for file in py_files:
            ruffcmd = [
                "ruff",
                "format",
                "--config",
                str(ruff_config),
                "--force-exclude",
                "--diff",
                file,
            ]

            logging.debug(f"Running: {' '.join(ruffcmd)}")

            try:
                subprocess.run(
                    ruffcmd,
                    check=True,
                    capture_output=True,
                    cwd=utils.GIT_TOP,
                )
            except subprocess.CalledProcessError:
                self.fmtd_failure(
                    "error",
                    "Ruff format",
                    file,
                    desc=f"File needs formatting. Run: ruff format {file}",
                )
