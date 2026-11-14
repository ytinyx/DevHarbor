import os
import subprocess
from types import SimpleNamespace

import pytest

from app.services import code_analysis, worktree_manager


@pytest.mark.parametrize("runner", [code_analysis._run_git, worktree_manager._run_git])
def test_background_git_cannot_wait_for_credentials(monkeypatch, tmp_path, runner):
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "1")
    monkeypatch.setenv("GCM_INTERACTIVE", "Always")
    monkeypatch.setenv("DEVHARBOR_GIT_TEST", "preserved")
    calls = []

    def run(command, **options):
        calls.append((command, options))
        return SimpleNamespace(stdout="ready\n")

    monkeypatch.setattr(subprocess, "run", run)
    runner(["fetch", "origin", "main"], cwd=tmp_path)
    command, options = calls[0]
    assert command == ["git", "fetch", "origin", "main"]
    assert options["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert options["env"]["GCM_INTERACTIVE"] == "Never"
    assert options["env"]["DEVHARBOR_GIT_TEST"] == "preserved"
    assert options["stdin"] == subprocess.DEVNULL
    assert options["timeout"] > 0
    if os.name == "nt":
        assert options["creationflags"] & subprocess.CREATE_NO_WINDOW
    # The rest of the application and the user's shell retain their environment.
    assert os.environ["GIT_TERMINAL_PROMPT"] == "1"
