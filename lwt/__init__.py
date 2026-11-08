"""LWT interpreter package.

Implemented language surface: scalars and variables, blocks and control flow
(``when``/``otherwise``, ``while``, ``each``, ``break``/``continue``), functions,
arrays and records, dict mappings, ``throw``/``finally`` recovery, static
function-library modules, and deterministic replayable concurrency
(``spawn``/``join``/``yield()``/channels, spec section 11).

The version string is the single source of truth mirrored by
``docs/delivery-manifest.json``; ``python -m lwt --version`` prints it.
"""

__version__ = "0.3.0"
