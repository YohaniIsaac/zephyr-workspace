#!/usr/bin/env python3

"""
Pylint compliance check.
Runs pylint on Python files with a limited set of checks enabled.
"""

import json
import logging
import os
import subprocess

from . import utils
from .base import ComplianceTest

logger = logging.getLogger(__name__)


class PyLint(ComplianceTest):
    """
    Runs pylint on all .py files, with a limited set of checks enabled. The
    configuration is in the pylintrc file.
    """

    name = "Pylint"
    doc = "See https://www.pylint.org/ for more details"
    path_hint = "<git-top>"

    def run(self, mode="default"):
        """
        Run the Pylint check.

        Args:
            mode: Analysis mode - "path" (explicit paths), "diff" (git diff), or "default"
        """
        # Path to pylint configuration file
        pylintrc = os.path.join(utils.GIT_TOP, ".pylintrc")

        # Path to additional pylint check scripts
        check_script_dir = os.path.abspath(os.path.join(utils.ZEPHYR_BASE, "scripts/pylint/checkers"))

        # Get Python files based on mode
        if mode == "diff":
            # DIFF MODE: Analyze only modified Python files from git diff
            logging.info("Pylint: analyzing modified files from git diff")
            files = utils.get_files(filter="d")
            py_files = utils.filter_python_files(files)
        else:
            # PATH/DEFAULT MODE: Scan directories for Python files
            if mode == "path":
                logging.info(f"Pylint: analyzing {', '.join(utils.TARGET_PATHS)}")
            else:
                logging.info("Pylint: analyzing main_node/ and secondary_node/ (default)")
            all_files = utils.files_from_paths()
            py_files = utils.filter_python_files(all_files)

        if not py_files:
            logging.info("Pylint: No Python files found to analyze")
            return

        python_environment = os.environ.copy()
        if "PYTHONPATH" in python_environment:
            python_environment["PYTHONPATH"] = check_script_dir + ":" + python_environment["PYTHONPATH"]
        else:
            python_environment["PYTHONPATH"] = check_script_dir

        pylintcmd = [
            "pylint",
            "--output-format=json2",
            "--rcfile=" + pylintrc,
            "--load-plugins=argparse-checker",
        ] + py_files

        logging.debug(f"Running: {' '.join(pylintcmd)}")

        try:
            subprocess.run(
                pylintcmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=utils.GIT_TOP,
                env=python_environment,
            )
        except subprocess.CalledProcessError as ex:
            output = ex.output.decode("utf-8")

            # Try to parse JSON output
            try:
                result = json.loads(output)
                messages = result.get('messages', [])
            except (json.JSONDecodeError, KeyError) as e:
                # If JSON parsing fails, output is likely an error message
                logging.error(f"Failed to parse pylint JSON output: {e}")
                logging.error(f"Raw output: {output[:500]}")  # First 500 chars
                self.failure(f"Pylint execution failed:\n{output}")
                return

            for m in messages:
                severity = 'unknown'
                if m['messageId'][0] in ('F', 'E'):
                    severity = 'error'
                elif m['messageId'][0] in ('W', 'C', 'R', 'I'):
                    severity = 'warning'
                self.fmtd_failure(
                    severity,
                    m['messageId'],
                    m['path'],
                    m['line'],
                    col=str(m['column']),
                    desc=m['message'] + f" ({m['symbol']})",
                )

            if len(messages) == 0:
                # If there are no specific messages add the whole output as a failure
                self.failure(output)
