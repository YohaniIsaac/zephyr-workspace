#!/usr/bin/env python3

"""
YAMLLint compliance check.
Checks YAML files for syntax and style issues using yamllint.
"""

from pathlib import Path

from yamllint import config, linter

from . import utils
from .base import ComplianceTest


class YAMLLint(ComplianceTest):
    """
    Runs yamllint on YAML files and reports issues.
    """

    name = "YAMLLint"
    doc = "Check YAML files with YAMLLint."
    path_hint = "<git-top>"

    def run(self, mode="default"):
        """
        Run the YAMLLint check.

        Args:
            mode: Analysis mode - "path" (explicit paths), "diff" (git diff), or "default" (node/ and lora_gateway/)
        """
        config_file = utils.OXYCONTROLLER_BASE / ".yamllint"

        # Determine which files to check based on mode
        if mode in ("path", "default"):
            # PATH/DEFAULT MODE: Scan filesystem
            files = utils.files_from_paths()
        else:
            # DIFF MODE: Use git diff
            files = utils.get_files(filter="d")

        for file in files:
            if Path(file).suffix not in ['.yaml', '.yml']:
                continue

            yaml_config = config.YamlLintConfig(file=config_file)

            # Tweak rules for specific files
            if file.startswith(".github/"):
                # Workflow files have different rules
                yaml_config.rules["line-length"] = False
                yaml_config.rules["truthy"]["allowed-values"].extend(['on', 'off'])
            elif file == ".codecov.yml":
                yaml_config.rules["truthy"]["allowed-values"].extend(['yes', 'no'])

            full_path = utils.GIT_TOP / file
            with open(full_path, encoding="utf-8") as fp:
                for p in linter.run(fp, yaml_config):
                    self.fmtd_failure('warning', f'YAMLLint ({p.rule})', file, p.line, col=p.column, desc=p.desc)
