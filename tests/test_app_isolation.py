from pathlib import Path


def test_database_path_is_isolated_under_tmp_path(app, tmp_path):
    """
    Regression test for SP-019: app.main's load_dotenv() used to run with
    override=True, which clobbered the app fixture's monkeypatched
    DATA_FOLDER back to the real local ./data directory whenever app.main
    was imported for the first time in a process after the monkeypatch ran.
    If this regresses, the test database would silently point at the real
    local data/receipts.json instead of an isolated tmp directory.
    """
    db_path = Path(app.database.file_path)
    assert db_path.parent == tmp_path
