"""PyInstaller entry point: the desktop icon, or the server when given --server."""

import sys

from notation_service.launcher import main

sys.exit(main())
