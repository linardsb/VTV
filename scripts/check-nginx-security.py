#!/usr/bin/env python3
"""nginx configuration security validator for VTV platform.

Reads nginx/nginx.conf and validates required security headers
and configuration directives are present.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def main() -> int:
    """Validate nginx security configuration."""
    nginx_path = Path("nginx/nginx.conf")
    if not nginx_path.exists():
        print("SKIP: nginx/nginx.conf not found")
        return 0

    content = nginx_path.read_text()
    failures = 0
    total = 0

    checks: list[tuple[str, str, bool]] = [
        # (name, regex pattern, is_hard_fail)
        ("Content-Security-Policy header", r"add_header\s+Content-Security-Policy", True),
        ("X-Frame-Options header", r"add_header\s+X-Frame-Options", True),
        ("X-Content-Type-Options header", r"add_header\s+X-Content-Type-Options", True),
        ("Strict-Transport-Security header", r"add_header\s+Strict-Transport-Security", True),
        ("Rate limiting configured", r"limit_req_zone", True),
        ("No unsafe-eval in CSP", r"unsafe-eval", False),  # WARN if present
    ]

    for name, pattern, is_hard in checks:
        total += 1
        match = re.search(pattern, content)

        if name == "No unsafe-eval in CSP":
            # Special case: presence is bad
            if match:
                print(f"  WARN: {name} - unsafe-eval found in CSP (consider removing)")
                # WARN, not FAIL
            else:
                print(f"  PASS: {name}")
        else:
            if match:
                print(f"  PASS: {name}")
            elif is_hard:
                print(f"  FAIL: {name} - not found in nginx.conf")
                failures += 1
            else:
                print(f"  WARN: {name} - not found")

    print(f"\nnginx security: {total - failures}/{total} checks passed")
    return failures


if __name__ == "__main__":
    sys.exit(main())
