#!/usr/bin/env python3
"""Validate run_command tool calls.

The script reads a JSON object from stdin representing the tool call
arguments (as produced by the Antigravity hook system). It inspects the
`CommandLine` field and aborts execution (exit code 1) if a destructive
command such as `rm -rf /` is detected.
"""
import sys
import json
import re

def is_destructive(command: str) -> bool:
    # Simple heuristic to catch `rm -rf /` or variants that attempt to
    # delete the root filesystem. The pattern allows optional whitespace
    # around the components.
    pattern = re.compile(r"\brm\s+-rf\s+/?$", re.IGNORECASE)
    return bool(pattern.search(command.strip()))

def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("[validate_tool_call] Invalid JSON input", file=sys.stderr)
        sys.exit(1)

    command = payload.get("CommandLine", "")
    if is_destructive(command):
        print(
            f"[validate_tool_call] Blocked destructive command: '{command}'",
            file=sys.stderr,
        )
        sys.exit(1)
    # If we reach here, the command is considered safe.
    sys.exit(0)

if __name__ == "__main__":
    main()
