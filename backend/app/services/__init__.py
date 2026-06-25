"""Business-logic services.

Layering: services depend on ``models``, ``utils``, and ``core`` — never on ``api`` or
``workers``. The provider sub-package is the only place that talks to an external flight
source. See ``docs/architecture.md``.
"""
