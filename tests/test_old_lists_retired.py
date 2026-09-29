"""The parallel, index-coupled lists that #18 replaced with the Channel registry must stay gone."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_SOURCES = sorted((REPO_ROOT / "datalogger_client").rglob("*.py"))


def test_no_source_still_has_the_old_lists_or_their_names():
    assert PACKAGE_SOURCES
    for source in PACKAGE_SOURCES:
        text = source.read_text(encoding="utf-8")
        for old_name in ("historico_leituras", "parametros = [", "self.addresses", "leitura"):
            assert old_name not in text, f"{old_name!r} found in {source.name}"


def test_the_channel_tables_of_the_old_layers_are_gone():
    assert not (REPO_ROOT / "datalogger_client" / "io_layer" / "channels.py").exists()
    assert not (REPO_ROOT / "datalogger_client" / "io_layer" / "snapshot.py").exists()
