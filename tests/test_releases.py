import json
import os
import re

from app.releases import current_version, load_releases

# Spec coverage:
#   everything here -> backlog/done/SP-046-show-app-version-and-whats-new-page.md
#   SP number shown first on /whats-new -> backlog/SP-049-show-sp-number-before-description-on-whats-new.md

SAMPLE_RELEASES = [
    {"version": 12, "date": "2026-11-01",
     "changes": [{"sp": "050", "text": "Twelfth release change"}]},
    {"version": 11, "date": "2026-10-20",
     "changes": [{"sp": "049", "text": "Eleventh release change"}]},
]


def use_releases(app, tmp_path, data):
    """Write `data` to a temp releases.json and point the app at it."""
    path = tmp_path / "releases.json"
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    app.config["RELEASES_FILE"] = str(path)
    return str(path)


class TestLoadReleases:

    def test_valid_file_loads_in_file_order(self, tmp_path):
        path = tmp_path / "releases.json"
        path.write_text(json.dumps(SAMPLE_RELEASES), encoding="utf-8")

        releases = load_releases(str(path))

        assert [r["version"] for r in releases] == [12, 11]
        assert releases[0]["date"] == "2026-11-01"
        assert releases[0]["changes"] == [{"sp": "050", "text": "Twelfth release change"}]

    def test_current_version_is_first_entry(self, tmp_path):
        path = tmp_path / "releases.json"
        path.write_text(json.dumps(SAMPLE_RELEASES), encoding="utf-8")

        assert current_version(load_releases(str(path))) == 12

    def test_current_version_none_when_empty(self):
        assert current_version([]) is None

    def test_missing_file_returns_empty_list(self, tmp_path):
        assert load_releases(str(tmp_path / "nope.json")) == []

    def test_malformed_json_returns_empty_list(self, tmp_path):
        path = tmp_path / "releases.json"
        path.write_text("{ this is not json", encoding="utf-8")

        assert load_releases(str(path)) == []

    def test_non_list_json_returns_empty_list(self, tmp_path):
        path = tmp_path / "releases.json"
        path.write_text('{"version": 1}', encoding="utf-8")

        assert load_releases(str(path)) == []

    def test_bad_entries_are_skipped_good_ones_kept(self, tmp_path):
        path = tmp_path / "releases.json"
        path.write_text(json.dumps([
            "not a dict",
            {"version": "12", "date": "2026-01-01", "changes": []},   # version not an int
            {"version": True, "date": "2026-01-01", "changes": []},   # bool is not a version
            {"version": 5, "changes": []},                            # no date
            {"version": 4, "date": "2026-01-01",
             "changes": [{"sp": "001"}, "junk", {"sp": "002", "text": "Kept"}]},
        ]), encoding="utf-8")

        releases = load_releases(str(path))

        assert len(releases) == 1
        assert releases[0]["version"] == 4
        # Only the change that has a text survives
        assert releases[0]["changes"] == [{"sp": "002", "text": "Kept"}]


class TestFooterVersion:

    def test_logged_in_footer_shows_version_as_link(self, app, logged_in_client, tmp_path):
        use_releases(app, tmp_path, SAMPLE_RELEASES)

        html = logged_in_client.get("/").get_data(as_text=True)

        assert "Version 12" in html
        assert 'href="/whats-new"' in html
        assert "Shopping Tracker" in html

    def test_logged_out_footer_shows_version_without_link(self, app, client, tmp_path):
        use_releases(app, tmp_path, SAMPLE_RELEASES)

        html = client.get("/login").get_data(as_text=True)

        assert "Version 12" in html
        assert "/whats-new" not in html

    def test_version_is_plain_integer(self, app, client, tmp_path):
        use_releases(app, tmp_path, [{"version": 7, "date": "2026-01-01", "changes": []}])

        html = client.get("/login").get_data(as_text=True)

        assert "Version 7" in html
        assert "Version 007" not in html
        assert "Version 7." not in html


