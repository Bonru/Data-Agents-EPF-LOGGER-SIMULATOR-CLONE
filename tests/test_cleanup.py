"""The migration's leftovers stay deleted, the launcher still starts both programs, and the docs say so."""
import importlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Written in pieces so that this file does not contain the names it forbids.
OLD_HANDLER = "ModbusClient" + "Handler"
OLD_CLIENT_MODULE = "Pymodbus" + "_cliente"
OLD_ADAPTER_NAMES = ("compatibility" + "_adapter", "Compatibility" + "Adapter", "ui" + ".adapter")

# Out of scope for the whole effort: never edited, so they may still mention what was deleted.
OUT_OF_SCOPE = ("interface_teste.py", "measure.py", "Testes", "web_view", "samples", ".git", ".scratch")


def repository_sources():
    for path in sorted(REPO_ROOT.rglob("*")):
        relative = path.relative_to(REPO_ROOT)
        if relative.parts[0] in OUT_OF_SCOPE or "__pycache__" in relative.parts or ".pytest_cache" in relative.parts:
            continue
        if path.is_file() and path.suffix in {".py", ".md", ".ini", ".json"} and path != Path(__file__).resolve():
            yield path


# --- nothing left of the old handler or the adapter -------------------------------------------------------


def test_the_old_handler_module_and_the_adapter_are_gone():
    assert not (REPO_ROOT / (OLD_CLIENT_MODULE + ".py")).exists()
    assert not (REPO_ROOT / "datalogger_client" / "ui" / "adapter.py").exists()
    assert not list((REPO_ROOT / "tests").glob("test_compat*"))


def test_no_source_or_doc_mentions_the_old_handler_or_the_adapter():
    sources = list(repository_sources())
    assert sources
    for path in sources:
        text = path.read_text(encoding="utf-8")
        for old_name in (OLD_HANDLER, OLD_CLIENT_MODULE, *OLD_ADAPTER_NAMES):
            assert old_name not in text, f"{old_name!r} found in {path.relative_to(REPO_ROOT)}"


def test_the_package_never_imports_the_top_level_scripts_or_the_deleted_module():
    for path in (REPO_ROOT / "datalogger_client").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for forbidden in ("import measure", "from measure", "import Pymodbus_Server", "from Pymodbus_Server"):
            assert forbidden not in text, f"{forbidden!r} found in {path.name}"


# --- the application still launches -----------------------------------------------------------------------


def test_the_launcher_starts_the_ui_and_the_simulator_and_both_scripts_exist(monkeypatch):
    launcher = importlib.import_module("execucao_simultanea")
    started = []

    class FakeProcess:
        returncode = 0

        def __init__(self, command):
            started.append(Path(command[1]).name)

        def wait(self):
            return 0

        def poll(self):
            return 0

        def terminate(self):
            pass

    monkeypatch.setattr(launcher.subprocess, "Popen", FakeProcess)

    assert launcher.main() == 0
    assert started == ["main.py", "Pymodbus_Server.py"]
    for script in started:
        assert (REPO_ROOT / script).is_file()


# --- the docs ---------------------------------------------------------------------------------------------


def test_the_readme_links_the_architecture_decision_record():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    adr = "docs/adr/0001-worker-thread-and-immutable-frames.md"
    assert f"]({adr})" in readme
    assert (REPO_ROOT / adr).is_file()


def test_the_glossary_has_no_client_side_naming_drift_but_keeps_the_simulators():
    glossary = (REPO_ROOT / "CONTEXT.md").read_text(encoding="utf-8")

    assert "historico_leituras" not in glossary
    assert "Pymodbus_Server.py`) still uses `leitura`" in glossary
