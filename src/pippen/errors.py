"""Exceptions shared across the package.

Why these live in one place
---------------------------
``MissingDependencyError`` was previously declared in five modules. Each
declaration created a distinct type, so a caller writing

.. code-block:: python

    try:
        fit_fusion(...)
    except MissingDependencyError:
        ...

caught whichever one they happened to import and silently missed the other
four. An exception whose whole purpose is to be caught by name has to be one
type.
"""

from __future__ import annotations


class MissingDependencyError(ImportError):
    """An optional dependency this code path needs is not installed.

    Raised by the modules behind the ``sources`` and ``fit`` extras. The
    message names the extra to install.
    """
