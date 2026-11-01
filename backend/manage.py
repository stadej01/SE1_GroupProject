#!/usr/bin/env python
"""Django management entry point. Defaults to the local dialogue editor."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Django is not installed in the active Python environment.") from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
