"""
Centralized output directory resolution.

All orchestrator modules import get_output_root() from here.
The value is resolved at call time from the SPECA_OUTPUT_DIR
environment variable, defaulting to "outputs" for backward compatibility.
"""

import os
from pathlib import Path


def get_output_root() -> Path:
    """Return the output root directory, resolved from env or default.

    Supports parallel SPECA instances by allowing each process
    to set its own ``SPECA_OUTPUT_DIR``.
    """
    return Path(os.environ.get("SPECA_OUTPUT_DIR", "outputs"))
