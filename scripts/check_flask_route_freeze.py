#!/usr/bin/env python3
"""Flask HTTP monolith retired — route freeze check is a no-op."""
from __future__ import annotations


def main() -> int:
    print("Flask retired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
