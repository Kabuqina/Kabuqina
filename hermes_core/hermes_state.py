"""Deprecated module alias for :mod:`kabuqina_state`.

Remove after the one-release A-R3 compatibility window.
"""

import sys

import kabuqina_state as _canonical

sys.modules[__name__] = _canonical
