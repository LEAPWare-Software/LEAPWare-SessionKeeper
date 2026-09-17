"""Tests for scripts/lws_check_hosted_runner.py.

Owner directive 18: "Public repos use GitHub-hosted runners only, never
self-hosted or local; add a CI check that fails on any `runs-on` value other
than a GitHub-hosted runner, proven by breaking it on purpose."

The proof-by-breaking is `test_breaking_the_real_ci_workflow_is_caught`: it
takes this repo's own `.github/workflows/ci.yml`, injects a self-hosted
runner, and asserts the check rejects it. A check that only ever sees clean
input has never been shown to catch anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lws_check_hosted_runner as hr  # noqa: E402


def _write(tmp_path: Path, text: str, name: str = "wf.yml") -> Path:
    d = tmp_path / "workflows"
    d.mkdir(exist_ok=True)
    p = d / name
    p.write_text(text, encoding="utf-8")
    return d


# --- label classification ---------------------------------------------------

def test_known_hosted_labels_are_accepted():
    for label in ("ubuntu-latest", "ubuntu-22.04", "windows-latest",
                  "windows-2022", "macos-latest", "macos-14"):
        assert hr.is_hosted_label(label) is True, label


def test_self_hosted_and_unknown_labels_are_rejected():
    for label in ("self-hosted", "linux", "my-runner", "ubuntu-latest-8core",
                  "SELF-HOSTED", "gpu"):
        assert hr.is_hosted_label(label) is False, label


# --- literal runs-on --------------------------------------------------------

def test_literal_hosted_runner_passes(tmp_path):
    d = _write(tmp_path, "jobs:\n  a:\n    runs-on: ubuntu-latest\n")
    assert hr.check_all(d) == []


def test_literal_self_hosted_runner_fails(tmp_path):
    d = _write(tmp_path, "jobs:\n  a:\n    runs-on: self-hosted\n")
    errors = hr.check_all(d)
    assert errors and any("self-hosted" in e for e in errors)


def test_runs_on_sequence_with_self_hosted_fails(tmp_path):
    d = _write(tmp_path, "jobs:\n  a:\n    runs-on: [self-hosted, linux, x64]\n")
    assert hr.check_all(d) != []


def test_runs_on_sequence_all_hosted_passes(tmp_path):
    d = _write(tmp_path, "jobs:\n  a:\n    runs-on: [ubuntu-latest]\n")
    assert hr.check_all(d) == []


def test_runner_group_mapping_fails(tmp_path):
    # `runs-on: group:` only ever names a self-hosted runner group.
    d = _write(tmp_path, "jobs:\n  a:\n    runs-on:\n      group: my-group\n")
    assert hr.check_all(d) != []


# --- matrix expressions -----------------------------------------------------

def test_matrix_expression_resolving_to_hosted_passes(tmp_path):
    d = _write(tmp_path, (
        "jobs:\n"
        "  a:\n"
        "    strategy:\n"
        "      matrix:\n"
        "        os: [ubuntu-latest, windows-latest, macos-latest]\n"
        "    runs-on: ${{ matrix.os }}\n"
    ))
    assert hr.check_all(d) == []


def test_matrix_expression_with_one_self_hosted_entry_fails(tmp_path):
    d = _write(tmp_path, (
        "jobs:\n"
        "  a:\n"
        "    strategy:\n"
        "      matrix:\n"
        "        os: [ubuntu-latest, self-hosted]\n"
        "    runs-on: ${{ matrix.os }}\n"
    ))
    errors = hr.check_all(d)
    assert errors and any("self-hosted" in e for e in errors)


def test_matrix_block_sequence_form_is_resolved(tmp_path):
    d = _write(tmp_path, (
        "jobs:\n"
        "  a:\n"
        "    strategy:\n"
        "      matrix:\n"
        "        os:\n"
        "          - ubuntu-latest\n"
        "          - self-hosted\n"
        "    runs-on: ${{ matrix.os }}\n"
    ))
    assert hr.check_all(d) != []


def test_matrix_key_that_does_not_exist_fails_closed(tmp_path):
    # runs-on names a matrix key the job never defines: unresolvable, so it
    # could be anything. Fail, do not skip.
    d = _write(tmp_path, (
        "jobs:\n"
        "  a:\n"
        "    strategy:\n"
        "      matrix:\n"
        "        python: ['3.12']\n"
        "    runs-on: ${{ matrix.os }}\n"
    ))
    assert hr.check_all(d) != []


def test_matrix_include_adding_a_self_hosted_runner_is_caught(tmp_path):
    """`include` entries add runner combinations the top-level lists never name.

    GitHub adds an `include` entry that matches no existing combination as an
    extra job. Reading only the flat `matrix.<key>` list therefore misses a
    real, running self-hosted job -- a silent bypass of the whole gate.
    """
    d = _write(tmp_path, (
        "jobs:\n"
        "  a:\n"
        "    strategy:\n"
        "      matrix:\n"
        "        os: [ubuntu-latest]\n"
        "        include:\n"
        "          - os: self-hosted\n"
        "            extra: 1\n"
        "    runs-on: ${{ matrix.os }}\n"
    ))
    errors = hr.check_all(d)
    assert errors and any("self-hosted" in e for e in errors)


def test_matrix_include_with_only_hosted_entries_passes(tmp_path):
    d = _write(tmp_path, (
        "jobs:\n"
        "  a:\n"
        "    strategy:\n"
        "      matrix:\n"
        "        os: [ubuntu-latest]\n"
        "        include:\n"
        "          - os: macos-14\n"
        "            experimental: true\n"
        "    runs-on: ${{ matrix.os }}\n"
    ))
    assert hr.check_all(d) == []


def test_matrix_key_supplied_only_by_include_is_resolved(tmp_path):
    # No top-level `os` key at all -- the value comes solely from include.
    d = _write(tmp_path, (
        "jobs:\n"
        "  a:\n"
        "    strategy:\n"
        "      matrix:\n"
        "        python: ['3.12']\n"
        "        include:\n"
        "          - os: self-hosted\n"
        "    runs-on: ${{ matrix.os }}\n"
    ))
    errors = hr.check_all(d)
    assert errors and any("self-hosted" in e for e in errors)


def test_windows_11_arm_and_ubuntu_arm_are_hosted():
    # Real, currently-shipping GitHub-hosted Arm64 labels. A pattern requiring
    # a 4-digit Windows year rejects windows-11-arm, which is a false positive
    # against a legitimate hosted runner.
    for label in ("windows-11-arm", "ubuntu-24.04-arm", "ubuntu-22.04-arm"):
        assert hr.is_hosted_label(label) is True, label


def test_multi_document_workflow_is_rejected(tmp_path):
    """Two `---`-separated documents must not silently merge.

    The second document's `jobs:` key would otherwise overwrite the first's,
    making a self-hosted runner in the first document disappear entirely.
    """
    d = _write(tmp_path, (
        "jobs:\n"
        "  a:\n"
        "    runs-on: self-hosted\n"
        "---\n"
        "jobs:\n"
        "  b:\n"
        "    runs-on: ubuntu-latest\n"
    ))
    errors = hr.check_all(d)
    assert errors and any("document" in e.lower() for e in errors)


def test_single_leading_document_marker_is_allowed(tmp_path):
    d = _write(tmp_path, "---\njobs:\n  a:\n    runs-on: ubuntu-latest\n")
    assert hr.check_all(d) == []


def test_non_matrix_expression_fails_closed(tmp_path):
    # An env/vars/input expression can resolve to a self-hosted label at run
    # time and cannot be checked statically. Fail-closed is the only safe read.
    for expr in ("${{ env.RUNNER }}", "${{ vars.RUNNER_LABEL }}",
                 "${{ inputs.runner }}", "${{ github.event.inputs.r }}"):
        d = _write(tmp_path, f"jobs:\n  a:\n    runs-on: {expr}\n", name="e.yml")
        assert hr.check_all(d) != [], expr


# --- whole-directory behaviour ----------------------------------------------

def test_job_with_no_runs_on_is_reported(tmp_path):
    # A reusable-workflow call job legitimately has no runs-on, but it has a
    # `uses:` instead; a job with neither is malformed and must not pass silently.
    d = _write(tmp_path, "jobs:\n  a:\n    steps:\n      - run: echo hi\n")
    assert hr.check_all(d) != []


def test_reusable_workflow_call_job_is_allowed(tmp_path):
    d = _write(tmp_path, "jobs:\n  a:\n    uses: ./.github/workflows/other.yml\n")
    assert hr.check_all(d) == []


def test_all_workflow_files_in_directory_are_checked(tmp_path):
    d = _write(tmp_path, "jobs:\n  a:\n    runs-on: ubuntu-latest\n", name="good.yml")
    (d / "bad.yaml").write_text("jobs:\n  b:\n    runs-on: self-hosted\n", encoding="utf-8")
    errors = hr.check_all(d)
    assert errors and any("bad.yaml" in e for e in errors)


# --- this repo, and the proof by breaking it --------------------------------

def test_this_repos_workflows_are_all_hosted():
    assert hr.check_all(REPO_ROOT / ".github" / "workflows") == []


def test_breaking_the_real_ci_workflow_is_caught(tmp_path):
    """Directive 18's 'proven by breaking it on purpose'.

    Take this repo's real ci.yml, swap the hosted matrix for a self-hosted
    runner, and assert the check rejects it. Without this, a green check
    proves only that it was never asked a hard question.
    """
    workflows = REPO_ROOT / ".github" / "workflows"
    real = (workflows / "ci.yml").read_text(encoding="utf-8")
    # The real file is clean as-is. Asserted as the property that matters --
    # every job resolves to a hosted runner -- not as absence of the literal
    # string, which any comment in the file may legitimately contain.
    assert hr.check_workflow(workflows / "ci.yml") == []

    broken = real.replace(
        "os: [windows-latest, macos-latest, ubuntu-latest]",
        "os: [windows-latest, self-hosted, ubuntu-latest]",
        1,
    )
    assert broken != real, "the injection point moved -- update this test"

    d = tmp_path / "workflows"
    d.mkdir()
    (d / "ci.yml").write_text(broken, encoding="utf-8")

    errors = hr.check_all(d)
    assert errors and any("self-hosted" in e for e in errors)
