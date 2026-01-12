#!/usr/bin/env python3

"""
Main orchestrator for compliance checks.

This script coordinates the execution of all compliance checks defined in the
compliance_checks package.
"""

import argparse
import logging
import os
import shlex
import sys
import traceback
from pathlib import Path

# ANSI color codes for colored output
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
ORANGE = '\033[38;5;214m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
BOLD = '\033[1m'
NC = '\033[0m'  # No Color

from compliance_checks import AVAILABLE_CHECKS, EndTest, git, init_globals, resolve_path_hint
from junitparser import JUnitXml, TestSuite

# Global variables (set by _main())
WORKSPACE_BASE = None
ZEPHYR_BASE = None

logger = logging.getLogger(__name__)


def get_shas(refspec):
    """Returns the list of Git SHAs for 'refspec'."""
    return git("rev-list", f"--max-count={-1 if '.' in refspec else 1}", refspec).split()


def init_logs(cli_arg):
    """Initialize logging."""
    global logger

    level = os.environ.get("LOG_LEVEL", "WARN")

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(levelname)-8s: %(message)s"))

    logger = logging.getLogger("")
    logger.addHandler(console)
    logger.setLevel(cli_arg or level)

    logger.info("Log init completed, level=%s", logging.getLevelName(logger.getEffectiveLevel()))


def annotate(res):
    """Print GitHub Actions-compatible annotations."""
    msg = res.message.replace("%", "%25").replace("\n", "%0A").replace("\r", "%0D")
    notice = (
        f"::{res.severity} file={res.file}"
        + (f",line={res.line}" if res.line else "")
        + (f",col={res.col}" if res.col else "")
        + (f",endLine={res.end_line}" if res.end_line else "")
        + (f",endColumn={res.end_col}" if res.end_col else "")
        + f",title={res.title}::{msg}"
    )
    print(notice)


def parse_args(argv):
    """Parse command line arguments."""
    default_range = "HEAD~1..HEAD"
    parser = argparse.ArgumentParser(
        description="Check for coding style and documentation warnings.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "-c",
        "--commits",
        default=default_range,
        help=f"Commit range in the form: a..[b], default is {default_range}",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="compliance.xml",
        help="Name of outfile in JUnit format, default is ./compliance.xml",
    )
    parser.add_argument(
        "-n",
        "--no-case-output",
        action="store_true",
        help="Do not store the individual test case output.",
    )
    parser.add_argument("-l", "--list", action="store_true", help="List all checks and exit")
    parser.add_argument(
        "-v",
        "--loglevel",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="python logging level",
    )
    parser.add_argument(
        "-m",
        "--module",
        action="append",
        default=[],
        help="Checks to run. All checks by default. (case insensitive)",
    )
    parser.add_argument(
        "-e",
        "--exclude-module",
        action="append",
        default=[],
        help="Do not run the specified checks (case insensitive)",
    )
    parser.add_argument(
        "-j",
        "--previous-run",
        default=None,
        help="Pre-load JUnit results in XML format from a previous run and combine with new results.",
    )
    parser.add_argument(
        "--annotate",
        action="store_true",
        help="Print GitHub Actions-compatible annotations.",
    )
    parser.add_argument(
        "-p",
        "--path",
        action="append",
        dest="path_list",
        metavar="DIR",
        help=("Application directory to analyze (can be specified multiple times). Default: main_node, secondary_node"),
    )

    args = parser.parse_args(argv)

    # Handle -p argument: flatten list if using multiple -p flags
    if args.path_list:
        args.path = args.path_list  # List of individual paths from multiple -p
    else:
        args.path = ["main_node", "secondary_node"]  # Default

    # Track if -c/--commits was explicitly specified by the user
    args.commits_explicit = '-c' in argv or '--commits' in argv

    # Track if -p/--path was explicitly specified by the user
    args.path_explicit = args.path_list is not None

    return args


