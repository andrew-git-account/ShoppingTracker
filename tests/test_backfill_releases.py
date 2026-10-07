"""
Tests for backfill_releases.py (SP-048).

Git is never called in most of these: get_marking_subjects() is replaced with
fixed commit subjects, and the backlog is a handful of small SP files written
into a temp folder. One test at the end checks the script against this repo's
real history (skipped if git history isn't available).
"""

import json
import subprocess

import pytest

import backfill_releases
from backfill_releases import (
    BackfillError,
    derive_releases,
    main,
    merge_releases,
    parse_marking_subject,
    read_sp_info,
)

SUBJECTS = [
    "Mark SP-001, SP-003 as deployed (aaa1111)",
    "Unrelated commit about deployed things",
    "Mark SP-002 as deployed (bbb2222)",
    "Mark SP-004, SP-005 as deployed (ccc3333)",
]


def write_sp(done_dir, number, title, sha=None, date=None):
    """Write a minimal finished SP file; sha/date=None leaves out the Deployed line."""
    lines = [f"# SP-{number}: {title}", "", "**Priority**: High", "**Status**: Done"]
    if sha:
        lines.append(f"**Deployed**: {sha} ({date})")
    (done_dir / f"SP-{number}-slug.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture()
def done_dir(tmp_path):
    d = tmp_path / "done"
    d.mkdir()
    write_sp(d, "001", "First story", "aaa1111", "2026-08-01")
    write_sp(d, "002", "Second story", "bbb2222", "2026-08-05")
    write_sp(d, "003", "Third story", "aaa1111", "2026-08-01")
    write_sp(d, "004", "Fourth story", "ccc3333", "2026-08-09")
    write_sp(d, "005", "Fifth story", "ccc3333", "2026-08-09")
    return d


class TestParseMarkingSubject:

    def test_extracts_sha_and_sp_numbers(self):
        assert parse_marking_subject("Mark SP-001, SP-003 as deployed (aaa1111)") == ("aaa1111", ["001", "003"])

    def test_single_sp(self):
        assert parse_marking_subject("Mark SP-045 as deployed (6e7a2e7)") == ("6e7a2e7", ["045"])

    def test_other_subjects_ignored(self):
        assert parse_marking_subject("SP-045: Allow a 5-Day Date Window") is None
        assert parse_marking_subject("Unrelated commit about deployed things") is None


class TestDeriveReleases:

    def test_versions_numbered_by_order(self, done_dir):
        releases = derive_releases(SUBJECTS, read_sp_info(str(done_dir)))

        assert [r["version"] for r in releases] == [1, 2, 3]

    def test_date_comes_from_sp_deployed_line(self, done_dir):
        releases = derive_releases(SUBJECTS, read_sp_info(str(done_dir)))

        assert [r["date"] for r in releases] == ["2026-08-01", "2026-08-05", "2026-08-09"]

    def test_changes_ascending_by_sp_with_title_text(self, done_dir):
        # The commit subject lists SP-003 before SP-001 here; output must still be ascending
        subjects = ["Mark SP-003, SP-001 as deployed (aaa1111)"]

        releases = derive_releases(subjects, read_sp_info(str(done_dir)))

        assert releases[0]["changes"] == [
            {"sp": "001", "text": "First story"},
            {"sp": "003", "text": "Third story"},
        ]

    def test_no_commit_shas_in_output(self, done_dir):
        releases = derive_releases(SUBJECTS, read_sp_info(str(done_dir)))

        assert "aaa1111" not in json.dumps(releases)
        for release in releases:
            assert set(release) == {"version", "date", "changes"}

    def test_sp_without_file_raises(self, done_dir):
        (done_dir / "SP-002-slug.md").unlink()

        with pytest.raises(BackfillError, match="SP-002"):
            derive_releases(SUBJECTS, read_sp_info(str(done_dir)))

    def test_sp_without_deployed_line_raises(self, done_dir):
        write_sp(done_dir, "002", "Second story")

        with pytest.raises(BackfillError, match="SP-002"):
            derive_releases(SUBJECTS, read_sp_info(str(done_dir)))

    def test_sha_mismatch_raises(self, done_dir):
        write_sp(done_dir, "002", "Second story", "zzz9999", "2026-08-05")

        with pytest.raises(BackfillError, match="SP-002"):
            derive_releases(SUBJECTS, read_sp_info(str(done_dir)))

    def test_dates_disagreeing_within_a_release_raises(self, done_dir):
        write_sp(done_dir, "003", "Third story", "aaa1111", "2026-08-02")

        with pytest.raises(BackfillError, match="disagree"):
            derive_releases(SUBJECTS, read_sp_info(str(done_dir)))


def _derived(versions):
    return [{"version": v, "date": f"2026-01-{v:02d}", "changes": []} for v in versions]


class TestMergeReleases:

    def test_adds_only_versions_below_lowest_existing(self):
        existing = [{"version": 10, "date": "2026-10-07", "changes": [{"sp": "046", "text": "x"}]}]

        merged, added, skipped = merge_releases(existing, _derived(range(1, 11)))

        assert [r["version"] for r in added] == [9, 8, 7, 6, 5, 4, 3, 2, 1]
        assert [r["version"] for r in skipped] == [10]
        assert [r["version"] for r in merged] == [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]

    def test_existing_entries_untouched(self):
        existing = [{"version": 10, "date": "2026-10-07", "changes": [{"sp": "046", "text": "x"}]}]

        merged, _, _ = merge_releases(existing, _derived(range(1, 4)))

        assert merged[0] is existing[0]
        assert merged[0] == {"version": 10, "date": "2026-10-07", "changes": [{"sp": "046", "text": "x"}]}

    def test_empty_existing_adds_everything_newest_first(self):
        merged, added, skipped = merge_releases([], _derived([1, 2, 3]))

        assert [r["version"] for r in merged] == [3, 2, 1]
        assert skipped == []

    def test_derived_at_or_above_lowest_existing_are_skipped(self):
        existing = [{"version": 5, "date": "2026-05-01", "changes": []}]

        merged, added, skipped = merge_releases(existing, _derived([4, 5, 6]))

        assert [r["version"] for r in added] == [4]
        assert [r["version"] for r in skipped] == [5, 6]


class TestMain:

    EXISTING = [{"version": 4, "date": "2026-08-20", "changes": [{"sp": "006", "text": "Newest"}]}]

    @pytest.fixture()
    def setup(self, tmp_path, done_dir, monkeypatch):
        monkeypatch.setattr(backfill_releases, "get_marking_subjects", lambda repo_dir: SUBJECTS)
        releases_file = tmp_path / "releases.json"
        releases_file.write_text(json.dumps(self.EXISTING, indent=2) + "\n", encoding="utf-8")
        args = ["--releases-file", str(releases_file), "--done-dir", str(done_dir)]
        return releases_file, args

    def test_dry_run_prints_entries_and_writes_nothing(self, setup, capsys):
        releases_file, args = setup
        before = releases_file.read_bytes()

        assert main(args) == 0

        out = capsys.readouterr().out
        assert "Would add 3 release(s)" in out
        assert "First story" in out
        assert "Dry run" in out
        assert releases_file.read_bytes() == before

    def test_write_adds_older_versions_below_existing(self, setup):
        releases_file, args = setup

        assert main(args + ["--write"]) == 0

        data = json.loads(releases_file.read_text(encoding="utf-8"))
        assert [r["version"] for r in data] == [4, 3, 2, 1]
        assert data[0] == self.EXISTING[0]
        assert data[3]["changes"] == [
            {"sp": "001", "text": "First story"},
            {"sp": "003", "text": "Third story"},
        ]

    def test_second_write_is_a_no_op(self, setup, capsys):
        releases_file, args = setup
        main(args + ["--write"])
        after_first = releases_file.read_bytes()
        capsys.readouterr()

        assert main(args + ["--write"]) == 0

        assert releases_file.read_bytes() == after_first
        assert "Nothing to add" in capsys.readouterr().out

    def test_skipped_versions_are_reported(self, tmp_path, done_dir, monkeypatch, capsys):
        monkeypatch.setattr(backfill_releases, "get_marking_subjects", lambda repo_dir: SUBJECTS)
        releases_file = tmp_path / "releases.json"
        releases_file.write_text(json.dumps(
            [{"version": 2, "date": "2026-08-05", "changes": []}]), encoding="utf-8")

        main(["--releases-file", str(releases_file), "--done-dir", str(done_dir)])

        out = capsys.readouterr().out
        assert "Skipped version(s) 2, 3" in out
        assert "Would add 1 release(s)" in out

    def test_malformed_existing_file_is_not_touched(self, tmp_path, done_dir, monkeypatch, capsys):
        monkeypatch.setattr(backfill_releases, "get_marking_subjects", lambda repo_dir: SUBJECTS)
        releases_file = tmp_path / "releases.json"
        releases_file.write_text("{ broken", encoding="utf-8")

        code = main(["--releases-file", str(releases_file), "--done-dir", str(done_dir), "--write"])

        assert code != 0
        assert releases_file.read_text(encoding="utf-8") == "{ broken"
        assert "[FAIL]" in capsys.readouterr().out

    def test_inconsistent_history_fails_without_writing(self, setup, done_dir, capsys):
        releases_file, args = setup
        write_sp(done_dir, "002", "Second story", "zzz9999", "2026-08-05")
        before = releases_file.read_bytes()

        assert main(args + ["--write"]) != 0

        assert releases_file.read_bytes() == before


def _git_history_available():
    try:
        result = subprocess.run(["git", "log", "--oneline", "--grep=as deployed"],
                                capture_output=True, text=True)
        return result.returncode == 0 and len(result.stdout.splitlines()) >= 9
    except OSError:
        return False


@pytest.mark.skipif(not _git_history_available(), reason="full git history not available")
def test_real_history_gives_versions_1_to_9_covering_sp_001_to_045_once():
    subjects = backfill_releases.get_marking_subjects(".")
    releases = derive_releases(subjects, read_sp_info("backlog/done"))
    first_nine = releases[:9]

    assert [r["version"] for r in first_nine] == list(range(1, 10))
    covered = [c["sp"] for r in first_nine for c in r["changes"]]
    assert sorted(covered) == [f"{n:03d}" for n in range(1, 46)]   # each exactly once
    assert len(first_nine[0]["changes"]) == 12
    assert first_nine[2]["date"] == "2026-08-21"   # taken from the SP files, not the marking commit
