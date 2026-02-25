#!/usr/bin/env python3
"""Docker Compose security validator for VTV platform.

Parses docker-compose.yml with yaml.safe_load() and validates that
long-running services have required security hardening options.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml


def check_service(name: str, config: dict[str, Any]) -> list[str]:
    """Check a single service for security hardening options."""
    failures: list[str] = []

    # Check security_opt contains no-new-privileges:true
    security_opt = config.get("security_opt", [])
    if "no-new-privileges:true" not in security_opt:
        failures.append(f"  FAIL: {name} missing security_opt: no-new-privileges:true")

    # Check cap_drop contains ALL
    cap_drop = config.get("cap_drop", [])
    if "ALL" not in cap_drop:
        failures.append(f"  FAIL: {name} missing cap_drop: ALL")

    return failures


def main() -> int:
    """Validate Docker Compose security configuration."""
    compose_path = Path("docker-compose.yml")
    if not compose_path.exists():
        print("SKIP: docker-compose.yml not found")
        return 0

    with compose_path.open() as f:
        compose = yaml.safe_load(f)

    if compose is None:
        print("ERROR: docker-compose.yml is empty or invalid YAML")
        return 1

    services: dict[str, Any] = compose.get("services", {})
    skip_services = {"migrate"}  # One-shot containers
    total_checks = 0
    total_failures = 0

    for name, config in services.items():
        if name in skip_services:
            continue
        if not isinstance(config, dict):
            continue

        failures = check_service(name, config)
        checks = 2  # no-new-privileges + cap_drop
        total_checks += checks

        if failures:
            for msg in failures:
                print(msg)
            total_failures += len(failures)
        else:
            print(f"  PASS: {name} - all security checks passed")

    print(f"\nDocker security: {total_checks - total_failures}/{total_checks} checks passed")
    return total_failures


if __name__ == "__main__":
    sys.exit(main())