def _main(args):
    """The main function that orchestrates all checks."""
    # Initialize global variables
    WORKSPACE_BASE = os.environ.get("WORKSPACE_BASE")
    if WORKSPACE_BASE:
        WORKSPACE_BASE = Path(WORKSPACE_BASE)
        ZEPHYR_BASE = WORKSPACE_BASE / "deps" / "zephyr"
    else:
        WORKSPACE_BASE = Path(__file__).resolve().parents[2]
        os.environ["WORKSPACE_BASE"] = str(WORKSPACE_BASE)
        ZEPHYR_BASE = WORKSPACE_BASE / "deps" / "zephyr"

    GIT_TOP = Path(git("rev-parse", "--show-toplevel"))
    COMMIT_RANGE = args.commits

    # Determine analysis mode and set TARGET_PATHS accordingly
    if args.path_explicit:
        # PATH MODE: User explicitly specified -p/--path
        mode = "path"
        TARGET_PATHS = args.path
    elif args.commits_explicit:
        # DIFF MODE: User explicitly specified -c/--commits
        mode = "diff"
        TARGET_PATHS = []
    else:
        # DEFAULT MODE: No flags specified, use default directories
        mode = "default"
        TARGET_PATHS = ["main_node", "secondary_node"]

    init_globals(
        git_top=GIT_TOP,
        commit_range=COMMIT_RANGE,
        target_paths=TARGET_PATHS,
        workspace_base=WORKSPACE_BASE,
        zephyr_base=ZEPHYR_BASE,
    )
    init_logs(args.loglevel)

    logger.info(f"Running tests in '{mode}' mode")

    if args.list:
        for check_name in sorted(AVAILABLE_CHECKS.keys()):
            print(AVAILABLE_CHECKS[check_name].name)
        return 0

    # Load saved test results from an earlier run, if requested
    if args.previous_run:
        if not os.path.exists(args.previous_run):
            print(f"error: '{args.previous_run}' not found", file=sys.stderr)
            return 1

        logging.info(f"Loading previous results from {args.previous_run}")
        for loaded_suite in JUnitXml.fromfile(args.previous_run):
            suite = loaded_suite
            break
    else:
        suite = TestSuite("Compliance")

    included = list(map(lambda x: x.lower(), args.module))
    excluded = list(map(lambda x: x.lower(), args.exclude_module))

    # Get all available check classes
    check_classes = AVAILABLE_CHECKS.values()

    for testcase_class in check_classes:
        # Filter checks based on include/exclude lists
        if included and testcase_class.name.lower() not in included:
            continue

        if testcase_class.name.lower() in excluded:
            print(f"{ORANGE}Skipping {testcase_class.name}{NC}")
            continue

        test = testcase_class()
        test.global_args = args  # Pass global args to test instance

        # Save environment before check to ensure isolation between checks
        # Each check should be self-contained and not affect others
        saved_env = os.environ.copy()

        try:
            print(f"{BLUE}Running {test.name:30}{NC} tests in {resolve_path_hint(test.path_hint)} ...")
            # Each check will use what it needs
            logging.info(f"Modo: {mode}")
            test.run(
                mode=mode,
            )
        except EndTest:
            pass
        except BaseException:
            test.failure(f"An exception occurred in {test.name}:\n{traceback.format_exc()}")

        finally:
            # Restore environment after check to prevent pollution
            os.environ.clear()
            os.environ.update(saved_env)
            logger.debug(f"Environment restored after {test.name}")

        # Annotate if required
        if args.annotate:
            for res in test.fmtd_failures:
                annotate(res)

        suite.add_testcase(test.case)

    if args.output:
        xml = JUnitXml()
        xml.add_testsuite(suite)
        xml.update_statistics()
        xml.write(args.output, pretty=True)

    failed_cases = []
    warning_cases = []
    name2doc = {testcase_class.name: testcase_class.doc for testcase_class in check_classes}

    for case in suite:
        if case.result:
            if case.is_skipped:
                logging.warning(f"Skipped {case.name}")
            else:
                if any(res.type in ("error", "failure") for res in case.result):
                    failed_cases.append(case)
                else:
                    warning_cases.append(case)
        else:
            logging.info(f"No JUnit result for {case.name}")

    n_fails = len(failed_cases)
    n_warnings = len(warning_cases)

    if n_fails or n_warnings:
        if n_fails:
            print(f"{RED}{n_fails} check(s) failed{NC}")
        if n_warnings:
            print(f"{YELLOW}{n_warnings} check(s) with warnings only{NC}")

        for case in failed_cases + warning_cases:
            print("", RED + "-" * 80, BOLD + case.name, RED + "-" * 80 + NC, sep="\n")
            for res in case.result:
                errmsg = res.text.strip()
                if res.type in ("error", "failure"):
                    logging.error(f"Test {case.name} failed: \n{errmsg}")
                else:
                    logging.warning(f"Test {case.name} warning: \n{errmsg}")

            if args.no_case_output:
                continue
            with open(f"{case.name}.txt", "w") as f:
                docs = name2doc.get(case.name)
                f.write(f"{docs}\n")
                for res in case.result:
                    errmsg = res.text.strip()
                    f.write(f"\n {errmsg}")

    if args.output:
        print(f"\nComplete results in {args.output}")
    return n_fails + n_warnings


def main(argv=None):
    """Entry point."""
    args = parse_args(argv)

    try:
        n_fails = _main(args)
    except BaseException:
        print(f"Python exception in `{__file__}`:\n\n```\n{traceback.format_exc()}\n```")
        raise

    sys.exit(n_fails)


def cmd2str(cmd):
    """Formats the command-line arguments in the iterable 'cmd' into a string."""
    return " ".join(shlex.quote(word) for word in cmd)


def err(msg):
    """Print error message and exit."""
    cmd = sys.argv[0]
    if cmd:
        cmd += ": "
    sys.exit(f"{cmd} error: {msg}")


if __name__ == "__main__":
    main(sys.argv[1:])
