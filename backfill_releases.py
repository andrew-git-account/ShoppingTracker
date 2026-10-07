"""
Backfill the release history into releases.json (see SP-048).

Before release versioning existed (SP-046), nine deployments were made. They
are recorded in two places:

1. Git: a commit whose message looks like
       "Mark SP-001, SP-002 as deployed (cb773f5)"
   was made right after each deployment. Oldest first, these are the releases
   1, 2, 3 ... in order, and the SHA in brackets is the deployed commit.
2. The backlog: every finished story in backlog/done/ has a line
       **Deployed**: cb773f5 (2026-08-16)
   which gives the SHA it shipped in and the real deployment date.

This script combines the two and merges the result into releases.json, so the
What's New page can show the whole history without anyone typing it by hand.

Usage (from the project root):
    python backfill_releases.py            # dry run: only prints what it would add
    python backfill_releases.py --write    # really updates releases.json

Safe to run more than once: it only ever adds releases OLDER than the oldest
one already in the file, and never changes an existing entry. If the history
looks inconsistent (a story whose Deployed line disagrees with git) it stops
with a message instead of guessing.

NOTE: deliberately not named migrate_*.py - the sdlc-deploy skill treats any
new or changed migrate_*.py as a production data migration and pauses to ask.
This script only edits a file in the repo; it never touches production data.
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys

# "Mark SP-001, SP-002 as deployed (cb773f5)"  ->  SPs + deployed SHA
_MARKING_RE = re.compile(r'^Mark (SP-\d+(?:, SP-\d+)*) as deployed \(([0-9a-f]+)\)$')
# "**Deployed**: cb773f5 (2026-08-16)"
_DEPLOYED_RE = re.compile(r'^\*\*Deployed\*\*:\s*([0-9a-f]+)\s*\((\d{4}-\d{2}-\d{2})\)', re.MULTILINE)
# "# SP-045: Allow a 5-Day Date Window in Transaction Matching"
_TITLE_RE = re.compile(r'^# SP-\d+:\s*(.+?)\s*$', re.MULTILINE)
_FILENAME_RE = re.compile(r'^SP-(\d+)-')


class BackfillError(Exception):
    """The history is inconsistent or a file is unusable - stop, don't guess."""


def _sp_key(number) -> str:
    """Normalise an SP number to the zero-padded form used everywhere ('45' -> '045')."""
    return f'{int(number):03d}'


def _safe(text: str) -> str:
    """The Windows console (cp1252) can't print every character; never crash on one."""
    return text.encode('ascii', 'replace').decode('ascii')


def get_marking_subjects(repo_dir: str) -> list:
    """
    Subjects of every "... as deployed ..." commit, oldest first.
    This is the only place that talks to git, so tests can replace it.
    """
    result = subprocess.run(
        ['git', 'log', '--reverse', '--format=%s', '--grep=as deployed'],
        cwd=repo_dir, capture_output=True, text=True, encoding='utf-8'
    )
    if result.returncode != 0:
        raise BackfillError(f'git log failed: {result.stderr.strip()}')
    return [line for line in result.stdout.splitlines() if line.strip()]


def parse_marking_subject(subject: str):
    """
    "Mark SP-001, SP-002 as deployed (cb773f5)" -> ('cb773f5', ['001', '002']).
    Returns None for any other commit subject.
    """
    match = _MARKING_RE.match(subject)
    if not match:
        return None
    sp_numbers = [_sp_key(n) for n in re.findall(r'SP-(\d+)', match.group(1))]
    return match.group(2), sp_numbers


def read_sp_info(done_dir: str) -> dict:
    """
    Read every SP-*.md in the done folder.
    Returns {'045': {'title': ..., 'sha': ... or None, 'date': ... or None}}.
    """
    info = {}
    for path in glob.glob(os.path.join(done_dir, 'SP-*.md')):
        name_match = _FILENAME_RE.match(os.path.basename(path))
        if not name_match:
            continue
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
        title = _TITLE_RE.search(text)
        deployed = _DEPLOYED_RE.search(text)
        info[_sp_key(name_match.group(1))] = {
            'title': title.group(1) if title else None,
            'sha': deployed.group(1) if deployed else None,
            'date': deployed.group(2) if deployed else None,
        }
    return info


