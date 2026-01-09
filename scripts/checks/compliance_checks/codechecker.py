#!/usr/bin/env python3

"""
CodeChecker compliance check.
"""

import logging
import re
import shutil
import subprocess
from pathlib import Path

from . import utils
from .base import ComplianceTest


class CodeChecker(ComplianceTest):
    name = "CodeChecker"
    doc = ""
    path_hint = "<git-top>"

    STATUS_OK = "ok"
    STATUS_FAIL = "fail"
    STATUS_ERROR = "error"

    _ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
    _CC_ISSUE_RE = re.compile(
        r"^\[(?P<sev>[A-Z]+)\]\s+"
        r"(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+):\s+"
        r"(?P<msg>.+?)\s+\[(?P<checker>[^\]]+)\]\s*$"
    )

    def _sanitize_for_xml(self, s: str) -> str:
        if not s:
            return ""
        s = self._ANSI_RE.sub("", s)
        out = []
        for ch in s:
            o = ord(ch)
            if ch in ("\t", "\n", "\r") or 0x20 <= o <= 0xD7FF or 0xE000 <= o <= 0xFFFD or 0x10000 <= o <= 0x10FFFF:
                out.append(ch)
        return "".join(out)

    def _map_cc_severity(self, sev: str) -> str:
        s = (sev or "").strip().upper()
        if s in ("HIGH", "CRITICAL", "SEVERE"):
            return "error"
        if s in ("MEDIUM",):
            return "warning"
        # LOW / STYLE / anything else
        return "notice"

    def _extract_cc_issues(self, out: str) -> list[dict]:
        issues: list[dict] = []
        if not out:
            return issues

        out = self._ANSI_RE.sub("", out)

        lines = out.splitlines()
        i = 0
        while i < len(lines):
            m = self._CC_ISSUE_RE.match(lines[i].strip())
            if not m:
                i += 1
                continue

            sev = self._map_cc_severity(m.group("sev"))
            fpath = m.group("file").strip()
            line = int(m.group("line"))
            col = int(m.group("col"))
            msg = m.group("msg").rstrip()
            checker = m.group("checker").strip()

            ctx = []
            j = i + 1
            while j < len(lines) and len(ctx) < 2:
                nxt = lines[j].rstrip("\n")
                if not nxt.strip():
                    break
                if self._CC_ISSUE_RE.match(nxt.strip()):
                    break
                if nxt.startswith("----====") or nxt.startswith("[INFO"):
                    break
                ctx.append(nxt)
                j += 1

            if ctx:
                msg = msg + "\r\n" + "\r\n".join(ctx)

            try:
                p = Path(fpath)
                if not p.is_absolute():
                    p = utils.GIT_TOP / p
                fpath = p.relative_to(utils.GIT_TOP).as_posix()
                if fpath.startswith("./"):
                    fpath = fpath[2:]
            except Exception:
                pass

            issues.append(
                {
                    "severity": sev,
                    "file": fpath,
                    "line": line,
                    "col": col,
                    "checker": checker,
                    "msg": msg,
                }
            )

            i = j

        return issues

    def _board_for_app(self, app: Path) -> str:
        if "secondary_node" in app.parts:
            return "adafruit_feather_m0_lora"
        return "qemu_cortex_m3"

    def _analyze_app(self, app: Path, only_files: list[str] | None = None) -> tuple[str, str]:
        board = self._board_for_app(app)

        rel = app.relative_to(utils.GIT_TOP)
        build_dir = utils.GIT_TOP / "buildsca" / str(rel) / board

        if build_dir.exists():
            shutil.rmtree(build_dir)
        build_dir.mkdir(parents=True, exist_ok=True)

        # 1) west build
        west_cmd = [
            "west",
            "build",
            "-b",
            board,
            "-d",
            str(build_dir),
            str(app),
            "-p",
            "always",
            "--cmake-only",
            "--",
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
        ]
        r = subprocess.run(
            west_cmd,
            cwd=utils.GIT_TOP,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
        )
        if r.returncode != 0:
            return (self.STATUS_ERROR, f"west build failed for {rel}\n{r.stdout}")

        gen_cmd = ["west", "build", "-d", str(build_dir), "-t", "zephyr_generated_headers"]
        r2 = subprocess.run(
            gen_cmd,
            cwd=utils.GIT_TOP,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
        )
        if r2.returncode != 0:
            pass

        compile_db = build_dir / "compile_commands.json"
        if not compile_db.is_file():
            return (self.STATUS_ERROR, f"Missing compile_commands.json for {rel}")

        # 2) CodeChecker analyze
        reports_dir = build_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        app_rel = rel.as_posix()

        skip_file = utils.GIT_TOP / ".codechecker.skip"

        analyze_cmd = [
            "CodeChecker",
            "analyze",
            str(compile_db),
            "-o",
            str(reports_dir),
            "-q",
            "--analyzers",
            "clangsa",
            "clang-tidy",
            "cppcheck",
            "--analyzer-config",
            f"clang-tidy:HeaderFilterRegex=.*/{app_rel}/.*",
        ]
        if skip_file.is_file():
            analyze_cmd += ["-i", str(skip_file)]

        # Zephyr logging macros trigger reserved identifier diagnostics
        analyze_cmd += [
            "-d",
            "clang-diagnostic-reserved-identifier",
            "-d",
            "clang-diagnostic-reserved-macro-identifier",
        ]

        r = subprocess.run(
            analyze_cmd,
            cwd=utils.GIT_TOP,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
        )
        if r.returncode != 0:
            return (self.STATUS_ERROR, f"CodeChecker analyze error for {rel}\n{r.stdout}")

        # 3) CodeChecker parse
        parse_cmd = [
            "CodeChecker",
            "parse",
            str(reports_dir),
            "--print-steps",
            "--trim-path-prefix",
            str(utils.GIT_TOP),
        ]

        if skip_file.is_file():
            parse_cmd += ["-i", str(skip_file)]

        r = subprocess.run(
            parse_cmd,
            cwd=utils.GIT_TOP,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
        )

        if r.returncode == 0:
            return (self.STATUS_OK, "")

        if r.returncode == 2:
            return (self.STATUS_FAIL, f"CodeChecker reports for {rel}\n{r.stdout}")

        return (self.STATUS_ERROR, f"CodeChecker parse error for {rel}\n{r.stdout}")

    def _normalize_repo_rel(self, p: str) -> str:
        try:
            pp = Path(p)
            if not pp.is_absolute():
                pp = utils.GIT_TOP / pp
            pp = pp.resolve()
            return pp.relative_to(utils.GIT_TOP.resolve()).as_posix()
        except Exception:
            return str(p).replace("\\", "/")

    def _finalize_results(self, results: list[tuple[Path, str, str, list[str] | None]]) -> None:
        errors = []
        fails = []

        for app, st, out, only_files in results:
            if st == self.STATUS_ERROR:
                errors.append((app, out))
            elif st == self.STATUS_FAIL:
                fails.append((app, out, only_files))

        if errors:
            msg = ["CodeChecker errors:"]
            for app, out in errors:
                msg.append(f"\n=== {app.relative_to(utils.GIT_TOP)} ===\n{out}")
            self.error(self._sanitize_for_xml("\n".join(msg)))
            return

        if fails:
            any_reported = False
            parsing_failed = []

            for app, out, only_files in fails:
                raw_issues = self._extract_cc_issues(out)

                if not raw_issues:
                    parsing_failed.append((app, out))
                    continue

                issues = raw_issues

                app_rel = app.relative_to(utils.GIT_TOP).as_posix()

                if only_files:
                    keep_set = set(self._normalize_repo_rel(f) for f in only_files)
                    issues = [it for it in issues if it.get("file") in keep_set]
                else:
                    keep_prefixes = (
                        f"{app_rel}/src/",
                        f"{app_rel}/include/",
                    )
                    issues = [it for it in issues if any(it.get("file", "").startswith(p) for p in keep_prefixes)]

                if not issues:
                    continue
                any_reported = True
                for it in issues:
                    self.fmtd_failure(
                        it["severity"],
                        it["checker"],
                        it["file"],
                        it["line"],
                        it["col"],
                        self._sanitize_for_xml(it["msg"]),
                    )

            if any_reported:
                return

            if parsing_failed:
                msg = ["CodeChecker reports (could not parse issues):"]
                for app, out in parsing_failed:
                    msg.append(f"\n=== {app.relative_to(utils.GIT_TOP)} ===\n{out}")
                self.failure(self._sanitize_for_xml("\n".join(msg)))
                return

            return

        # OK
        return

    def run(self, mode="default"):
        log = logging.getLogger(self.name)

        if mode == "default":
            default_apps = [
                utils.GIT_TOP / "main_node",
                utils.GIT_TOP / "secondary_node",
            ]

            apps = []
            for p in default_apps:
                app = utils.find_zephyr_app_root(p)
                if app is None:
                    log.warning("Default app root not found (no prj.conf up-tree): %s", p)
                    continue
                apps.append(app)

            if not apps:
                self.skip("No default Zephyr apps found (main_node/secondary_node)")
                return

            unique_apps = sorted(set(apps))

            log.info("Apps (%d):", len(unique_apps))
            for a in unique_apps:
                log.info("  - %s", a.relative_to(utils.GIT_TOP))

            results = []
            for app in unique_apps:
                log.info("Analyzing app: %s", app.relative_to(utils.GIT_TOP))
                st, out = self._analyze_app(app)
                results.append((app, st, out, None))

            self._finalize_results(results)
            return

        if mode == "path":
            exts = ('.c', '.h', '.cpp', '.hpp', '.cc', '.S', '.s', '.inc')

            full_apps = set()
            for raw in getattr(utils, "TARGET_PATHS", []) or []:
                p = Path(raw)
                if not p.is_absolute():
                    p = utils.GIT_TOP / p
                if p.exists() and p.is_dir():
                    app = utils.find_zephyr_app_root(p)
                    if app is not None:
                        full_apps.add(app)

            files = []
            for f in utils.files_from_paths():
                if f.endswith(exts):
                    files.append(f)

            if not files:
                self.skip("No files to list in path mode")
                return

            log.debug("Files (%d):\n%s", len(files), "\n".join(files))

            apps = {}
            for f in files:
                app = utils.find_zephyr_app_root(f)
                if app is None:
                    log.warning("No app (no prj.conf up-tree): %s", f)
                    continue
                apps.setdefault(app, []).append(f)

            for app in full_apps:
                apps[app] = None

            log.info("Apps (%d):", len(apps))
            for app in sorted(apps.keys()):
                log.info("  - %s", app.relative_to(utils.GIT_TOP))

            if not apps:
                self.skip("No Zephyr apps found for listed files")
                return

            results = []
            for app in sorted(apps.keys()):
                log.info("Analyzing app: %s", app.relative_to(utils.GIT_TOP))
                only_files = apps[app]
                if only_files is None:
                    st, out = self._analyze_app(app)
                else:
                    st, out = self._analyze_app(app, only_files)

                results.append((app, st, out, only_files))

            self._finalize_results(results)
            return

        if mode != "diff":
            self.error(f"Unknown mode: {mode}")
            return

        # DIFF MODE: Use git diff
        files = utils.get_files(filter="ACMRTUXB")
        if not files:
            self.skip("CodeChecker: no files to list in diff mode")
            return

        ANALYZABLE_EXTS = ('.c', '.h', '.cpp', '.hpp', '.cc', '.S', '.s', '.inc')
        files = [f for f in files if f.endswith(ANALYZABLE_EXTS)]
        files = [f for f in files if (utils.GIT_TOP / f).is_file()]

        if not files:
            self.skip("No analyzable files after filtering in diff mode")
            return

        log.debug("Files (%d):\n%s", len(files), "\n".join(files))

        apps = {}
        for f in files:
            app = utils.find_zephyr_app_root(f)
            if app is None:
                log.warning("No app (no prj.conf up-tree): %s", f)
                continue
            apps.setdefault(app, []).append(f)

        log.info("Apps (%d):", len(apps))
        for app in sorted(apps.keys()):
            log.info("  - %s", app.relative_to(utils.GIT_TOP))

        if not apps:
            self.skip("No Zephyr apps found for listed files")
            return

        results = []
        for app in sorted(apps.keys()):
            log.info("Analyzing app: %s", app.relative_to(utils.GIT_TOP))
            st, out = self._analyze_app(app, apps[app])
            results.append((app, st, out, apps[app]))

        self._finalize_results(results)

        return
