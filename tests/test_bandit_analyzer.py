from qallm.analysis.analyzers.bandit import BanditAnalyzer


def test_bandit_analyzer_writes_artifact_when_tool_missing(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    ws = tmp_path / "ws"
    reports.mkdir()
    ws.mkdir()

    monkeypatch.setattr("qallm.analysis.analyzers.bandit.shutil.which", lambda _: None)

    r = BanditAnalyzer().analyze(ws, reports)

    assert r.tool == "bandit"
    assert r.exit_code == 127
    assert (reports / "bandit.json").exists()


def test_bandit_analyzer_uses_run_cmd_and_writes_file(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    ws = tmp_path / "ws"
    reports.mkdir()
    ws.mkdir()

    monkeypatch.setattr("qallm.analysis.analyzers.bandit.shutil.which", lambda _: "/usr/bin/bandit")

    class Dummy:
        exit_code = 0
        stdout = ""
        stderr = ""

    def fake_run_cmd(cmd, cwd, timeout_sec=120):
        # Bandit writes via -o, so our analyzer should ensure file exists
        return Dummy()

    monkeypatch.setattr("qallm.analysis.analyzers.bandit.run_cmd", fake_run_cmd)

    r = BanditAnalyzer().analyze(ws, reports)
    assert r.exit_code == 0
    assert (reports / "bandit.json").exists()


def test_bandit_tool_name():
    assert BanditAnalyzer().tool_name() == "bandit"


def test_bandit_nonzero_exit_preserved(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    ws = tmp_path / "ws"
    reports.mkdir()
    ws.mkdir()

    monkeypatch.setattr("qallm.analysis.analyzers.bandit.shutil.which", lambda _: "/usr/bin/bandit")

    class Dummy:
        exit_code = 1
        stdout = ""
        stderr = "some bandit warning"

    monkeypatch.setattr("qallm.analysis.analyzers.bandit.run_cmd", lambda *args, **kwargs: Dummy())

    r = BanditAnalyzer().analyze(ws, reports)
    assert r.exit_code == 1
    assert r.stderr == "some bandit warning"


def test_bandit_artifact_field(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    ws = tmp_path / "ws"
    reports.mkdir()
    ws.mkdir()

    monkeypatch.setattr("qallm.analysis.analyzers.bandit.shutil.which", lambda _: "/usr/bin/bandit")

    class Dummy:
        exit_code = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr("qallm.analysis.analyzers.bandit.run_cmd", lambda *args, **kwargs: Dummy())

    r = BanditAnalyzer().analyze(ws, reports)
    assert r.artifact == "bandit.json"
    assert r.tool == "bandit"
