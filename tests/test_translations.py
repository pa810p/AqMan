from aqman.translations import LANGUAGE_NAMES, TRANSLATIONS, translate


def test_all_languages_have_the_same_translation_keys() -> None:
    assert set(LANGUAGE_NAMES) == set(TRANSLATIONS)
    assert set(TRANSLATIONS["en"]) == set(TRANSLATIONS["pl"])


def test_translations_format_dynamic_values() -> None:
    assert translate("en", "volume", volume=120) == "Volume: 120 L"
    assert translate("pl", "volume", volume=120) == "Objętość: 120 l"
    assert translate("en", "history_water_change_entry", source="RO", volume=20) == "RO: 20 L"
    assert translate("pl", "history_water_change_entry", source="RO", volume=20) == "RO: 20 l"
