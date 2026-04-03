from qallm.analysis.analyzers.ruff import RuffAnalyzer


def test_ruff_analyzer_writes_artifact_when_tool_missing(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    ws = tmp_path / "ws"
    reports.mkdir()
    ws.mkdir()

    monkeypatch.setattr("qallm.analysis.analyzers.ruff.shutil.which", lambda _: None)

    r = RuffAnalyzer().analyze(ws, reports)

    assert r.tool == "ruff"
    assert r.exit_code == 127
    assert (reports / "ruff.json").exists()


def test_ruff_analyzer_writes_stdout_to_json(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    ws = tmp_path / "ws"
    reports.mkdir()
    ws.mkdir()

    monkeypatch.setattr("qallm.analysis.analyzers.ruff.shutil.which", lambda _: "/usr/bin/ruff")

    class Dummy:
        exit_code = 0
        stdout = "[]"
        stderr = ""

    monkeypatch.setattr("qallm.analysis.analyzers.ruff.run_cmd", lambda *args, **kwargs: Dummy())

    r = RuffAnalyzer().analyze(ws, reports)
    assert r.exit_code == 0
    assert (reports / "ruff.json").read_text(encoding="utf-8").strip() == "[]"


def test_ruff_tool_name():
    assert RuffAnalyzer().tool_name() == "ruff"


def test_ruff_nonzero_exit_preserved(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    ws = tmp_path / "ws"
    reports.mkdir()
    ws.mkdir()

    monkeypatch.setattr("qallm.analysis.analyzers.ruff.shutil.which", lambda _: "/usr/bin/ruff")

    class Dummy:
        exit_code = 1
        stdout = "[]"
        stderr = "ruff error"

    monkeypatch.setattr("qallm.analysis.analyzers.ruff.run_cmd", lambda *args, **kwargs: Dummy())

    r = RuffAnalyzer().analyze(ws, reports)
    assert r.exit_code == 1
    assert r.stderr == "ruff error"


def test_ruff_artifact_field(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    ws = tmp_path / "ws"
    reports.mkdir()
    ws.mkdir()

    monkeypatch.setattr("qallm.analysis.analyzers.ruff.shutil.which", lambda _: "/usr/bin/ruff")

    class Dummy:
        exit_code = 0
        stdout = "[]"
        stderr = ""

    monkeypatch.setattr("qallm.analysis.analyzers.ruff.run_cmd", lambda *args, **kwargs: Dummy())

    r = RuffAnalyzer().analyze(ws, reports)
    assert r.artifact == "ruff.json"
    assert r.tool == "ruff"
