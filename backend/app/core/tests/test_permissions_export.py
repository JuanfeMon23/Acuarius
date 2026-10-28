"""El contrato de tags commiteado para el frontend coincide con el catalogo."""

from app.core import permissions_export as export


def test_committed_json_matches_catalog():
    assert export.is_aligned(), (
        "tags desalineados: ejecuta uv run python -m app.core.permissions_export"
    )


def test_check_flag_reports_misalignment(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(export, "OUTPUT", tmp_path / "permissions.json")
    assert export.main(["--check"]) == 1
    assert "tags desalineados" in capsys.readouterr().out
    assert export.main([]) == 0
    assert export.main(["--check"]) == 0


def test_events_are_not_assignable():
    actions = {
        a["tag"]: a["assignable"]
        for m in export.build_contract()["modules"]
        for a in m["actions"]
    }
    assert actions["acuarius.settings.update"] is False
    assert actions["acuarius.account.activate"] is False
    assert actions["acuarius.results.view"] is True
    assert sum(actions.values()) == 9
