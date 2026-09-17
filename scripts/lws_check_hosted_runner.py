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

# Curated allow-list of GitHub-hosted runner labels. Deliberately exact: a
# label that merely looks hosted (`ubuntu-latest-8core`) is a larger-runner
# name an owner configures, indistinguishable from a self-hosted label, so it
# fails until someone adds it here on purpose.
HOSTED_LABEL_PATTERNS = (
    re.compile(r"ubuntu-(?:latest|\d{2}\.\d{2})(?:-arm)?"),
    re.compile(r"windows-(?:latest|\d{4})(?:-arm)?"),
    re.compile(r"macos-(?:latest|\d{2})(?:-large|-xlarge)?"),
)

MATRIX_EXPR_RE = re.compile(r"^\$\{\{\s*matrix\.([A-Za-z0-9_-]+)\s*\}\}$")
ANY_EXPR_RE = re.compile(r"\$\{\{.*\}\}")

Node = Union[str, list, dict]


def is_hosted_label(label: str) -> bool:
    """True only for a label this file recognises as GitHub-hosted."""
    if not isinstance(label, str):
        return False
    return any(p.fullmatch(label.strip()) for p in HOSTED_LABEL_PATTERNS)


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


def _significant_lines(text: str) -> list[tuple[int, str]]:
    """(indent, content) for each line that carries structure."""
    rows: list[tuple[int, str]] = []
    for raw in text.splitlines():
        if raw.lstrip().startswith("#"):
            continue
        stripped = _strip_comment(raw)
        if not stripped.strip():
            continue
        rows.append((len(stripped) - len(stripped.lstrip()), stripped.strip()))
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

    # A block sequence.
    if rows[start][1].startswith("- "):
        items: list = []
        i = start
        while i < len(rows) and rows[i][0] == indent and rows[i][1].startswith("- "):
            items.append(_scalar(rows[i][1][2:]))
            i += 1
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
        values = matrix.get(key) if isinstance(matrix, dict) else None
        if isinstance(values, str) and values:
            values = [values]
        if not isinstance(values, list) or not values:
            errors.append(
                f"{where}: job {job_name!r} runs on '{value}' but "
                f"strategy.matrix.{key} is not a list this check can resolve"
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
            "HOSTED_LABEL_PATTERNS in this file only if it is genuinely a "
            "GitHub-hosted runner."
        )
        return 1
    print("lws-hosted-runner check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
