#!/usr/bin/env python3
"""Fail if any workflow job can run on anything but a GitHub-hosted runner.

Owner directive 18: "Public repos use GitHub-hosted runners only, never
self-hosted or local; add a CI check that fails on any `runs-on` value other
than a GitHub-hosted runner, proven by breaking it on purpose."

Why this is a gate and not a convention: a self-hosted runner on a public
repo executes workflow code from any fork's pull request on hardware the
owner controls. It is also the most direct way to reintroduce a dependency
on one machine, which directive 8 calls SACRED ("there must NOT be ANY
dependence on or tie-in to a local environment").

The check is FAIL-CLOSED. A `runs-on` value it cannot statically resolve to
a known GitHub-hosted label is an error, never a skip: `${{ env.RUNNER }}`
resolves at run time to whatever the variable holds, which may be a
self-hosted label, so "unknown" and "not allowed" have to mean the same
thing here.

Python 3.10+ standard library only (directive 11), so there is no PyYAML.
`_parse_block` below is a deliberately small YAML subset reader -- block
mappings, block sequences, inline flow sequences, and opaque block scalars
-- sufficient for `jobs.<id>.runs-on`, `jobs.<id>.uses` and
`jobs.<id>.strategy.matrix.<key>`, and nothing more. Anything it does not
understand becomes an error rather than a silent pass.

Known limitation -- this gate is self-referential, and that bounds what it
can promise. For a pull request from a FORK, GitHub runs the job and step
definitions from the base ref against the fork's file content, so a fork
cannot strip this step out; the check still runs and still reads the merged
tree. For a branch in THIS repo, or a direct push, the contributor's own
version of the workflow runs, so a commit may delete this step and that same
commit's CI will simply not execute it. No script can close that: it is
closed by the ruleset (required reviews plus required status checks), not
here. Do not read a green run as proof that nobody could have removed it.

Usage:
    python scripts/lws_check_hosted_runner.py
    python scripts/lws_check_hosted_runner.py --workflows-dir path/to/workflows

Exit 0 when every job is hosted, 1 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Union

REPO_ROOT = Path(__file__).resolve().parent.parent

# Curated allow-list of GitHub-hosted runner labels, held as an explicit set
# rather than a regex on purpose: a regex silently decides the fate of labels
# nobody checked. `windows-11-arm` is exactly that trap -- a real, generally
# available hosted Arm64 runner that a `windows-\d{4}` pattern rejects.
#
# Deliberately exact. A label that merely looks hosted (`ubuntu-latest-8core`)
# is a larger-runner name an owner configures, indistinguishable from a
# self-hosted label, so it fails until someone adds it here on purpose. A new
# hosted image (a future `ubuntu-26.04`) also fails until added -- fail-closed
# means the update is deliberate, and this list needs review as GitHub's
# lineup changes.
HOSTED_LABELS = frozenset({
    "ubuntu-latest", "ubuntu-24.04", "ubuntu-22.04", "ubuntu-20.04",
    "ubuntu-24.04-arm", "ubuntu-22.04-arm",
    "windows-latest", "windows-2025", "windows-2022", "windows-2019",
    "windows-11-arm",
    "macos-latest", "macos-15", "macos-14", "macos-13",
    "macos-latest-large", "macos-latest-xlarge",
    "macos-15-large", "macos-14-large", "macos-13-large",
    "macos-15-xlarge", "macos-14-xlarge", "macos-13-xlarge",
})

MATRIX_EXPR_RE = re.compile(r"^\$\{\{\s*matrix\.([A-Za-z0-9_-]+)\s*\}\}$")
ANY_EXPR_RE = re.compile(r"\$\{\{.*\}\}")

Node = Union[str, list, dict]


def is_hosted_label(label: str) -> bool:
    """True only for a label this file recognises as GitHub-hosted."""
    if not isinstance(label, str):
        return False
    return label.strip().lower() in HOSTED_LABELS


# --- the YAML subset --------------------------------------------------------

def _strip_comment(line: str) -> str:
    """Drop a trailing `#` comment, respecting quotes."""
    out = []
    quote = None
    for i, ch in enumerate(line):
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
            continue
        if ch == "#" and (i == 0 or line[i - 1].isspace()):
            break
        out.append(ch)
    return "".join(out).rstrip()


class MultiDocumentError(ValueError):
    """Raised for a workflow file holding more than one YAML document."""


def _significant_lines(text: str) -> list[tuple[int, str]]:
    """(indent, content) for each line that carries structure.

    A second `---` document marker raises: this reader has no concept of
    documents, so two `jobs:` mappings would merge and the later one would
    overwrite the earlier, hiding whatever runners the first one declared.
    Refusing is the only honest answer.
    """
    rows: list[tuple[int, str]] = []
    seen_content = False
    for raw in text.splitlines():
        if raw.lstrip().startswith("#"):
            continue
        stripped = _strip_comment(raw)
        if not stripped.strip():
            continue
        content = stripped.strip()
        if content == "---" or content.startswith("--- "):
            if seen_content or rows:
                raise MultiDocumentError(
                    "multi-document YAML is not supported by this check"
                )
            seen_content = True
            continue
        rows.append((len(stripped) - len(stripped.lstrip()), content))
    return rows


def _flow_sequence(value: str) -> list[str]:
    inner = value[1:-1].strip()
    if not inner:
        return []
    return [item.strip().strip("'\"") for item in inner.split(",")]


def _scalar(value: str) -> str:
    return value.strip().strip("'\"")


def _parse_block(rows: list[tuple[int, str]], start: int, indent: int) -> tuple[Node, int]:
    """Parse the block at `indent` beginning at `rows[start]`.

    Returns the parsed node and the index of the first row after the block.
    """
    if start >= len(rows):
        return {}, start

    # A block sequence. Items may be scalars (`- ubuntu-latest`) or mappings
    # (`- os: self-hosted` with further keys indented beneath) -- strategy
    # matrix `include`/`exclude` entries are the latter, and reading them as
    # scalars is what let a self-hosted `include` entry through unnoticed.
    if rows[start][1] == "-" or rows[start][1].startswith("- "):
        items: list = []
        i = start
        while i < len(rows) and rows[i][0] == indent and (
            rows[i][1] == "-" or rows[i][1].startswith("- ")
        ):
            head = rows[i][1][2:].strip() if rows[i][1].startswith("- ") else ""
            i += 1

            nested_start = i
            while i < len(rows) and rows[i][0] > indent:
                i += 1
            nested = rows[nested_start:i]

            if head and ":" in head and not head.startswith("["):
                key, _, rest = head.partition(":")
                entry: dict = {_scalar(key): _scalar(rest) if rest.strip() else ""}
                if nested:
                    more, _ = _parse_block(nested, 0, nested[0][0])
                    if isinstance(more, dict):
                        entry.update(more)
                items.append(entry)
            elif head:
                items.append(_scalar(head))
            elif nested:
                more, _ = _parse_block(nested, 0, nested[0][0])
                items.append(more)
            else:
                items.append("")
        return items, i

    mapping: dict = {}
    i = start
    while i < len(rows):
        line_indent, content = rows[i]
        if line_indent < indent:
            break
        if line_indent > indent:  # stray deeper line with no owning key
            i += 1
            continue
        if ":" not in content:
            i += 1
            continue

        key, _, rest = content.partition(":")
        key = _scalar(key)
        rest = rest.strip()
        i += 1

        if rest.startswith("|") or rest.startswith(">"):
            # Opaque block scalar: swallow every deeper line untouched.
            while i < len(rows) and rows[i][0] > line_indent:
                i += 1
            mapping[key] = ""
        elif rest.startswith("[") and rest.endswith("]"):
            mapping[key] = _flow_sequence(rest)
        elif rest:
            mapping[key] = _scalar(rest)
        elif i < len(rows) and rows[i][0] > line_indent:
            mapping[key], i = _parse_block(rows, i, rows[i][0])
        else:
            mapping[key] = ""

    return mapping, i


def parse_workflow(text: str) -> dict:
    rows = _significant_lines(text)
    node, _ = _parse_block(rows, 0, rows[0][0] if rows else 0)
    return node if isinstance(node, dict) else {}


# --- the check --------------------------------------------------------------

def _check_labels(labels: list[str], where: str, errors: list[str]) -> None:
    for label in labels:
        if not is_hosted_label(label):
            errors.append(f"{where}: runner label {label!r} is not a GitHub-hosted runner")


def check_job(job_name: str, job: Node, where: str, errors: list[str]) -> None:
    if not isinstance(job, dict):
        errors.append(f"{where}: job {job_name!r} could not be parsed")
        return

    runs_on = job.get("runs-on")

    if runs_on is None or runs_on == "":
        # A job that calls a reusable workflow has `uses:` and no `runs-on`;
        # the called workflow is checked on its own. Anything else is malformed.
        if not job.get("uses"):
            errors.append(f"{where}: job {job_name!r} has no 'runs-on' and no 'uses'")
        return

    if isinstance(runs_on, list):
        _check_labels(runs_on, f"{where} job {job_name!r}", errors)
        return

    if isinstance(runs_on, dict):
        if "group" in runs_on:
            errors.append(
                f"{where}: job {job_name!r} uses runner group "
                f"{runs_on['group']!r} -- runner groups are self-hosted only"
            )
        labels = runs_on.get("labels")
        if isinstance(labels, list):
            _check_labels(labels, f"{where} job {job_name!r}", errors)
        elif isinstance(labels, str) and labels:
            _check_labels([labels], f"{where} job {job_name!r}", errors)
        elif "group" not in runs_on:
            errors.append(f"{where}: job {job_name!r} has an unrecognised 'runs-on' mapping")
        return

    value = str(runs_on).strip()

    matrix_match = MATRIX_EXPR_RE.match(value)
    if matrix_match:
        key = matrix_match.group(1)
        strategy = job.get("strategy")
        matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
        if not isinstance(matrix, dict):
            errors.append(
                f"{where}: job {job_name!r} runs on '{value}' but has no "
                "strategy.matrix this check can resolve"
            )
            return

        values: list = []
        direct = matrix.get(key)
        if isinstance(direct, str) and direct:
            values.append(direct)
        elif isinstance(direct, list):
            values.extend(direct)

        # `include` entries are not decoration: GitHub adds an entry matching
        # no existing combination as an EXTRA job, so an `include` can name a
        # runner the flat matrix list never mentions. `exclude` is ignored on
        # purpose -- ignoring it can only over-report, which is the safe way
        # to be wrong.
        include = matrix.get("include")
        if include is not None:
            if not isinstance(include, list):
                errors.append(
                    f"{where}: job {job_name!r} has a strategy.matrix.include "
                    "this check cannot parse"
                )
                return
            for entry in include:
                if not isinstance(entry, dict):
                    errors.append(
                        f"{where}: job {job_name!r} has a strategy.matrix.include "
                        f"entry this check cannot parse: {entry!r}"
                    )
                    return
                if key in entry:
                    values.append(entry[key])

        if not values:
            errors.append(
                f"{where}: job {job_name!r} runs on '{value}' but "
                f"strategy.matrix.{key} resolves to nothing this check can read"
            )
            return
        _check_labels(values, f"{where} job {job_name!r} (matrix.{key})", errors)
        return

    if ANY_EXPR_RE.search(value):
        errors.append(
            f"{where}: job {job_name!r} runs on expression '{value}', which cannot be "
            "resolved statically -- only '${{ matrix.<key> }}' over a literal matrix "
            "is checkable, so this fails closed"
        )
        return

    _check_labels([value], f"{where} job {job_name!r}", errors)


def check_workflow(path: Path) -> list[str]:
    errors: list[str] = []
    where = path.name
    try:
        data = parse_workflow(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return [f"{where}: could not be read: {exc}"]
    except MultiDocumentError as exc:
        return [f"{where}: {exc}"]

    jobs = data.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        return [f"{where}: no parseable 'jobs' mapping"]

    for job_name, job in jobs.items():
        check_job(job_name, job, where, errors)
    return errors


def check_all(workflows_dir: Path) -> list[str]:
    workflows_dir = Path(workflows_dir)
    if not workflows_dir.is_dir():
        return [f"{workflows_dir}: no such directory"]

    paths = sorted(
        p for p in workflows_dir.iterdir()
        if p.is_file() and p.suffix in (".yml", ".yaml")
    )
    if not paths:
        return [f"{workflows_dir}: no workflow files found"]

    errors: list[str] = []
    for path in paths:
        errors.extend(check_workflow(path))
    return errors


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workflows-dir",
        default=str(REPO_ROOT / ".github" / "workflows"),
        help="directory of workflow files (default: this repo's .github/workflows)",
    )
    args = parser.parse_args()

    errors = check_all(Path(args.workflows_dir))
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        print(
            "\nOwner directive 18: GitHub-hosted runners only. Add a label to "
            "HOSTED_LABELS in this file only if it is genuinely a "
            "GitHub-hosted runner."
        )
        return 1
    print("lws-hosted-runner check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
