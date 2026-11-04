from pathlib import Path

import pytest

from aqman.config import get_settings


def test_get_settings_creates_default_toml_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config" / "aquarium-manager" / "config.toml"
    monkeypatch.setenv("AQMAN_CONFIG_FILE", str(config_file))
    monkeypatch.setenv("AQMAN_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("AQMAN_PORT", raising=False)

    settings = get_settings()

    assert settings.config_file == config_file
    assert settings.show_time_in_datetime_picker is False
    assert settings.activity_history_page_size == 10
    assert settings.activity_history_range_days == 365
    assert settings.port == 8080
    assert 'show_time_in_datetime_picker = false' in config_file.read_text()
    assert "activity_history_page_size = 10" in config_file.read_text()
    assert "activity_history_range_days = 365" in config_file.read_text()
    assert "port = 8080" in config_file.read_text()


def test_get_settings_uses_xdg_config_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_home = tmp_path / "xdg-config"
    monkeypatch.delenv("AQMAN_CONFIG_FILE", raising=False)
    monkeypatch.delenv("AQMAN_PORT", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setenv("AQMAN_DATA_DIR", str(tmp_path / "data"))

    settings = get_settings()

    assert settings.config_file == (
        config_home / "aquarium-manager" / "config.toml"
    )
    assert settings.config_file.is_file()


def test_get_settings_reads_show_time_from_toml(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        "[server]\nport = 8896\n\n[ui]\n"
        "show_time_in_datetime_picker = true\n"
        "activity_history_page_size = 25\n"
        "activity_history_range_days = 180\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AQMAN_CONFIG_FILE", str(config_file))
    monkeypatch.setenv("AQMAN_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("AQMAN_PORT", raising=False)

    settings = get_settings()

    assert settings.show_time_in_datetime_picker is True
    assert settings.activity_history_page_size == 25
    assert settings.activity_history_range_days == 180
    assert settings.port == 8896


def test_aqman_port_overrides_the_toml_setting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text("[server]\nport = 8896\n", encoding="utf-8")
    monkeypatch.setenv("AQMAN_CONFIG_FILE", str(config_file))
    monkeypatch.setenv("AQMAN_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("AQMAN_PORT", raising=False)
    monkeypatch.setenv("AQMAN_PORT", "9000")

    settings = get_settings()

    assert settings.port == 9000


def test_get_settings_rejects_non_boolean_show_time(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[ui]\nshow_time_in_datetime_picker = "false"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("AQMAN_CONFIG_FILE", str(config_file))
    monkeypatch.setenv("AQMAN_DATA_DIR", str(tmp_path / "data"))

    with pytest.raises(ValueError, match="show_time_in_datetime_picker"):
        get_settings()


@pytest.mark.parametrize("page_size_literal", ["0", "-1", '"10"', "true"])
def test_get_settings_rejects_invalid_activity_history_page_size(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    page_size_literal: str,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        f"[ui]\nactivity_history_page_size = {page_size_literal}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AQMAN_CONFIG_FILE", str(config_file))
    monkeypatch.setenv("AQMAN_DATA_DIR", str(tmp_path / "data"))

    with pytest.raises(ValueError, match="ui.activity_history_page_size"):
        get_settings()


@pytest.mark.parametrize("range_days_literal", ["0", "-1", '"365"', "true"])
def test_get_settings_rejects_invalid_activity_history_range_days(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    range_days_literal: str,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        f"[ui]\nactivity_history_range_days = {range_days_literal}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AQMAN_CONFIG_FILE", str(config_file))
    monkeypatch.setenv("AQMAN_DATA_DIR", str(tmp_path / "data"))

    with pytest.raises(ValueError, match="ui.activity_history_range_days"):
        get_settings()


@pytest.mark.parametrize("port_literal", ["0", "65536", '"8080"', "true"])
def test_get_settings_rejects_invalid_toml_port(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    port_literal: str,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        f"[server]\nport = {port_literal}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AQMAN_CONFIG_FILE", str(config_file))
    monkeypatch.setenv("AQMAN_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("AQMAN_PORT", raising=False)

    with pytest.raises(ValueError, match="server.port"):
        get_settings()
