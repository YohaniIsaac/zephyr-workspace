#!/usr/bin/env python3

"""
DevicetreeBindings compliance check.
Checks if we are introducing any unwanted properties in Devicetree Bindings.
"""

import os
import subprocess
import sys
from glob import glob
from pathlib import Path

from . import utils
from .base import ComplianceTest


class DevicetreeBindingsCheck(ComplianceTest):
    """
    Checks if we are introducing any unwanted properties in Devicetree Bindings.
    """

    name = "DevicetreeBindings"
    doc = "See https://docs.zephyrproject.org/latest/build/dts/bindings-syntax.html for more details."
    path_hint = "<git-top>"

    def run(self, mode="default"):
        """
        Run the DevicetreeBindings check.

        Args:
            mode: Analysis mode - "path" (explicit paths), "diff" (git diff), or "default"
        """
        bindings_diff, bindings = self.get_yaml_bindings(mode)

        if mode in ("path", "default"):
            # PATH/DEFAULT MODE
            if not bindings:
                self.skip("no devicetree bindings found in selected paths")
                return
        else:
            # DIFF MODE
            if not bindings_diff:
                self.skip("no changes to bindings were made")
                return
            try:
                subprocess.check_call(["git", "diff", "--quiet", utils.COMMIT_RANGE] + bindings_diff, cwd=utils.GIT_TOP)
                self.skip("no changes to bindings were made")
                return
            except subprocess.CalledProcessError:
                pass

        for binding in bindings:
            self.check(binding, self.check_yaml_property_name)
            self.check(binding, self.required_false_check)

    @staticmethod
    def check(binding, callback):
        while binding is not None:
            callback(binding)
            binding = binding.child_binding

    def _get_edtlib(self):
        """Load edtlib from Zephyr."""
        dts_lib = utils.ZEPHYR_BASE / "scripts" / "dts" / "python-devicetree" / "src"
        if str(dts_lib) not in sys.path:
            sys.path.insert(0, str(dts_lib))
        try:
            from devicetree import edtlib
        except Exception:
            self.skip("python-devicetree (edtlib) not available from deps/zephyr")
            return None
        return edtlib

    def _load_property_allowlist(self):
        """Load property names allowlist from bindings_properties_allowlist.yaml."""
        allow = set()
        allow_path = utils.GIT_TOP / "bindings_properties_allowlist.yaml"
        if not allow_path.exists():
            return allow

        try:
            import yaml

            data = yaml.safe_load(allow_path.read_text(encoding="utf-8", errors="replace"))
            if data:
                allow = set(data)
        except Exception:
            allow = set()

        return allow

    def get_yaml_bindings(self, mode):
        """
        Returns bindings under '**/dts/bindings/**/*.yaml'
        In diff mode (-c): limit to the binding roots that changed.
        In path/default mode (-p or default): scan selected paths.

        Args:
            mode: Analysis mode - "path", "diff", or "default"

        Returns:
            Tuple of (bindings_diff, bindings)
        """
        BINDINGS_PATH = "dts/bindings/"
        BINDINGS_MATCH = "/" + BINDINGS_PATH

        bindings_diff_dir = set()
        yamls = []

        def _is_binding_yaml(p: str) -> bool:
            p = p.replace("\\", "/")
            return (p.startswith(BINDINGS_PATH) or (BINDINGS_MATCH in p)) and p.endswith(".yaml")

        if mode in ("path", "default"):
            # PATH/DEFAULT MODE: Scan filesystem directly
            for f in utils.files_from_paths():
                if _is_binding_yaml(f):
                    yamls.append(f)
            bindings_diff = []
        else:
            # DIFF MODE: Find which binding roots changed, then scan all yamls under them
            for file_name in utils.get_files(filter="d"):
                f = file_name.replace("\\", "/")
                if f.startswith(BINDINGS_PATH) or (BINDINGS_MATCH in f):
                    before, _, _ = f.partition(BINDINGS_PATH)
                    bindings_diff_dir.add(os.path.join(before, BINDINGS_PATH))

            for path in bindings_diff_dir:
                yamls.extend(glob(f"{os.fspath(path)}/**/*.yaml", recursive=True))

            bindings_diff = sorted(bindings_diff_dir)

        edtlib = self._get_edtlib()
        if edtlib is None:
            return bindings_diff, []

        # Add Zephyr bindings for reference
        zephyr_bindings_dir = utils.ZEPHYR_BASE / "dts" / "bindings"
        support_yamls = []
        if zephyr_bindings_dir.exists():
            support_yamls = glob(f"{os.fspath(zephyr_bindings_dir)}/**/*.yaml", recursive=True)

        parse_list = list(dict.fromkeys(yamls + support_yamls))

        bindings_all = edtlib.bindings_from_paths(parse_list, ignore_errors=True)

        wanted = {str((utils.GIT_TOP / y).resolve()) for y in yamls}
        bindings = [b for b in bindings_all if str(Path(b.path).resolve()) in wanted]

        return bindings_diff, bindings

    def check_yaml_property_name(self, binding):
        """
        Checks if the property names in the binding file contain underscores.
        """
        allowlist = self._load_property_allowlist()

        for prop_name in binding.prop2specs:
            if "_" in prop_name and prop_name not in allowlist:
                better_prop = prop_name.replace("_", "-")
                self.failure(
                    f"{binding.path}: property '{prop_name}' contains underscores.\n"
                    f"\tUse '{better_prop}' instead unless this property name is from Linux\n"
                    "Or another authoritative upstream source of bindings for "
                    f"compatible '{binding.compatible}'.\n"
                    "\tHint: update 'bindings_properties_allowlist.yaml' if you need to "
                    "override this check for this property."
                )

    def required_false_check(self, binding):
        raw_props = binding.raw.get("properties", {})
        for prop_name, raw_prop in raw_props.items():
            if raw_prop.get("required") is False:
                self.failure(f'{binding.path}: property "{prop_name}": \'required: false\' is redundant, please remove')