class TestWhatsNewPage:

    def test_anonymous_redirected_to_login(self, app, client, tmp_path):
        use_releases(app, tmp_path, SAMPLE_RELEASES)

        response = client.get("/whats-new")

        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_non_admin_user_can_view(self, app, logged_in_client, tmp_path):
        use_releases(app, tmp_path, SAMPLE_RELEASES)

        assert logged_in_client.get("/whats-new").status_code == 200

    def test_admin_user_can_view(self, app, admin_client, tmp_path):
        use_releases(app, tmp_path, SAMPLE_RELEASES)

        assert admin_client.get("/whats-new").status_code == 200

    def test_lists_releases_newest_first_with_changes(self, app, logged_in_client, tmp_path):
        use_releases(app, tmp_path, SAMPLE_RELEASES)

        html = logged_in_client.get("/whats-new").get_data(as_text=True)

        assert html.index("Version 12") < html.index("Version 11")
        assert "2026-11-01" in html
        assert "Twelfth release change" in html
        assert "Eleventh release change" in html
        assert '<span class="release-sp">SP-050:</span>' in html

    def test_sp_number_shown_before_description(self, app, logged_in_client, tmp_path):
        # SP-049: each change reads "SP-NNN: description", number first
        use_releases(app, tmp_path, SAMPLE_RELEASES)

        html = logged_in_client.get("/whats-new").get_data(as_text=True)

        # Strip the tags and collapse whitespace so we compare what the user reads
        visible = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html))
        assert "SP-050: Twelfth release change" in visible
        assert "SP-049: Eleventh release change" in visible
        assert "Twelfth release change SP-050" not in visible

    def test_change_without_sp_shows_only_text(self, app, logged_in_client, tmp_path):
        use_releases(app, tmp_path, [
            {"version": 3, "date": "2026-01-01", "changes": [{"text": "Plain change"}]},
        ])

        html = logged_in_client.get("/whats-new").get_data(as_text=True)

        assert re.search(r"<li>\s*Plain change\s*</li>", html)
        assert "release-sp" not in html.split("<main")[1].split("</main>")[0]
        assert "SP-" not in html

    def test_page_has_no_javascript(self, app, logged_in_client, tmp_path):
        use_releases(app, tmp_path, SAMPLE_RELEASES)

        html = logged_in_client.get("/whats-new").get_data(as_text=True)

        assert "<script" not in html


class TestMissingOrBrokenReleasesFile:

    def test_missing_file_does_not_break_pages(self, app, client, logged_in_client, tmp_path):
        app.config["RELEASES_FILE"] = str(tmp_path / "does-not-exist.json")

        login_html = client.get("/login")
        page = logged_in_client.get("/whats-new")

        assert login_html.status_code == 200
        assert "Version" not in login_html.get_data(as_text=True)
        assert page.status_code == 200
        assert "No release information is available" in page.get_data(as_text=True)

    def test_malformed_file_does_not_break_pages(self, app, client, logged_in_client, tmp_path):
        use_releases(app, tmp_path, "{ broken json")

        login_html = client.get("/login")
        home = logged_in_client.get("/")
        page = logged_in_client.get("/whats-new")

        assert login_html.status_code == 200
        assert "Version" not in login_html.get_data(as_text=True)
        assert home.status_code == 200
        assert page.status_code == 200


class TestRealReleasesFile:
    """Guards the releases.json that actually ships in the deployment package."""

    def test_real_file_loads_and_top_entry_is_version_10(self, app):
        path = app.config["RELEASES_FILE"]
        assert os.path.basename(path) == "releases.json"

        releases = load_releases(path)

        assert current_version(releases) == 10
        assert releases[0]["changes"], "version 10 should describe its changes"

    def test_real_file_stores_no_commit_shas(self, app):
        with open(app.config["RELEASES_FILE"], encoding="utf-8") as f:
            raw = json.load(f)

        for entry in raw:
            assert not ({"sha", "commit", "short"} & set(entry))
