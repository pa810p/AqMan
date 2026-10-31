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

    settings = get_settings()

    assert settings.config_file == config_file
    assert settings.show_time_in_datetime_picker is False
    assert 'show_time_in_datetime_picker = false' in config_file.read_text()


def test_get_settings_uses_xdg_config_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_home = tmp_path / "xdg-config"
    monkeypatch.delenv("AQMAN_CONFIG_FILE", raising=False)
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
        "[ui]\nshow_time_in_datetime_picker = true\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AQMAN_CONFIG_FILE", str(config_file))
    monkeypatch.setenv("AQMAN_DATA_DIR", str(tmp_path / "data"))

    settings = get_settings()

    assert settings.show_time_in_datetime_picker is True


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
