#!/usr/bin/env python3

"""
Kconfig compliance check.
Checks for Kconfig warnings/errors such as undefined Kconfig variables.
"""

import argparse
import collections
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import utils
from .base import ComplianceTest, EndTest

logger = logging.getLogger(__name__)


class KconfigCheck(ComplianceTest):
    """
    Checks if we are introducing any new warnings/errors with Kconfig,
    for example using undefined Kconfig variables.
    """

    name = "Kconfig"
    doc = "See https://docs.zephyrproject.org/latest/build/kconfig/tips.html for more details."
    path_hint = "<git-top>"

    def run(self, mode="default"):
        """
        Run the Kconfig check.

        Args:
            mode: Analysis mode - "path" (explicit paths), "diff" (git diff), or "default" (node/ and lora_gateway/)
        """
        full = True
        self.no_modules = False
        filename = "Kconfig"
        hwm = None

        if mode == "diff":
            # DIFF MODE: Kconfig checks don't make sense in diff mode
            self.skip("Kconfig checks are not applicable in diff mode (use -p or default mode)")
            return

        # Determine which directories to analyze
        if mode == "path":
            # PATH MODE: Use explicit paths from -p
            app_dirs = [d.rstrip('/') for d in utils.TARGET_PATHS if d != '.']
            analyze_all = '.' in utils.TARGET_PATHS
        else:
            # DEFAULT MODE: Analyze node/ and lora_gateway/
            app_dirs = ["node", "lora_gateway"]
            analyze_all = False

        # Execute analysis
        if analyze_all:
            logging.info("Kconfig: analyzing entire repository")
            self._run_full_analysis(full, filename, hwm)
        else:
            logging.info(f"Kconfig: analyzing {', '.join(app_dirs)}")
            self._run_multi_app_analysis(app_dirs, full, filename, hwm)

    def _run_full_analysis(self, full, filename, hwm):
        """Analyze entire repository."""
        self.current_app_dir = None  # None = search entire repo (excluding deps/)

        # Use lora_gateway/Kconfig or fallback to Kconfig.zephyr
        app_kconfig = self._find_entry_kconfig("lora_gateway", filename)

        kconf = self.parse_kconfig(filename=app_kconfig, hwm=hwm)

        # Execute ALL checks
        self.check_no_pointless_menuconfigs(kconf)
        self.check_no_undef_within_kconfig(kconf)
        self.check_no_redefined_in_defconfig(kconf)
        self.check_no_enable_in_boolean_prompt(kconf)
        self.check_soc_name_sync(kconf)
        if full:
            self.check_no_undef_outside_kconfig(kconf)

    def _run_multi_app_analysis(self, app_dirs, full, filename, hwm):
        """Analyze multiple application directories independently."""
        # Run global Kconfig structure checks ONCE
        logging.info("Running global Kconfig structure checks")

        # Use first app with Kconfig, or fallback to lora_gateway, then Zephyr
        base_kconfig = None
        for app_dir in app_dirs:
            kconfig_path = utils.OXYCONTROLLER_BASE / app_dir / filename
            if kconfig_path.exists():
                base_kconfig = str(kconfig_path)
                logging.info(f"Using {app_dir}/{filename} for global checks")
                break

        if not base_kconfig:
            base_kconfig = self._find_entry_kconfig("deps/zephyr", filename)
            logging.info(f"Using fallback: {base_kconfig}")

        kconf_base = self.parse_kconfig(filename=base_kconfig, hwm=hwm)

        self.check_no_pointless_menuconfigs(kconf_base)
        self.check_no_undef_within_kconfig(kconf_base)
        self.check_no_redefined_in_defconfig(kconf_base)
        self.check_no_enable_in_boolean_prompt(kconf_base)
        self.check_soc_name_sync(kconf_base)

        # Run per-app CONFIG_* reference checks
        if not full:
            return

        logging.info("Running per-application CONFIG_* reference checks")
        for app_dir in app_dirs:
            self._check_app_config_references(app_dir, filename, hwm)

    def _check_app_config_references(self, app_dir, filename, hwm):
        """Check CONFIG_* references for a single application."""
        app_path = utils.OXYCONTROLLER_BASE / app_dir
        if not app_path.is_dir():
            logging.warning(f"Skipping {app_dir}: directory not found")
            return

        logging.info(f"Checking application: {app_dir}/")

        # Detect Kconfig and parse appropriate tree
        app_kconfig_path = app_path / filename
        if app_kconfig_path.exists():
            logging.debug(f"Using app Kconfig: {app_dir}/{filename}")
            kconf = self.parse_kconfig(filename=str(app_kconfig_path), hwm=hwm)
        else:
            logging.debug("No app Kconfig, using Zephyr base")
            kconf = self.parse_kconfig(filename=str(utils.ZEPHYR_BASE / "Kconfig.zephyr"), hwm=hwm)

        # Execute check filtered by app_dir
        self.current_app_dir = app_dir
        self.check_no_undef_outside_kconfig(kconf)

    def _find_entry_kconfig(self, app_dir, filename):
        """Find entry Kconfig for an app (or fallback to Zephyr)."""
        kconfig_path = utils.OXYCONTROLLER_BASE / app_dir / filename
        if kconfig_path.exists():
            return str(kconfig_path)
        return str(utils.ZEPHYR_BASE / "Kconfig.zephyr")

    def get_modules(self, modules_file, settings_file):
        """
        Get a list of modules and put them in a file that is parsed by
        Kconfig

        This is needed to complete Kconfig sanity tests.

        """
        if self.no_modules:
            with open(modules_file, 'w') as fp_module_file:
                fp_module_file.write("# Empty\n")
            return

        # Invoke the script directly using the Python executable since this is
        # not a module nor a pip-installed Python utility
        zephyr_module_path = os.path.join(utils.ZEPHYR_BASE, "scripts", "zephyr_module.py")
        cmd = [sys.executable, zephyr_module_path, '--kconfig-out', modules_file, '--settings-out', settings_file]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as ex:
            self.error(ex.output.decode("utf-8"))

        modules_dir = utils.ZEPHYR_BASE / 'modules'
        modules = [name for name in os.listdir(modules_dir) if os.path.exists(modules_dir / name / 'Kconfig')]

        with open(modules_file) as fp_module_file:
            content = fp_module_file.read()

        with open(modules_file, 'w') as fp_module_file:
            for module in modules:
                fp_module_file.write(
                    "ZEPHYR_{}_KCONFIG = {}\n".format(
                        re.sub('[^a-zA-Z0-9]', '_', module).upper(), str(modules_dir / module / 'Kconfig')
                    )
                )
            fp_module_file.write(content)

    def get_kconfig_dts(self, kconfig_dts_file, settings_file):
        """
        Generate the Kconfig.dts using dts/bindings as the source.

        This is needed to complete Kconfig compliance tests.

        """
        # Invoke the script directly using the Python executable since this is
        # not a module nor a pip-installed Python utility
        zephyr_drv_kconfig_path = os.path.join(utils.ZEPHYR_BASE, "scripts", "dts", "gen_driver_kconfig_dts.py")
        binding_paths = []
        binding_paths.append(os.path.join(utils.ZEPHYR_BASE, "dts", "bindings"))

        if os.path.exists(settings_file):
            with open(settings_file) as fp_setting_file:
                content = fp_setting_file.read()

            lines = content.strip().split('\n')
            for line in lines:
                if line.startswith('"DTS_ROOT":'):
                    _, dts_root_path = line.split(":", 1)
                    binding_paths.append(os.path.join(dts_root_path.strip('"'), "dts", "bindings"))

        cmd = [sys.executable, zephyr_drv_kconfig_path, '--kconfig-out', kconfig_dts_file, '--bindings-dirs']
        for binding_path in binding_paths:
            cmd.append(binding_path)
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as ex:
            self.error(ex.output.decode("utf-8"))

    def get_v1_model_syms(self, kconfig_v1_file, kconfig_v1_syms_file):
        """
        Generate a symbol define Kconfig file.
        This function creates a file with all Kconfig symbol definitions from
        old boards model so that those symbols will not appear as undefined
        symbols in hardware model v2.

        This is needed to complete Kconfig compliance tests.
        """
        os.environ['HWM_SCHEME'] = 'v1'
        # 'kconfiglib' is global
        # pylint: disable=undefined-variable

        try:
            kconf_v1 = kconfiglib.Kconfig(filename=kconfig_v1_file, warn=False)
        except kconfiglib.KconfigError as e:
            self.failure(str(e))
            raise EndTest from e

        with open(kconfig_v1_syms_file, 'w') as fp_kconfig_v1_syms_file:
            for s in kconf_v1.defined_syms:
                if s.type != kconfiglib.UNKNOWN:
                    fp_kconfig_v1_syms_file.write('config ' + s.name)
                    fp_kconfig_v1_syms_file.write('\n\t' + kconfiglib.TYPE_TO_STR[s.type])
                    fp_kconfig_v1_syms_file.write('\n\n')

    def get_v2_model(self, kconfig_dir):
        """
        Get lists of v2 boards and SoCs and put them in a file that is parsed by
        Kconfig

        This is needed to complete Kconfig sanity tests.
        """
        # Import Zephyr scripts dynamically
        zephyr_scripts_path = str(utils.ZEPHYR_BASE / "scripts")
        if zephyr_scripts_path not in sys.path:
            sys.path.insert(0, zephyr_scripts_path)
        import list_boards
        import list_hardware

        os.environ['HWM_SCHEME'] = 'v2'
        kconfig_file = os.path.join(kconfig_dir, 'boards', 'Kconfig')
        kconfig_boards_file = os.path.join(kconfig_dir, 'boards', 'Kconfig.boards')
        kconfig_defconfig_file = os.path.join(kconfig_dir, 'boards', 'Kconfig.defconfig')

        # Read BOARD_ROOT from settings_file to include module boards
        board_roots = [Path(utils.ZEPHYR_BASE)]
        soc_roots = [Path(utils.ZEPHYR_BASE)]
        settings_file = os.path.join(kconfig_dir, 'settings_file.txt')

        if os.path.exists(settings_file):
            with open(settings_file) as f:
                for line in f:
                    if '"BOARD_ROOT":' in line:
                        match = re.search(r'"BOARD_ROOT":"(.+?)"', line)
                        if match:
                            board_root = Path(match.group(1))
                            if board_root not in board_roots:
                                board_roots.append(board_root)
                    elif '"SOC_ROOT":' in line:
                        match = re.search(r'"SOC_ROOT":"(.+?)"', line)
                        if match:
                            soc_root = Path(match.group(1))
                            if soc_root not in soc_roots:
                                soc_roots.append(soc_root)

        root_args = argparse.Namespace(
            **{'board_roots': board_roots, 'soc_roots': soc_roots, 'board': None, 'board_dir': []}
        )
        v2_boards = list_boards.find_v2_boards(root_args)

        with open(kconfig_defconfig_file, 'w') as fp:
            for board in v2_boards.values():
                fp.write('osource "' + (Path(board.dir) / 'Kconfig.defconfig').as_posix() + '"\n')

        with open(kconfig_boards_file, 'w') as fp:
            for board in v2_boards.values():
                board_str = 'BOARD_' + re.sub(r"[^a-zA-Z0-9_]", "_", board.name).upper()
                fp.write('config  ' + board_str + '\n')
                fp.write('\t bool\n')
                for qualifier in list_boards.board_v2_qualifiers(board):
                    board_str = ('BOARD_' + board.name + '_' + re.sub(r"[^a-zA-Z0-9_]", "_", qualifier)).upper()
                    fp.write('config  ' + board_str + '\n')
                    fp.write('\t bool\n')
                fp.write('source "' + (Path(board.dir) / ('Kconfig.' + board.name)).as_posix() + '"\n\n')

        with open(kconfig_file, 'w') as fp:
            fp.write('osource "' + (Path(kconfig_dir) / 'boards' / 'Kconfig.syms.v1').as_posix() + '"\n')
            for board in v2_boards.values():
                fp.write('osource "' + (Path(board.dir) / 'Kconfig').as_posix() + '"\n')

        kconfig_defconfig_file = os.path.join(kconfig_dir, 'soc', 'Kconfig.defconfig')
        kconfig_soc_file = os.path.join(kconfig_dir, 'soc', 'Kconfig.soc')
        kconfig_file = os.path.join(kconfig_dir, 'soc', 'Kconfig')

        # Use the soc_roots already extracted from settings_file above
        root_args = argparse.Namespace(**{'soc_roots': soc_roots})
        v2_systems = list_hardware.find_v2_systems(root_args)

        # soc.folder es una lista, necesitamos aplanarla
        soc_folders = {folder for soc in v2_systems.get_socs() for folder in soc.folder}
        with open(kconfig_defconfig_file, 'w') as fp:
            for folder in soc_folders:
                fp.write('osource "' + (Path(folder) / 'Kconfig.defconfig').as_posix() + '"\n')

        with open(kconfig_soc_file, 'w') as fp:
            for folder in soc_folders:
                fp.write('source "' + (Path(folder) / 'Kconfig.soc').as_posix() + '"\n')

        with open(kconfig_file, 'w') as fp:
            for folder in soc_folders:
                fp.write('source "' + (Path(folder) / 'Kconfig').as_posix() + '"\n')

        kconfig_file = os.path.join(kconfig_dir, 'arch', 'Kconfig')

        root_args = argparse.Namespace(**{'arch_roots': [Path(utils.ZEPHYR_BASE)], 'arch': None})
        v2_archs = list_hardware.find_v2_archs(root_args)

        with open(kconfig_file, 'w') as fp:
            for arch in v2_archs['archs']:
                fp.write('source "' + (Path(arch['path']) / 'Kconfig').as_posix() + '"\n')

    def parse_kconfig(self, filename="Kconfig", hwm=None):
        """
        Returns a kconfiglib.Kconfig object for the Kconfig files. We reuse
        this object for all tests to avoid having to reparse for each test.
        """
        # Put the Kconfiglib path first to make sure no local Kconfiglib version is
        # used
        kconfig_path = os.path.join(utils.ZEPHYR_BASE, "scripts", "kconfig")
        if not os.path.exists(kconfig_path):
            self.error(kconfig_path + " not found")

        kconfiglib_dir = tempfile.mkdtemp(prefix="kconfiglib_")

        sys.path.insert(0, kconfig_path)
        # Import globally so that e.g. kconfiglib.Symbol can be referenced in
        # tests
        global kconfiglib
        import kconfiglib

        # Look up Kconfig files relative to ZEPHYR_BASE
        # srctree debe ser ZEPHYR_BASE para que source "Kconfig.zephyr" funcione
        # Pasaremos la ruta completa al Kconfig de la aplicación como filename
        os.environ["srctree"] = str(utils.ZEPHYR_BASE)  # noqa: SIM112
        os.environ["ZEPHYR_BASE"] = str(utils.ZEPHYR_BASE)

        # Parse the entire Kconfig tree, to make sure we see all symbols
        os.environ["SOC_DIR"] = "soc/"
        os.environ["ARCH_DIR"] = "arch/"
        os.environ["BOARD"] = "boards"
        os.environ["ARCH"] = "*"
        os.environ["KCONFIG_BINARY_DIR"] = kconfiglib_dir
        os.environ['DEVICETREE_CONF'] = "dummy"
        os.environ['TOOLCHAIN_HAS_NEWLIB'] = "y"

        # Older name for DEVICETREE_CONF, for compatibility with older Zephyr
        # versions that don't have the renaming
        os.environ["GENERATED_DTS_BOARD_CONF"] = "dummy"

        # For multi repo support
        self.get_modules(
            os.path.join(kconfiglib_dir, "Kconfig.modules"), os.path.join(kconfiglib_dir, "settings_file.txt")
        )
        # For Kconfig.dts support
        self.get_kconfig_dts(
            os.path.join(kconfiglib_dir, "Kconfig.dts"), os.path.join(kconfiglib_dir, "settings_file.txt")
        )

        # To make compliance work with old hw model and HWMv2 simultaneously.
        kconfiglib_boards_dir = os.path.join(kconfiglib_dir, 'boards')
        os.makedirs(kconfiglib_boards_dir, exist_ok=True)
        os.makedirs(os.path.join(kconfiglib_dir, 'soc'), exist_ok=True)
        os.makedirs(os.path.join(kconfiglib_dir, 'arch'), exist_ok=True)

        os.environ["BOARD_DIR"] = kconfiglib_boards_dir
        self.get_v2_model(kconfiglib_dir)

        # Tells Kconfiglib to generate warnings for all references to undefined
        # symbols within Kconfig files
        os.environ["KCONFIG_WARN_UNDEF"] = "y"

        try:
            # Note this will both print warnings to stderr _and_ return
            # them: so some warnings might get printed
            # twice. "warn_to_stderr=False" could unfortunately cause
            # some (other) warnings to never be printed.
            return kconfiglib.Kconfig(filename=filename)
        except kconfiglib.KconfigError as e:
            self.failure(str(e))
            raise EndTest from e
        finally:
            # Clean up the temporary directory
            shutil.rmtree(kconfiglib_dir)

    def get_logging_syms(self, kconf):
        # Returns a set() with the names of the Kconfig symbols generated with
        # logging template in samples/tests folders. The Kconfig symbols doesn't
        # include `CONFIG_` and for each module declared there is one symbol
        # per suffix created.

        suffixes = [
            "_LOG_LEVEL",
            "_LOG_LEVEL_DBG",
            "_LOG_LEVEL_ERR",
            "_LOG_LEVEL_INF",
            "_LOG_LEVEL_WRN",
            "_LOG_LEVEL_OFF",
            "_LOG_LEVEL_INHERIT",
            "_LOG_LEVEL_DEFAULT",
        ]

        # Warning: Needs to work with both --perl-regexp and the 're' module.
        regex = r"^\s*(?:module\s*=\s*)([A-Z0-9_]+)\s*(?:#|$)"

        # Grep samples/ and tests/ for symbol definitions
        grep_stdout = utils.git(
            "grep", "-I", "-h", "--perl-regexp", regex, "--", ":samples", ":tests", cwd=utils.ZEPHYR_BASE
        )

        names = re.findall(regex, grep_stdout, re.MULTILINE)

        kconf_syms = []
        for name in names:
            for suffix in suffixes:
                kconf_syms.append(f"{name}{suffix}")

        return set(kconf_syms)

    def get_defined_syms(self, kconf):
        # Returns a set() with the names of all defined Kconfig symbols (with no
        # 'CONFIG_' prefix). This is complicated by samples and tests defining
        # their own Kconfig trees. For those, just grep for 'config FOO' to find
        # definitions. Doing it "properly" with Kconfiglib is still useful for
        # the main tree, because some symbols are defined using preprocessor
        # macros.

        # Warning: Needs to work with both --perl-regexp and the 're' module.
        # (?:...) is a non-capturing group.
        regex = r"^\s*(?:menu)?config\s*([A-Z0-9_]+)\s*(?:#|$)"

        # Grep samples/ and tests/ for symbol definitions
        grep_stdout = utils.git(
            "grep", "-I", "-h", "--perl-regexp", regex, "--", ":samples", ":tests", cwd=utils.ZEPHYR_BASE
        )

        # Generate combined list of configs and choices from the main Kconfig tree.
        kconf_syms = kconf.unique_defined_syms + kconf.unique_choices

        # Symbols from the main Kconfig tree + grepped definitions from samples
        # and tests
        return set([sym.name for sym in kconf_syms] + re.findall(regex, grep_stdout, re.MULTILINE)).union(
            self.get_logging_syms(kconf)
        )

    def check_top_menu_not_too_long(self, kconf):
        """
        Checks that there aren't too many items in the top-level menu (which
        might be a sign that stuff accidentally got added there)
        """
        max_top_items = 50

        n_top_items = 0
        node = kconf.top_node.list
        while node:
            # Only count items with prompts. Other items will never be
            # shown in the menuconfig (outside show-all mode).
            if node.prompt:
                n_top_items += 1
            node = node.next

        if n_top_items > max_top_items:
            self.failure(f"""
Expected no more than {max_top_items} potentially visible items (items with
prompts) in the top-level Kconfig menu, found {n_top_items} items. If you're
deliberately adding new entries, then bump the 'max_top_items' variable in
{__file__}.""")

    def check_no_redefined_in_defconfig(self, kconf):
        # Checks that no symbols are (re)defined in defconfigs.

        for node in kconf.node_iter():
            # 'kconfiglib' is global
            # pylint: disable=undefined-variable
            if "defconfig" in node.filename and (node.prompt or node.help):
                name = node.item.name if node.item not in (kconfiglib.MENU, kconfiglib.COMMENT) else str(node)
                self.failure(f"""
Kconfig node '{name}' found with prompt or help in {node.filename}.
Options must not be defined in defconfig files.
""")
                continue

    def check_no_enable_in_boolean_prompt(self, kconf):
        # Checks that boolean's prompt does not start with "Enable...".

        for node in kconf.node_iter():
            # skip Kconfig nodes not in-tree (will present an absolute path)
            if os.path.isabs(node.filename):
                continue

            # 'kconfiglib' is global
            # pylint: disable=undefined-variable

            # only process boolean symbols with a prompt
            if (
                not isinstance(node.item, kconfiglib.Symbol)
                or node.item.type != kconfiglib.BOOL
                or not node.prompt
                or not node.prompt[0]
            ):
                continue

            if re.match(r"^[Ee]nable.*", node.prompt[0]):
                self.failure(f"""
Boolean option '{node.item.name}' prompt must not start with 'Enable...'. Please
check Kconfig guidelines.
""")
                continue

    def check_no_pointless_menuconfigs(self, kconf):
        # Checks that there are no pointless 'menuconfig' symbols without
        # children in the Kconfig files

        bad_mconfs = []
        for node in kconf.node_iter():
            # 'kconfiglib' is global
            # pylint: disable=undefined-variable

            # Avoid flagging empty regular menus and choices, in case people do
            # something with 'osource' (could happen for 'menuconfig' symbols
            # too, though it's less likely)
            if node.is_menuconfig and not node.list and isinstance(node.item, kconfiglib.Symbol):
                bad_mconfs.append(node)

        if bad_mconfs:
            self.failure(
                """\
Found pointless 'menuconfig' symbols without children. Use regular 'config'
symbols instead. See
https://docs.zephyrproject.org/latest/build/kconfig/tips.html#menuconfig-symbols.

"""
                + "\n".join(f"{node.item.name:35} {node.filename}:{node.linenr}" for node in bad_mconfs)
            )

    def check_no_undef_within_kconfig(self, kconf):
        """
        Checks that there are no references to undefined Kconfig symbols within
        the Kconfig files
        """
        undef_ref_warnings = "\n\n\n".join(warning for warning in kconf.warnings if "undefined symbol" in warning)

        if undef_ref_warnings:
            self.failure(f"Undefined Kconfig symbols:\n\n {undef_ref_warnings}")

    def check_soc_name_sync(self, kconf):
        # Import Zephyr scripts dynamically
        zephyr_scripts_path = str(utils.ZEPHYR_BASE / "scripts")
        if zephyr_scripts_path not in sys.path:
            sys.path.insert(0, zephyr_scripts_path)
        import list_hardware

        root_args = argparse.Namespace(**{'soc_roots': [Path(utils.ZEPHYR_BASE)]})
        v2_systems = list_hardware.find_v2_systems(root_args)

        soc_names = {soc.name for soc in v2_systems.get_socs()}

        soc_kconfig_names = set()
        for node in kconf.node_iter():
            # 'kconfiglib' is global
            # pylint: disable=undefined-variable
            if isinstance(node.item, kconfiglib.Symbol) and node.item.name == "SOC":
                n = node.item
                for d in n.defaults:
                    soc_kconfig_names.add(d[0].name)

        soc_name_warnings = []
        for name in soc_names:
            if name not in soc_kconfig_names:
                soc_name_warnings.append(f"soc name: {name} not found in CONFIG_SOC defaults.")

        if soc_name_warnings:
            soc_name_warning_str = '\n'.join(soc_name_warnings)
            self.failure(f'''
Missing SoC names or CONFIG_SOC vs soc.yml out of sync:

{soc_name_warning_str}
''')

    def check_no_undef_outside_kconfig(self, kconf):
        """
        Checks that there are no references to undefined Kconfig symbols
        outside Kconfig files (any CONFIG_FOO where no FOO symbol exists)
        """
        defined_syms = self.get_defined_syms(kconf)

        # Maps each undefined symbol to a list <filename>:<linenr> strings
        undef_to_locs = collections.defaultdict(list)

        # Warning: Needs to work with both --perl-regexp and the 're' module
        regex = r"\bCONFIG_[A-Z0-9_]+\b(?!\s*##|[$@{*])"

        # Construct search arguments based on current_app_dir
        if hasattr(self, 'current_app_dir') and self.current_app_dir is not None:
            # Mode: specific app directory
            search_path = self.current_app_dir
            logging.info(f"Searching CONFIG_* references in: {search_path}/")
            search_args = [search_path]
        else:
            # Mode: entire repository (excluding deps/)
            logging.info("Searching CONFIG_* references in: entire repository (excluding deps/)")
            search_args = [".", ":!deps/"]

        # Skip doc/releases and doc/security/vulnerabilities.rst, which often
        # reference removed symbols
        grep_stdout = utils.git(
            "grep",
            "--line-number",
            "-I",
            "--null",
            "--perl-regexp",
            regex,
            "--",
            *search_args,
            ":!/doc/releases",
            ":!/doc/security/vulnerabilities.rst",
            cwd=Path(utils.GIT_TOP),
        )

        # splitlines() supports various line terminators
        for grep_line in grep_stdout.splitlines():
            path, lineno, line = grep_line.split("\0")

            # Extract symbol references (might be more than one) within the
            # line
            for sym_name in re.findall(regex, line):
                sym_name = sym_name[7:]  # Strip CONFIG_
                if (
                    sym_name not in defined_syms
                    and sym_name not in self.UNDEF_KCONFIG_ALLOWLIST
                    and not (sym_name.endswith("_MODULE") and sym_name[:-7] in defined_syms)
                ):
                    undef_to_locs[sym_name].append(f"{path}:{lineno}")

        if not undef_to_locs:
            return

        # String that describes all referenced but undefined Kconfig symbols,
        # in alphabetical order, along with the locations where they're
        # referenced. Example:
        #
        #   CONFIG_ALSO_MISSING    arch/xtensa/core/fatal.c:273
        #   CONFIG_MISSING         arch/xtensa/core/fatal.c:264, subsys/fb/cfb.c:20
        undef_desc = "\n".join(
            f"CONFIG_{sym_name:35} {', '.join(locs)}" for sym_name, locs in sorted(undef_to_locs.items())
        )

        self.failure(f"""
Found references to undefined Kconfig symbols. If any of these are false
positives, then add them to UNDEF_KCONFIG_ALLOWLIST in {__file__}.

If the reference is for a comment like /* CONFIG_FOO_* */ (or
/* CONFIG_FOO_*_... */), then please use exactly that form (with the '*'). The
CI check knows not to flag it.

More generally, a reference followed by $, @, {{, *, or ## will never be
flagged.

{undef_desc}""")

    # Many of these are symbols used as examples. Note that the list is sorted
    # alphabetically, and skips the CONFIG_ prefix.
    UNDEF_KCONFIG_ALLOWLIST = {
        "ALSO_MISSING",
        "APP_LINK_WITH_",
        "APP_LOG_LEVEL",  # Application log level is not detected correctly as
        # the option is defined using a template, so it can't
        # be grepped
        "APP_LOG_LEVEL_DBG",
        "ARMCLANG_STD_LIBC",  # The ARMCLANG_STD_LIBC is defined in the
        # toolchain Kconfig which is sourced based on
        # Zephyr toolchain variant and therefore not
        # visible to compliance.
        "BOARD_",  # Used as regex in scripts/utils/board_v1_to_v2.py
        "BOOT_ENCRYPTION_KEY_FILE",  # Used in sysbuild
        "BOOT_ENCRYPT_IMAGE",  # Used in sysbuild
        "BINDESC_",  # Used in documentation as a prefix
        "BOOT_UPGRADE_ONLY",  # Used in example adjusting MCUboot config, but
        # symbol is defined in MCUboot itself.
        "BOOT_SERIAL_BOOT_MODE",  # Used in (sysbuild-based) test/
        # documentation
        "BOOT_SERIAL_CDC_ACM",  # Used in (sysbuild-based) test
        "BOOT_SERIAL_ENTRANCE_GPIO",  # Used in (sysbuild-based) test
        "BOOT_SERIAL_IMG_GRP_HASH",  # Used in documentation
        "BOOT_SHARE_DATA",  # Used in Kconfig text
        "BOOT_SHARE_DATA_BOOTINFO",  # Used in (sysbuild-based) test
        "BOOT_SHARE_BACKEND_RETENTION",  # Used in Kconfig text
        "BOOT_SIGNATURE_KEY_FILE",  # MCUboot setting used by sysbuild
        "BOOT_SIGNATURE_TYPE_ECDSA_P256",  # MCUboot setting used by sysbuild
        "BOOT_SIGNATURE_TYPE_ED25519",  # MCUboot setting used by sysbuild
        "BOOT_SIGNATURE_TYPE_NONE",  # MCUboot setting used by sysbuild
        "BOOT_SIGNATURE_TYPE_RSA",  # MCUboot setting used by sysbuild
        "BOOT_VALIDATE_SLOT0",  # Used in (sysbuild-based) test
        "BOOT_WATCHDOG_FEED",  # Used in (sysbuild-based) test
        "CDC_ACM_PORT_NAME_",
        "CHRE",  # Optional module
        "CHRE_LOG_LEVEL_DBG",  # Optional module
        "CLOCK_STM32_SYSCLK_SRC_",
        "CMU",
        "COMPILER_RT_RTLIB",
        "BT_6LOWPAN",  # Defined in Linux, mentioned in docs
        "CMD_CACHE",  # Defined in U-Boot, mentioned in docs
        "CRC",  # Used in TI CC13x2 / CC26x2 SDK comment
        "DEEP_SLEEP",  # #defined by RV32M1 in ext/
        "DESCRIPTION",
        "ERR",
        "ESP_DIF_LIBRARY",  # Referenced in CMake comment
        "EXPERIMENTAL",
        "FFT",  # Used as an example in cmake/extensions.cmake
        "FLAG",  # Used as an example
        "FOO",
        "FOO_LOG_LEVEL",
        "FOO_SETTING_1",
        "FOO_SETTING_2",
        "HEAP_MEM_POOL_ADD_SIZE_",  # Used as an option matching prefix
        "LSM6DSO_INT_PIN",
        "LIBGCC_RTLIB",
        "LLVM_USE_LD",  # Both LLVM_USE_* are in cmake/toolchain/llvm/Kconfig
        "LLVM_USE_LLD",  # which are only included if LLVM is selected but
        # not other toolchains. Compliance check would complain,
        # for example, if you are using GCC.
        "MCUBOOT_LOG_LEVEL_WRN",  # Used in example adjusting MCUboot
        # config,
        "MCUBOOT_LOG_LEVEL_INF",
        "MCUBOOT_DOWNGRADE_PREVENTION",  # but symbols are defined in MCUboot
        # itself.
        "MCUBOOT_ACTION_HOOKS",  # Used in (sysbuild-based) test
        "MCUBOOT_CLEANUP_ARM_CORE",  # Used in (sysbuild-based) test
        "MCUBOOT_SERIAL",  # Used in (sysbuild-based) test/
        # documentation
        "MCUMGR_GRP_EXAMPLE_OTHER_HOOK",  # Used in documentation
        "MISSING",
        "MODULES",
        "MYFEATURE",
        "MY_DRIVER_0",
        "NORMAL_SLEEP",  # #defined by RV32M1 in ext/
        "OPT",
        "OPT_0",
        "PEDO_THS_MIN",
        "PSA_H",  # This is used in config-psa.h as guard for the header file
        "REG1",
        "REG2",
        "RIMAGE_SIGNING_SCHEMA",  # Optional module
        "LOG_BACKEND_MOCK_OUTPUT_DEFAULT",  # Referenced in tests/subsys/logging/log_syst
        "LOG_BACKEND_MOCK_OUTPUT_SYST",  # Referenced in testcase.yaml of log_syst test
        "SEL",
        "SHIFT",
        "SOC_SERIES_",  # Used as regex in scripts/utils/board_v1_to_v2.py
        "SOC_WATCH",  # Issue 13749
        "SOME_BOOL",
        "SOME_INT",
        "SOME_OTHER_BOOL",
        "SOME_STRING",
        "SRAM2",  # Referenced in a comment in samples/application_development
        "STACK_SIZE",  # Used as an example in the Kconfig docs
        "STD_CPP",  # Referenced in CMake comment
        "TEST1",
        "TOOLCHAIN_ARCMWDT_SUPPORTS_THREAD_LOCAL_STORAGE",  # The symbol is defined in the toolchain
        # Kconfig which is sourced based on Zephyr
        # toolchain variant and therefore not visible
        # to compliance.
        "TYPE_BOOLEAN",
        "USB_CONSOLE",
        "USE_STDC_",
        "WHATEVER",
        "EXTRA_FIRMWARE_DIR",  # Linux, in boards/xtensa/intel_adsp_cavs25/doc
        "HUGETLBFS",  # Linux, in boards/xtensa/intel_adsp_cavs25/doc
        "MODVERSIONS",  # Linux, in boards/xtensa/intel_adsp_cavs25/doc
        "SECURITY_LOADPIN",  # Linux, in boards/xtensa/intel_adsp_cavs25/doc
        "ZEPHYR_TRY_MASS_ERASE",  # MCUBoot setting described in sysbuild
        # documentation
        "ZTEST_FAIL_TEST_",  # regex in tests/ztest/fail/CMakeLists.txt
        "SUIT_MPI_GENERATE",  # Used by nRF runners to program provisioning data, based on build configuration
        "SUIT_MPI_APP_AREA_PATH",  # Used by nRF runners to program provisioning data, based on build configuration
        "SUIT_MPI_RAD_AREA_PATH",  # Used by nRF runners to program provisioning data, based on build configuration
    }
