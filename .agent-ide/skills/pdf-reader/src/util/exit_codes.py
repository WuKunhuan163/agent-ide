"""Exit codes, defined once so every verb agrees on them.

A caller has to be able to tell three different situations apart, so they get three
different numbers:

* ``OK`` -- everything asked for was delivered;
* ``PARTIAL`` -- something was delivered and something was not; a later ``fetch``
  can still collect the rest, which is why this is not simply a failure;
* ``FAILED`` -- nothing was delivered;
* ``USAGE`` -- the request itself was wrong (bad arguments, unknown parameter, a
  value outside its bounds) or the credentials/config were not usable.  Nothing was
  submitted, so it must not be confused with ``PARTIAL``: the caller has to fix the
  command rather than wait.

``USAGE`` uses the conventional value from ``sysexits.h`` precisely because it is
*not* in the 0/1/2 run-outcome family.
"""
from __future__ import annotations

OK = 0
FAILED = 1
PARTIAL = 2
USAGE = 64
