from aqman.ui.components import note_form as note_form_module
from aqman.ui.components.note_form import NoteForm
from component_ui import install_datetime_picker, install_ui


def test_note_form_values_save_callback_and_reset(monkeypatch):
    fake_ui = install_ui(monkeypatch, note_form_module)
    install_datetime_picker(monkeypatch, note_form_module)
    saved = []
    form = NoteForm("en", saved.append, show_time=False)
    form._category.value = "maintenance"
    form._content.value = "Cleaned the filter"

    values = form.values
    assert values.category == "maintenance"
    assert values.content == "Cleaned the filter"
    assert values.timestamp == form._datetime.value
    fake_ui.by_label(form._t("save_note")).on_click()
    assert saved == [form]

    form._content.value = None
    assert form.values.content == ""
    form._category.value = "maintenance"
    form._content.value = "Cleaned the filter"
    form.reset_after_save()
    assert form._category.value == ""
    assert form._content.value == ""
    assert form._datetime.value.tzinfo is not None
