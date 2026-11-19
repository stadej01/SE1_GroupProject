"""Arguments shared by the reset commands."""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import CommandError


def add_target_arguments(parser):
    parser.add_argument("--database-host", required=True)
    parser.add_argument("--database-name", required=True)
    parser.add_argument("--repository", required=True, help="owner/name")
    parser.add_argument("--branch", required=True)


def outside_repository(path):
    """These files list private project data, so they stay out of the source tree."""
    resolved = Path(path).resolve()
    if resolved.is_relative_to(Path(settings.BASE_DIR).parent.resolve()):
        raise CommandError(f"Write {path} outside the source repository.")
    return resolved


def write_private_json(path, data):
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
