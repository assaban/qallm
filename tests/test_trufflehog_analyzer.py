from qallm.analysis.analyzers.trufflehog import TruffleHogAnalyzer


def test_trufflehog_analyzer_writes_artifact_when_tool_missing(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    ws = tmp_path / "ws"
    reports.mkdir()
    ws.mkdir()

    monkeypatch.setattr("qallm.analysis.analyzers.trufflehog.shutil.which", lambda _: None)

    r = TruffleHogAnalyzer().analyze(ws, reports)

    assert r.tool == "trufflehog"
    assert r.exit_code == 127
    assert (reports / "trufflehog.jsonl").exists()


def test_trufflehog_analyzer_uses_run_cmd_and_writes_file(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    ws = tmp_path / "ws"
    reports.mkdir()
    ws.mkdir()

    monkeypatch.setattr("qallm.analysis.analyzers.trufflehog.shutil.which", lambda _: "/usr/local/bin/trufflehog")

    class Dummy:
        exit_code = 0
        stdout = '{"DetectorName":"AWS"}\n'
        stderr = ""

    def fake_run_cmd(cmd, cwd, timeout_sec=180):
        return Dummy()

    monkeypatch.setattr("qallm.analysis.analyzers.trufflehog.run_cmd", fake_run_cmd)

    r = TruffleHogAnalyzer().analyze(ws, reports)
    assert r.exit_code == 0
    assert (reports / "trufflehog.jsonl").exists()
    assert "AWS" in (reports / "trufflehog.jsonl").read_text()


def test_trufflehog_tool_name():
    assert TruffleHogAnalyzer().tool_name() == "trufflehog"


def test_trufflehog_nonzero_exit_preserved(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    ws = tmp_path / "ws"
    reports.mkdir()
    ws.mkdir()

    monkeypatch.setattr("qallm.analysis.analyzers.trufflehog.shutil.which", lambda _: "/usr/local/bin/trufflehog")

    class Dummy:
        exit_code = 183
        stdout = ""
        stderr = "trufflehog error"

    monkeypatch.setattr("qallm.analysis.analyzers.trufflehog.run_cmd", lambda *args, **kwargs: Dummy())

    r = TruffleHogAnalyzer().analyze(ws, reports)
    assert r.exit_code == 183
    assert r.stderr == "trufflehog error"


def test_trufflehog_artifact_field(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    ws = tmp_path / "ws"
    reports.mkdir()
    ws.mkdir()

    monkeypatch.setattr("qallm.analysis.analyzers.trufflehog.shutil.which", lambda _: "/usr/local/bin/trufflehog")

    class Dummy:
        exit_code = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr("qallm.analysis.analyzers.trufflehog.run_cmd", lambda *args, **kwargs: Dummy())

    r = TruffleHogAnalyzer().analyze(ws, reports)
    assert r.artifact == "trufflehog.jsonl"
    assert r.tool == "trufflehog"
