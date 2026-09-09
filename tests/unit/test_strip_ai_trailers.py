"""Tests for the commit-message trailer policy.

The hook must remove assistant attribution and nothing else. Over-matching would
delete real human co-authorship, which is worse than the problem it solves.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_hook() -> ModuleType:
    name = "strip_ai_trailers"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, REPO_ROOT / "scripts" / "hooks" / f"{name}.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def hook() -> ModuleType:
    return _load_hook()


def test_removes_claude_coauthor(hook: ModuleType) -> None:
    message = "feat: a thing\n\nBody.\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>\n"
    assert "Claude" not in hook.strip_trailers(message)


def test_removes_session_trailer(hook: ModuleType) -> None:
    message = "fix: a thing\n\nClaude-Session: https://claude.ai/code/session_abc123\n"
    assert "Claude-Session" not in hook.strip_trailers(message)


def test_removes_generated_with_line(hook: ModuleType) -> None:
    message = "docs: a thing\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\n"
    assert "Generated with" not in hook.strip_trailers(message)


def test_keeps_human_coauthors(hook: ModuleType) -> None:
    # Deleting real co-authorship would be a worse lie than the one being fixed.
    message = (
        "feat: a thing\n\n"
        "Co-Authored-By: Jordan Rivera <jordan@example.com>\n"
        "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>\n"
    )
    result = hook.strip_trailers(message)
    assert "Jordan Rivera" in result
    assert "Claude" not in result


def test_keeps_prose_that_mentions_the_assistant(hook: ModuleType) -> None:
    # Only whole-line trailers are removed, never a mention inside the body.
    message = "docs: explain why Claude Code output is reviewed\n\nSome body text.\n"
    assert "Claude Code" in hook.strip_trailers(message)


def test_subject_line_survives(hook: ModuleType) -> None:
    message = "feat(rapm): add bootstrap standard errors\n\nCo-Authored-By: Claude Opus 5 <x@y>\n"
    assert (
        hook.strip_trailers(message).splitlines()[0] == "feat(rapm): add bootstrap standard errors"
    )


def test_no_dangling_blank_lines(hook: ModuleType) -> None:
    message = (
        "feat: a thing\n\nBody.\n\nCo-Authored-By: Claude Opus 5 <x@y>\nClaude-Session: https://x\n"
    )
    result = hook.strip_trailers(message)
    assert result.endswith("Body.\n")


def test_message_without_trailers_is_untouched(hook: ModuleType) -> None:
    message = "chore: nothing to strip\n\nBody.\n"
    assert hook.strip_trailers(message) == message


def test_is_idempotent(hook: ModuleType) -> None:
    message = "feat: a thing\n\nCo-Authored-By: Claude Opus 5 <x@y>\n"
    once = hook.strip_trailers(message)
    assert hook.strip_trailers(once) == once


def test_message_that_is_only_trailers_becomes_empty(hook: ModuleType) -> None:
    assert hook.strip_trailers("Co-Authored-By: Claude Opus 5 <x@y>\n") == ""


def test_matching_is_case_insensitive(hook: ModuleType) -> None:
    assert (
        "claude"
        not in hook.strip_trailers("feat: x\n\nco-authored-by: claude opus 5 <x@y>\n").lower()
    )


def test_rewrites_the_file_in_place(hook: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "COMMIT_EDITMSG"
    path.write_text("feat: x\n\nCo-Authored-By: Claude Opus 5 <x@y>\n", encoding="utf-8")
    assert hook.main([str(path)]) == 0
    assert "Claude" not in path.read_text(encoding="utf-8")


def test_never_blocks_a_commit(hook: ModuleType) -> None:
    # A commit-msg hook that exits non-zero aborts the commit. Stripping a
    # trailer is never a reason to do that.
    assert hook.main([]) == 0
