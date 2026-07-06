# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Built-in course definitions bundled with the learning package.

Each course is a pure-Python data module exposing a ``COURSE`` dict (space +
artifacts + embedded source materials). Keeping the content in Python — not a
side-car ``.json``/asset tree — means a built-in course ships on exactly the
same path as the ``learning`` package code, with no ``package_data`` / bundle
wiring, and materials can be written into a workspace without a separate copy
step. See :mod:`learning.builtin_course_seed`.
"""
