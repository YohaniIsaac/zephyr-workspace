#!/usr/bin/env python3

"""
DevicetreeLinting compliance check.
Checks DeviceTree files for syntax and formatting issues using dts-linter.
"""

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

from . import utils
from .base import ComplianceTest

logger = logging.getLogger(__name__)


class DevicetreeLintingCheck(ComplianceTest):
    """
    Checks DeviceTree files for syntax and formatting issues using dts-linter.
    """

    name = "DevicetreeLinting"
    doc = "See https://docs.zephyrproject.org/latest/contribute/style/devicetree.html for more details."
    path_hint = "<git-top>"
    NPX_EXECUTABLE = "npx"

    def ensure_npx(self) -> bool:
        if not (npx_executable := shutil.which(self.NPX_EXECUTABLE)):
            return False
        try:
            self.npx_exe = npx_executable
            # --no prevents npx from fetching from registry
            subprocess.run(
                [self.npx_exe, "--prefix", "./scripts/checks", "--no", 'dts-linter', "--", "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                text=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def _parse_json_output(self, cmd, cwd=None):
        """Run command and parse single JSON output with issues array"""
        logging.debug(f"Running: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            check=False,
            text=True,
            cwd=cwd or utils.GIT_TOP,
        )

        # dts-linter returns exit code 1 when it finds formatting issues, which is expected
        # Only treat it as a fatal error if return code is something else (like 127 = command not found)
        if result.returncode not in (0, 1):
            error_msg = f"dts-linter exited with unexpected code {result.returncode}"
            if result.stderr:
                error_msg += f"\nstderr: {result.stderr}"
            if result.stdout:
                error_msg += f"\nstdout: {result.stdout}"
            raise RuntimeError(error_msg)

        if not result.stdout.strip():
            # No output means no issues found (success)
            return None

        try:
            json_data = json.loads(result.stdout)
            return json_data
        except json.JSONDecodeError as e:
            # Show what we tried to parse for debugging
            preview = result.stdout[:500] if len(result.stdout) > 500 else result.stdout
            raise RuntimeError(f"Failed to parse dts-linter JSON output: {e}\nOutput preview: {preview}") from e

    def _process_json_output(self, json_output: dict):
        if "issues" not in json_output:
            return

        cwd = json_output.get("cwd", "")
        logging.info(f"Processing issues from: {cwd}")

        for issue in json_output["issues"]:
            level = issue.get("level", "unknown")
            message = issue.get("message", "")

            if level == "info":
                logging.info(message)
            else:
                title = issue.get("title", "")
                file = issue.get("file", "")
                line = issue.get("startLine", None)
                col = issue.get("startCol", None)
                end_line = issue.get("endLine", None)
                end_col = issue.get("endCol", None)
                self.fmtd_failure(level, title, file, line, col, message, end_line, end_col)

    def run(self, mode="default"):
        """
        Run the DevicetreeLinting check.

        Args:
            mode: Analysis mode - "path" (explicit paths), "diff" (git diff), or "default"
        """
        self.npx_exe = self.NPX_EXECUTABLE

        if not self.ensure_npx():
            self.skip(
                'dts-linter not installed. To run this check, '
                'install Node.js and then run [npm --prefix ./scripts/checks ci] command inside '
                'WORKSPACE_BASE'
            )
            return

        temp_patch_files = []

        if mode == "diff":
            # DIFF MODE: Analyze only modified DTS files from git diff
            logging.info("DevicetreeLinting: analyzing modified files from git diff")
            files = utils.get_files(filter="d")
            dts_files = [f for f in files if f.endswith((".dts", ".dtsi", ".overlay"))]

            if not dts_files:
                self.skip('No DTS files modified')
                return

            batch_size = 500

            for i in range(0, len(dts_files), batch_size):
                batch = dts_files[i : i + batch_size]

                # use a temporary file for each batch
                temp_patch = utils.GIT_TOP / f"dts_linter_{i}.patch"
                temp_patch_files.append(temp_patch)

                cmd = [
                    self.npx_exe,
                    "--prefix",
                    str(utils.GIT_TOP / "scripts" / "checks"),
                    "--no",
                    "dts-linter",
                    "--",
                    "--outputFormat",
                    "json",
                    "--format",
                    "--patchFile",
                    str(temp_patch),
                ]
                for file in batch:
                    cmd.extend(["--file", file])

                try:
                    json_output = self._parse_json_output(cmd)
                    if json_output:
                        self._process_json_output(json_output)

                except subprocess.CalledProcessError as ex:
                    stderr_output = ex.stderr if ex.stderr else ""
                    if stderr_output.strip():
                        self.failure(f"dts-linter found issues:\n{stderr_output}")
                    else:
                        err = "dts-linter failed with no output. "
                        err += "Make sure you install Node.js and then run "
                        err += "[npm --prefix ./scripts/checks ci] inside WORKSPACE_BASE"
                        self.failure(err)
                except RuntimeError as ex:
                    self.failure(f"{ex}")

        else:
            # PATH/DEFAULT MODE: Directory scanning mode with application detection
            if mode == "path":
                logging.info(f"DevicetreeLinting: analyzing {', '.join(utils.TARGET_PATHS)}")
                search_dirs = [utils.GIT_TOP / d for d in utils.TARGET_PATHS]
            else:
                logging.info("DevicetreeLinting: analyzing main_node/ and secondary_node/ (default)")
                search_dirs = [utils.GIT_TOP / "main_node", utils.GIT_TOP / "secondary_node"]

            # Find all applications in search directories
            applications = self._find_applications(search_dirs)

            if not applications:
                logging.info("DevicetreeLinting: No applications found to analyze")
                return

            logging.debug(f"Found {len(applications)} application(s) to analyze")

            # Process each application separately with its own context
            app_number = 0

            for app_dir in applications:
                app_number += 1

                # Find DTS files in this specific application
                dts_files = self._find_dts_files_in_app(app_dir)

                if not dts_files:
                    continue

                # Process files in batches (dts-linter can handle multiple files at once)
                batch_size = 500
                for i in range(0, len(dts_files), batch_size):
                    batch = dts_files[i : i + batch_size]

                    # use a temporary file for each batch (absolute path so it's created in GIT_TOP)
                    temp_patch = utils.GIT_TOP / f"dts_linter_app{app_number}_batch{i}.patch"
                    temp_patch_files.append(temp_patch)

                    cmd = [
                        self.npx_exe,
                        "--prefix",
                        str(utils.GIT_TOP / "scripts" / "checks"),  # Use absolute path for --prefix
                        "--no",
                        "dts-linter",
                        "--",
                        "--cwd",
                        str(app_dir),  # Set working directory to application root
                        "--outputFormat",
                        "json",
                        "--format",
                        "--patchFile",
                        str(temp_patch),  # Use absolute path so patch is created in GIT_TOP
                    ]
                    for file in batch:
                        # Make file path relative to app_dir
                        file_path = utils.GIT_TOP / file
                        try:
                            rel_to_app = file_path.relative_to(app_dir)
                            cmd.extend(["--file", str(rel_to_app)])
                        except ValueError:
                            # File is outside app_dir, use absolute path
                            cmd.extend(["--file", str(file_path)])

                    try:
                        json_output = self._parse_json_output(cmd, cwd=app_dir)
                        if json_output:
                            self._process_json_output(json_output)

                    except subprocess.CalledProcessError as ex:
                        stderr_output = ex.stderr if ex.stderr else ""
                        if stderr_output.strip():
                            self.failure(
                                f"dts-linter found issues in {app_dir.relative_to(utils.GIT_TOP)}:\n{stderr_output}"
                            )
                        else:
                            err = f"dts-linter failed for {app_dir.relative_to(utils.GIT_TOP)} with no output. "
                            err += "Make sure you install Node.js and then run "
                            err += "[npm --prefix ./scripts/checks ci] inside WORKSPACE_BASE"
                            self.failure(err)
                    except RuntimeError as ex:
                        self.failure(f"Error in {app_dir.relative_to(utils.GIT_TOP)}: {ex}")

        # merge all temp patch files into one
        if temp_patch_files:
            final_patch_path = utils.GIT_TOP / "dts_linter.patch"
            with open(final_patch_path, "wb") as final_patch:
                for patch in temp_patch_files:
                    if patch.exists():
                        with open(patch, "rb") as f:
                            shutil.copyfileobj(f, final_patch)

            # cleanup temporary patch files
            for patch in temp_patch_files:
                if patch.exists():
                    patch.unlink()

            # If -n/--no-case-output is set, also remove the final patch file
            if hasattr(self, 'global_args') and self.global_args.no_case_output:
                if final_patch_path.exists():
                    final_patch_path.unlink()
                    logging.debug("Removed dts_linter.patch (--no-case-output mode)")
            else:
                logging.info(f"Generated formatting patch: {final_patch_path}")
                logging.info("Apply with: git apply dts_linter.patch")

    def _find_applications(self, search_dirs):
        """
        Find all Zephyr applications within the given directories.
        An application is a directory containing prj.conf or CMakeLists.txt.

        Returns list of application directories (as Path objects).
        """
        applications = []

        for search_dir in search_dirs:
            if not search_dir.exists():
                logging.warning(f"DevicetreeLinting: Directory does not exist: {search_dir}")
                continue

            # Check if search_dir itself is an application
            if (search_dir / "prj.conf").exists() or (search_dir / "CMakeLists.txt").exists():
                applications.append(search_dir)
            else:
                # Search for applications in subdirectories
                for root, dirs, files in os.walk(search_dir):
                    root_path = Path(root)

                    # Exclude directories in IGNORE_PATH_PARTS
                    dirs[:] = [d for d in dirs if d not in utils.IGNORE_PATH_PARTS]

                    # Check if this directory is an application
                    if "prj.conf" in files or "CMakeLists.txt" in files:
                        applications.append(root_path)
                        # Don't recurse into subdirectories of an application
                        dirs[:] = []

        return applications

    def _find_dts_files_in_app(self, app_dir):
        """
        Find all DeviceTree files within a specific application directory.
        Returns paths relative to GIT_TOP.
        """
        dts_files = []

        for root, dirs, files in os.walk(app_dir):
            # Exclude directories in IGNORE_PATH_PARTS
            dirs[:] = [d for d in dirs if d not in utils.IGNORE_PATH_PARTS]

            for file in files:
                if file.endswith(('.dts', '.dtsi', '.overlay')):
                    full_path = Path(root) / file
                    # Make path relative to GIT_TOP
                    try:
                        rel_path = full_path.relative_to(utils.GIT_TOP)
                        dts_files.append(str(rel_path))
                    except ValueError:
                        # Path is not relative to GIT_TOP, skip it
                        continue

        return dts_files
