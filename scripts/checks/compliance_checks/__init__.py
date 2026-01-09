#!/usr/bin/env python3

"""
Compliance checks package.

This package contains modular compliance checks for the zephyr-workspace project.
Each check is implemented in its own module.
"""

# Export base classes
from .base import ComplianceTest, EndTest, FmtdFailure

# Import all check classes
from .checkpatch import CheckPatch
from .clang_format import ClangFormat
from .cmake_style import CMakeStyle
from .coccinelle import CoccinelleCheck
from .codechecker import CodeChecker
from .devicetree_bindings import DevicetreeBindingsCheck
from .devicetree_linting import DevicetreeLintingCheck
from .kconfig import KconfigCheck
from .pylint import PyLint
from .ruff import Ruff
from .utils import git, init_globals, resolve_path_hint
from .yaml_lint import YAMLLint

# Registry of available checks
# Maps check name (lowercase) to check class
AVAILABLE_CHECKS = {
    'clangformat': ClangFormat,
    'checkpatch': CheckPatch,
    'cmakestyle': CMakeStyle,
    'devicetreebindings': DevicetreeBindingsCheck,
    'yamllint': YAMLLint,
    'kconfig': KconfigCheck,
    'pylint': PyLint,
    'ruff': Ruff,
    'coccinelle': CoccinelleCheck,
    'devicetreelinting': DevicetreeLintingCheck,
    'codechecker': CodeChecker,
}

# For backwards compatibility, also export by name
__all__ = [
    'AVAILABLE_CHECKS',
    'CheckPatch',
    'ClangFormat',
    'CMakeStyle',
    'CoccinelleCheck',
    'ComplianceTest',
    'DevicetreeBindingsCheck',
    'DevicetreeLintingCheck',
    'CodeChecker',
    'EndTest',
    'FmtdFailure',
    'KconfigCheck',
    'PyLint',
    'Ruff',
    'YAMLLint',
    'git',
    'init_globals',
    'resolve_path_hint',
]
