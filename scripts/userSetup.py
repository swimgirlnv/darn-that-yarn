"""
Maya userSetup.py for Darn That Yarn.

SETUP INSTRUCTIONS (do this once):
  Symlink or copy this file to your Maya scripts directory, e.g.:
    macOS/Linux: ~/Library/Preferences/Autodesk/maya/<version>/scripts/
    Windows:     Documents\maya\<version>\scripts\

  Then set DARN_THAT_YARN_PATH in that same userSetup.py (or in Maya.env)
  to the absolute path of the repo's 'scripts' folder, e.g.:

    macOS/Linux: export DARN_THAT_YARN_PATH=/path/to/darn-that-yarn/scripts
    Windows:     set DARN_THAT_YARN_PATH=C:\path\to\darn-that-yarn\scripts

  Alternatively, edit REPO_SCRIPTS_PATH below to an absolute path for your machine.
"""
import os
import sys

# Option 1: read from environment variable
_env_path = os.environ.get("DARN_THAT_YARN_PATH")

# Option 2: hardcode your local path here as a fallback
REPO_SCRIPTS_PATH = ""  # e.g. "/Users/yourname/dev/darn-that-yarn/scripts"

scripts_dir = _env_path or REPO_SCRIPTS_PATH

if scripts_dir and os.path.isdir(scripts_dir):
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    print(f"[darn-that-yarn] Added to sys.path: {scripts_dir}")
else:
    print(
        "[darn-that-yarn] WARNING: Could not find scripts directory. "
        "Set DARN_THAT_YARN_PATH or edit REPO_SCRIPTS_PATH in userSetup.py."
    )
