"""
Release information - reads releases.json (see SP-046).

releases.json is a list of releases, newest first. Each release looks like:

    {"version": 10, "date": "2026-10-07",
     "changes": [{"sp": "046", "text": "What changed, in plain words"}]}

This one file is the single source of truth for BOTH the version number shown
in the footer (the first entry) and the list on the What's New page, so the
two can never disagree.

The functions here never raise on a bad or missing file. A broken release
file should never be able to take down every page of the app (the footer is on
all of them), so we quietly fall back to "no release information" instead.
"""

import json
from typing import Dict, List, Optional


def _clean_release(entry) -> Optional[Dict]:
    """
    Validate one entry from the file. Returns a tidy dict, or None if the
    entry is unusable (so one bad entry doesn't hide all the good ones).
    """
    if not isinstance(entry, dict):
        return None

    version = entry.get('version')
    # bool is a subclass of int in Python (True == 1), so exclude it explicitly
    if not isinstance(version, int) or isinstance(version, bool):
        return None

    date = entry.get('date')
    if not isinstance(date, str):
        return None

    changes = []
    raw_changes = entry.get('changes')
    if isinstance(raw_changes, list):
        for change in raw_changes:
            # Each change needs at least a text; the SP number is optional
            if isinstance(change, dict) and isinstance(change.get('text'), str):
                sp = change.get('sp')
                changes.append({
                    'text': change['text'],
                    'sp': sp if isinstance(sp, str) else None,
                })

    return {'version': version, 'date': date, 'changes': changes}


def load_releases(path: str) -> List[Dict]:
    """
    Read releases.json and return the list of releases in file order
    (newest first). Returns an empty list if the file is missing, unreadable,
    not valid JSON, or not a list.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        # OSError: file missing or unreadable.
        # ValueError: invalid JSON (json.JSONDecodeError is a ValueError),
        # or a file that isn't valid UTF-8.
        return []

    if not isinstance(data, list):
        return []

    releases = [_clean_release(entry) for entry in data]
    return [r for r in releases if r is not None]


def current_version(releases: List[Dict]) -> Optional[int]:
    """The current version is the first (newest) entry, or None if there are none."""
    return releases[0]['version'] if releases else None
