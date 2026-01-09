#!/usr/bin/env python3

"""
Coccinelle compliance check.
Runs Zephyr Coccinelle coding guideline checks on C/H files.
"""

import logging
import os
import subprocess
from pathlib import Path

from . import utils
from .base import ComplianceTest

logger = logging.getLogger(__name__)


class CoccinelleCheck(ComplianceTest):
    """
    Runs Zephyr Coccinelle coding guideline checks on codebase.
    """

    name = "Coccinelle"
    doc = "See https://docs.zephyrproject.org/latest/develop/coccinelle.html for more details"
    path_hint = "<git-top>"

    # Coccinelle rules to run in REPORT mode (must support --mode=report)
    REPORT_RULES = [
        "array_size.cocci",
        "boolean.cocci",
        "const_config_info.cocci",
        "deref_null.cocci",
        "find_dev_usage.cocci",
        "identifier_length.cocci",
        "int_ms_to_timeout.cocci",
        "mini_lock.cocci",
        "noderef.cocci",
        "reserved_names.cocci",
        "returnvar.cocci",
        "same_identifier.cocci",
        "semicolon.cocci",
        "unsigned_lesser_than_zero.cocci",
        "unsigned_suffix.cocci",
        "ztest_strcmp.cocci",
    ]

    # Rules for which we DO want to also inspect headers in REPORT mode
    HEADER_REPORT_RULES = {
        "array_size.cocci",
        "identifier_length.cocci",
        "reserved_names.cocci",
        "same_identifier.cocci",
    }

    def run(self, mode="default"):
        """
        Run the Coccinelle check.

        Args:
            mode: Analysis mode - "path" (explicit paths), "diff" (git diff), or "default"
        """
        # Find Zephyr root
        zephyr_root = utils.ZEPHYR_BASE
        if not zephyr_root.is_dir():
            self.skip("Zephyr tree not found at deps/zephyr")
            return

        # Prepare function pickle
        self._ensure_function_pickle(zephyr_root)

        # Determine target directories based on mode
        target_dirs = []

        if mode == "diff":
            # DIFF MODE: Analyze only modified C/H files from git diff
            logging.info("Coccinelle: analyzing modified files from git diff")
            files = utils.get_files(filter="d")
            c_files = [f for f in files if f.endswith(('.c', '.h'))]

            # Extract unique top-level directories from modified files
            # Coccinelle searches recursively, so we only need top-level dirs
            dirs_from_files = set()
            for file in c_files:
                file_path = Path(file)
                # Get top-level directory (e.g., "main_node" from "main_node/src/main.c")
                if len(file_path.parts) > 0:
                    top_dir = file_path.parts[0]
                    # Skip if in IGNORE_PATH_PARTS
                    if top_dir in utils.IGNORE_PATH_PARTS:
                        logging.debug(f"Skipping file in excluded directory: {file}")
                        continue
                    # Add absolute path of top-level directory
                    abs_dir = utils.GIT_TOP / top_dir
                    if abs_dir.is_dir():
                        dirs_from_files.add(str(abs_dir))

            target_dirs = sorted(dirs_from_files)

            if not target_dirs:
                self.skip("No C/H files modified in diff")
                return

        else:
            # PATH/DEFAULT MODE: Scan directories with absolute paths
            if mode == "path":
                logging.info(f"Coccinelle: analyzing {', '.join(utils.TARGET_PATHS)}")
                search_dirs = [utils.GIT_TOP / d for d in utils.TARGET_PATHS]
            else:
                logging.info("Coccinelle: analyzing main_node/ and secondary_node/ (default)")
                search_dirs = [utils.GIT_TOP / "main_node", utils.GIT_TOP / "secondary_node"]

            # Build list of absolute paths to analyze
            for d in search_dirs:
                full = d.resolve()

                # If analyzing repository root (.), expand into subdirectories
                if full == utils.GIT_TOP:
                    logging.info(f"Expanding repository root into subdirectories (excluding {utils.IGNORE_PATH_PARTS})")
                    for subdir in full.iterdir():
                        if not subdir.is_dir():
                            continue
                        # Skip directories in IGNORE_PATH_PARTS
                        if subdir.name in utils.IGNORE_PATH_PARTS:
                            logging.debug(f"Skipping excluded directory: {subdir.name}")
                            continue
                        target_dirs.append(str(subdir))
                        logging.debug(f"Added subdirectory: {subdir.name}")
                else:
                    # Specific directory: use it directly (unless it's in IGNORE_PATH_PARTS)
                    if full.name not in utils.IGNORE_PATH_PARTS:
                        target_dirs.append(str(full))
                    else:
                        logging.warning(f"Skipping excluded directory: {full.name}")

            if not target_dirs:
                self.skip("No target directories found to analyze")
                return

        logging.debug(f"Found {len(target_dirs)} director{'y' if len(target_dirs) == 1 else 'ies'} to analyze")

        # Store violations for JUnit reporting
        violations = []

        # Run checks in report mode only
        self._run_report_mode(zephyr_root, target_dirs, violations)

        # Report violations for JUnit XML
        for violation in violations:
            self.fmtd_failure(
                violation['severity'],
                f"Coccinelle ({violation['rule']})",
                violation['file'],
                line=int(violation['line']) if violation['line'].isdigit() else None,
                desc=violation['message'],
            )

    def _run_report_mode(self, zephyr_root: Path, target_dirs: list[str], violations: list):
        """Run all REPORT_RULES in report mode over all target_dirs."""
        for rule in self.REPORT_RULES:
            # Only some rules need header analysis
            if rule in self.HEADER_REPORT_RULES:
                sp_flags = ["--include-headers"]
            else:
                sp_flags = None

            for td in target_dirs:
                # Run coccicheck on each directory separately to ensure correct behavior
                _, rule_errors = self._run_coccinelle_rule(zephyr_root, rule, [td], sp_flags, violations)

                if rule_errors:
                    self.failure(f"Coccinelle rule {rule} failed with internal errors")

    def _ensure_function_pickle(self, zephyr_root: Path):
        """
        Ensure function_names.pickle exists in zephyr_root.

        Some Zephyr coccinelle scripts expect function_names.pickle to be present
        in Zephyr tree root. We generate it once by running find_functions.cocci
        with jobs=1 (as recommended upstream).
        """
        pickle_path = zephyr_root / "function_names.pickle"
        if pickle_path.exists():
            return

        logging.debug("Generating function_names.pickle for Coccinelle")

        coccicheck = zephyr_root / "scripts" / "coccicheck"
        cocci_file = zephyr_root / "scripts" / "coccinelle" / "find_functions.cocci"

        cmd = [
            str(coccicheck),
            "--mode=report",
            "--jobs=1",
            f"--cocci={cocci_file}",
            "--sp-flag=--include-headers",
            ".",
        ]

        logging.debug(f"Running: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            cwd=zephyr_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        if result.returncode != 0:
            logging.warning("find_functions.cocci failed while generating function_names.pickle")
            return

        if not pickle_path.exists():
            logging.warning("function_names.pickle was not created after find_functions.cocci ran")
            return

    def _run_coccinelle_rule(
        self,
        zephyr_root: Path,
        rule: str,
        target_dirs: list[str],
        extra_sp_flags: list[str] = None,
        violations_list: list = None,
    ):
        """
        Run a single Coccinelle rule in report mode and parse violations.

        Returns (had_issues, had_errors):
          - had_issues = True  if any WARNING:/ERROR: lines were seen
          - had_errors = True  if coccicheck failed in an unexpected way
        """
        coccicheck = zephyr_root / "scripts" / "coccicheck"
        cocci_file = zephyr_root / "scripts" / "coccinelle" / rule

        if not cocci_file.is_file():
            logging.warning(f"Skipping rule {rule} (file not found: {cocci_file})")
            return False, False

        cmd = [
            str(coccicheck),
            "--mode=report",
            f"--cocci={cocci_file}",
        ]

        # Extra semantic patch flags (e.g. --include-headers) if requested
        if extra_sp_flags:
            for flag in extra_sp_flags:
                cmd.append(f"--sp-flag={flag}")

        cmd.extend(target_dirs)

        logging.debug(f"Running: {' '.join(cmd)}")

        # Run command silently (capture output)
        result = subprocess.run(
            cmd,
            cwd=zephyr_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        raw_output = result.stdout or ""

        # Parse output for violations
        had_issues = False
        had_errors = False

        for line in raw_output.splitlines():
            if "WARNING:" in line or "ERROR:" in line:
                stripped = line.lstrip()
                path_part = stripped.split(":", 1)[0]

                if self._path_is_in_build_dir(path_part):
                    continue  # Skip build directories

                had_issues = True
                # Store violation for JUnit reporting
                if violations_list is not None:
                    try:
                        # Parse line format: filename:line:column: TYPE: message
                        parts = stripped.split(":", 4)
                        if len(parts) >= 3:
                            filename = parts[0]
                            line_num = parts[1]
                            rest = ":".join(parts[2:])

                            # Extract type and message
                            if "ERROR:" in rest:
                                severity = "error"
                                message = rest.split("ERROR:", 1)[1].strip()
                            elif "WARNING:" in rest:
                                severity = "warning"
                                message = rest.split("WARNING:", 1)[1].strip()
                            else:
                                severity = "warning"
                                message = rest.strip()

                            # Convert path relative to zephyr_root to absolute path
                            abs_path = (zephyr_root / filename).resolve()
                            violations_list.append(
                                {
                                    'file': str(abs_path),
                                    'line': line_num,
                                    'severity': severity,
                                    'message': message,
                                    'rule': rule,
                                }
                            )
                    except Exception:
                        pass  # Skip parsing errors

            if "Invalid mode" in line:
                had_errors = True

        # coccicheck convention: 0 = no matches, 1 = matches found, >1 = internal error
        if result.returncode not in (0, 1):
            had_errors = True

        return had_issues, had_errors

    def _path_is_in_build_dir(self, path_str: str) -> bool:
        """
        Return True if the given file path lives under a build* directory.

        We normalize the path and then look for any segment equal to 'build'
        or starting with 'build_' (e.g. build_xm126, build_boya_lora, etc.).
        """
        cleaned = path_str.lstrip("./").lstrip(".\\")
        cleaned = os.path.normpath(cleaned)
        segments = cleaned.split(os.sep)

        return any(seg == "build" or seg.startswith("build_") for seg in segments)
