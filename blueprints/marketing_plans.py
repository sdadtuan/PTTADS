"""Marketing plan HTTP surface.

- Preliminary (KH MKT sơ bộ @ Proposal): ``blueprints.presales``
- Official (TMMT @ Deliver): ``blueprints.lifecycle``
"""
from __future__ import annotations

from blueprints import lifecycle as lifecycle_module
from blueprints import presales as presales_module

__all__ = ["presales_module", "lifecycle_module"]