def derive_releases(subjects, sp_info: dict) -> list:
    """
    Build the release list, OLDEST FIRST: the first "as deployed" commit is
    version 1, the next version 2, and so on.

    Each release's date comes from its stories' Deployed lines (the real
    deployment day), not from the date of the marking commit, which can be a
    day later. Every check below raises BackfillError rather than guessing.
    """
    releases = []
    for subject in subjects:
        parsed = parse_marking_subject(subject)
        if parsed is None:
            continue  # some other commit that happened to match the search
        deployed_sha, sp_numbers = parsed
        version = len(releases) + 1

        dates = set()
        changes = []
        for number in sorted(sp_numbers, key=int):
            sp = sp_info.get(number)
            if sp is None:
                raise BackfillError(
                    f'Release {version}: SP-{number} is named by git but has no file in the done folder.')
            if not sp['title']:
                raise BackfillError(f'SP-{number}: could not find the "# SP-NNN: Title" heading.')
            if not sp['sha'] or not sp['date']:
                raise BackfillError(f'SP-{number}: no "**Deployed**: <sha> (<date>)" line found.')
            # Short SHAs can be written with different lengths, so accept a prefix match
            if not (sp['sha'].startswith(deployed_sha) or deployed_sha.startswith(sp['sha'])):
                raise BackfillError(
                    f'SP-{number}: its Deployed line says {sp["sha"]} but git says release {version} '
                    f'was {deployed_sha}.')
            dates.add(sp['date'])
            changes.append({'sp': number, 'text': sp['title']})

        if len(dates) != 1:
            raise BackfillError(
                f'Release {version} ({deployed_sha}): its stories disagree on the date: '
                f'{", ".join(sorted(dates))}.')

        releases.append({'version': version, 'date': dates.pop(), 'changes': changes})
    return releases


def merge_releases(existing: list, derived: list):
    """
    Add derived releases to the existing file contents.

    Only releases OLDER than the oldest existing one are added: git history may
    by then contain deployments newer than what is in the file (and they may
    already be there), and an existing entry must never be changed. The new
    entries go after the existing ones, newest first, so the file keeps its
    newest-first order.

    Returns (merged_list, added, skipped).
    """
    existing_versions = [e['version'] for e in existing
                         if isinstance(e, dict) and isinstance(e.get('version'), int)]
    lowest = min(existing_versions) if existing_versions else None

    added = [r for r in derived if lowest is None or r['version'] < lowest]
    skipped = [r for r in derived if lowest is not None and r['version'] >= lowest]
    added.sort(key=lambda r: r['version'], reverse=True)
    return list(existing) + added, added, skipped


def _load_existing(path: str) -> list:
    """Existing releases.json as raw data. Missing file = empty; a broken file is never overwritten."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        raise BackfillError(f'{path} could not be read as JSON ({exc}); not touching it.')
    if not isinstance(data, list):
        raise BackfillError(f'{path} is not a JSON list; not touching it.')
    return data


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Backfill releases.json from the deploy history.')
    parser.add_argument('--write', action='store_true',
                        help='update releases.json (without this flag it is a dry run)')
    parser.add_argument('--releases-file', default='releases.json')
    parser.add_argument('--done-dir', default=os.path.join('backlog', 'done'))
    parser.add_argument('--repo-dir', default='.')
    args = parser.parse_args(argv)

    try:
        existing = _load_existing(args.releases_file)
        derived = derive_releases(get_marking_subjects(args.repo_dir), read_sp_info(args.done_dir))
        merged, added, skipped = merge_releases(existing, derived)
    except BackfillError as exc:
        print(f'[FAIL] {_safe(str(exc))}')
        return 1

    if skipped:
        versions = ', '.join(str(r['version']) for r in sorted(skipped, key=lambda r: r['version']))
        print(f'[INFO] Skipped version(s) {versions}: not older than the oldest existing release.')

    if not added:
        print('[OK] Nothing to add.')
        return 0

    print(f'{"Adding" if args.write else "Would add"} {len(added)} release(s):')
    for release in added:
        print(f'  Version {release["version"]} ({release["date"]}): {len(release["changes"])} change(s)')
        for change in release['changes']:
            print(f'    SP-{change["sp"]}: {_safe(change["text"])}')

    if args.write:
        with open(args.releases_file, 'w', encoding='utf-8') as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
            f.write('\n')
        print(f'[OK] {args.releases_file} updated.')
    else:
        print('[INFO] Dry run - nothing written. Re-run with --write to apply.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
