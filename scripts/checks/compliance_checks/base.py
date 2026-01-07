#!/usr/bin/env python3

"""
Base classes for compliance checks.
"""

from junitparser import Error, Failure, Skipped, TestCase


class FmtdFailure(Failure):
    def __init__(
        self,
        severity,
        title,
        file,
        line=None,
        col=None,
        desc="",
        end_line=None,
        end_col=None,
    ):
        self.severity = severity
        self.title = title
        self.file = file
        self.line = line
        self.col = col
        self.end_line = end_line
        self.end_col = end_col
        self.desc = desc
        description = f":{desc}" if desc else ""
        msg_body = desc or title

        txt = (
            f"\n{title}{description}\nFile:{file}"
            + (f"\nLine:{line}" if line else "")
            + (f"\nColumn:{col}" if col else "")
            + (f"\nEndLine:{end_line}" if end_line else "")
            + (f"\nEndColumn:{end_col}" if end_col else "")
        )
        msg = f"{file}" + (f":{line}" if line else "") + f" {msg_body}"
        typ = severity.lower()

        super().__init__(msg, typ)

        self.text = txt


class ComplianceTest:
    """
    Base class for tests. Inheriting classes should have a run() method and set
    these class variables:

    name:
      Test name

    doc:
      Link to documentation related to what's being tested

    path_hint:
      The path the test runs itself in. By default it uses the magic string
      "<git-top>" which refers to the top-level repository directory.

      This avoids running 'git' to find the top-level directory before main()
      runs (class variable assignments run when the 'class ...' statement
      runs). That avoids swallowing errors, because main() reports them to
      GitHub.

      Subclasses may override the default with a specific path or one of the
      magic strings below:
      - "<zephyr-base>" can be used to refer to the environment variable
        ZEPHYR_BASE or, when missing, the calculated base of the zephyr tree.
    """

    path_hint = "<git-top>"

    def __init__(self):
        self.case = TestCase(type(self).name, "Guidelines")
        # This is necessary because Failure can be subclassed, but since it is
        # always restored form the element tree, the subclass is lost upon
        # restoring
        self.fmtd_failures = []

    def _result(self, res, text):
        res.text = text.rstrip()
        self.case.result += [res]

    def error(self, text, msg=None, type_="error"):
        """
        Signals a problem with running the test, with message 'msg'.

        Raises an exception internally, so you do not need to put a 'return'
        after error().
        """
        err = Error(msg or f"{type(self).name} error", type_)
        self._result(err, text)

        raise EndTest

    def skip(self, text, msg=None, type_="skip"):
        """
        Signals that the test should be skipped, with message 'msg'.

        Raises an exception internally, so you do not need to put a 'return'
        after skip().
        """
        skpd = Skipped(msg or f"{type(self).name} skipped", type_)
        self._result(skpd, text)

        raise EndTest

    def failure(self, text, msg=None, type_="failure"):
        """
        Signals that the test failed, with message 'msg'. Can be called many
        times within the same test to report multiple failures.
        """
        fail = Failure(msg or f"{type(self).name} issues", type_)
        self._result(fail, text)

    def fmtd_failure(
        self,
        severity,
        title,
        file,
        line=None,
        col=None,
        desc="",
        end_line=None,
        end_col=None,
    ):
        """
        Signals that the test failed, and store the information in a formatted
        standardized manner. Can be called many times within the same test to
        report multiple failures.
        """
        fail = FmtdFailure(severity, title, file, line, col, desc, end_line, end_col)
        self._result(fail, fail.text)
        self.fmtd_failures.append(fail)


class EndTest(Exception):
    """
    Raised by ComplianceTest.error()/skip() to end the test.

    Tests can raise EndTest themselves to immediately end the test, e.g. from
    within a nested function call.
    """
