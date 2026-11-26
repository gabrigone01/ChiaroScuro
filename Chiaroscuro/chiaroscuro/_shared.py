"""Moduli condivisi della root ProgettiQlc (_tools/): qxf, qlc_ws, midi_in, coremidi.
Dai sorgenti li prende da ../../_tools; nell'app impacchettata sono inclusi da PyInstaller."""
import os
import sys

_TOOLS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "_tools"))
if os.path.isdir(_TOOLS) and _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

import qxf      # noqa: E402,F401
import qlc_ws   # noqa: E402,F401
import midi_in  # noqa: E402,F401
