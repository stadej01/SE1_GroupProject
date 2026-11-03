#!/usr/bin/env python3
"""Django management entry point. Defaults to the local dialogue editor."""

import os
import sys


def main():
    """Run Django management commands."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Is it installed and available "
            "in your current Python environment? "
            "Did you forget to activate your virtual environment?"
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()