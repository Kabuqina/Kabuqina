"""Deprecated module alias for :mod:`kabuqina_time`.

Remove after the one-release A-R3 compatibility window.
"""

import sys

import kabuqina_time as _canonical

sys.modules[__name__] = _canonical
