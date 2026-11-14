"""Non-interactive options for Git operations owned by the backend."""

import os
import subprocess
from typing import Any


def background_git_options() -> dict[str, Any]:
    # Cached credentials still work; a background request cannot answer prompts.
    environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "Never"}
    options: dict[str, Any] = {"env": environment, "stdin": subprocess.DEVNULL}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    return options
