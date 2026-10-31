import asyncio
import base64
from types import SimpleNamespace

import pytest

from aqman.services import ValidationError
from aqman.ui.components import aquarium_dialog as aquarium_dialog_module
from aqman.ui.components.aquarium_dialog import AquariumDialog, image_data_uri
from component_ui import install_ui


class AquariumService:
    def __init__(self, error=None):
        self.error = error
        self.created = []
        self.updated = []

    def create_aquarium(self, *args, **kwargs):
        if self.error:
            raise self.error
        self.created.append((args, kwargs))

    def update_aquarium(self, *args, **kwargs):
        if self.error:
            raise self.error
        self.updated.append((args, kwargs))


def build_dialog(monkeypatch, service):
    fake_ui = install_ui(monkeypatch, aquarium_dialog_module)
    saved = []
    errors = []
    dialog = AquariumDialog(service, "en", lambda: saved.append(True), errors.append)
    return fake_ui, dialog, saved, errors


def test_image_data_uri_encodes_data_and_preserves_content_type():
    assert image_data_uri(b"\x00\xff", "image/png") == (
        "data:image/png;base64," + base64.b64encode(b"\x00\xff").decode("ascii")
    )


def test_create_dialog_saves_values_and_closes(monkeypatch):
    service = AquariumService()
    fake_ui, dialog, saved, errors = build_dialog(monkeypatch, service)

    dialog.open()
    fake_ui.by_label(dialog._t("name")).value = "Reef"
    fake_ui.by_label(dialog._t("aquarium_volume")).value = 120
    fake_ui.by_label(dialog._t("description")).value = "Living room"
    fake_ui.by_label(dialog._t("save")).on_click()

    assert service.created == [
        (("Reef", 120, "Living room"), {"thumbnail_data": None})
    ]
    assert saved == [True]
    assert errors == []
    assert fake_ui.dialogs[0].closed
    assert fake_ui.notifications == [(dialog._t("saved_aquarium"), "positive")]


def test_create_service_validation_error_keeps_dialog_open(monkeypatch):
    failure = ValidationError("bad aquarium")
    service = AquariumService(failure)
    fake_ui, dialog, saved, errors = build_dialog(monkeypatch, service)

    dialog.open()
    fake_ui.by_label(dialog._t("save")).on_click()

    assert errors == [failure]
    assert saved == []
    assert not getattr(fake_ui.dialogs[0], "closed", False)
    assert fake_ui.notifications == []


def test_edit_dialog_uploads_photo_and_preserves_it_on_save(monkeypatch):
    service = AquariumService()
    fake_ui, dialog, saved, errors = build_dialog(monkeypatch, service)
    aquarium = SimpleNamespace(
        id=8, name="Old name", volume_liters=55, description="Old", thumbnail_data=b"old"
    )

    dialog.open(aquarium)
    upload = next(control for control in fake_ui.controls if "on_upload" in control.kwargs)

    class UploadedFile:
        content_type = "image/png"

        async def read(self):
            return b"new photo"

    asyncio.run(upload.kwargs["on_upload"](SimpleNamespace(file=UploadedFile())))

    preview = next(
        control
        for control in fake_ui.controls
        if control.source and control.source.startswith("data:")
    )
    placeholder = fake_ui.by_label(dialog._t("no_photo"))
    remove_button = fake_ui.by_label(dialog._t("remove_photo"))
    assert preview.source == image_data_uri(b"new photo", "image/png")
    assert preview.visible
    assert not placeholder.visible
    assert remove_button.visible

    fake_ui.by_label(dialog._t("save")).on_click()

    assert service.updated == [
        (
            (8, "Old name", 55, "Old"),
            {"thumbnail_data": b"new photo", "clear_thumbnail": False},
        )
    ]
    assert saved == [True]
    assert errors == []


def test_edit_dialog_removes_thumbnail_and_reports_rejected_upload(monkeypatch):
    service = AquariumService()
    fake_ui, dialog, saved, errors = build_dialog(monkeypatch, service)
    aquarium = SimpleNamespace(
        id=2, name="Reef", volume_liters=60, description="", thumbnail_data=b"photo"
    )

    dialog.open(aquarium)
    fake_ui.by_label(dialog._t("remove_photo")).on_click()
    preview = next(
        control
        for control in fake_ui.controls
        if control.source and control.source.startswith("data:")
    )
    placeholder = fake_ui.by_label(dialog._t("no_photo"))
    remove_button = fake_ui.by_label(dialog._t("remove_photo"))
    assert not preview.visible
    assert placeholder.visible
    assert not remove_button.visible

    upload = next(control for control in fake_ui.controls if "on_rejected" in control.kwargs)
    upload.kwargs["on_rejected"]()
    assert fake_ui.notifications == [(dialog._t("image_upload_rejected"), "negative")]

    fake_ui.by_label(dialog._t("save")).on_click()
    assert service.updated[0][1] == {"thumbnail_data": None, "clear_thumbnail": True}
    assert saved == [True]
    assert errors == []


def test_edit_dialog_reports_missing_aquarium(monkeypatch):
    failure = ValidationError("aquarium missing")
    service = AquariumService(failure)
    fake_ui, dialog, saved, errors = build_dialog(monkeypatch, service)
    aquarium = SimpleNamespace(
        id=2, name="Reef", volume_liters=60, description="", thumbnail_data=None
    )

    dialog.open(aquarium)
    fake_ui.by_label(dialog._t("save")).on_click()

    assert errors == [failure]
    assert saved == []
    assert not getattr(fake_ui.dialogs[0], "closed", False)
