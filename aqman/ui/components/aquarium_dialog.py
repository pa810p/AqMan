from __future__ import annotations

import base64
from collections.abc import Callable

from nicegui import ui
from nicegui.events import UploadEventArguments

from aqman.images import MAX_IMAGE_SIZE_BYTES
from aqman.models import Aquarium
from aqman.services import AquariumService, NotFoundError, ValidationError
from aqman.translations import translate


def image_data_uri(data: bytes, content_type: str = "image/jpeg") -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


class AquariumDialog:
    def __init__(
        self,
        aquarium_service: AquariumService,
        language: str,
        on_saved: Callable[[], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        self._aquarium_service = aquarium_service
        self._language = language
        self._on_saved = on_saved
        self._on_error = on_error

    def open(self, aquarium: Aquarium | None = None) -> None:
        thumbnail_data = aquarium.thumbnail_data if aquarium else None
        thumbnail_changed = False

        with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg"):
            ui.label(
                self._t("edit_aquarium_dialog")
                if aquarium
                else self._t("add_aquarium_dialog")
            ).classes("text-h6")
            name_input = ui.input(
                self._t("name"),
                value=aquarium.name if aquarium else "",
            ).classes("w-full")
            volume_input = ui.number(
                self._t("aquarium_volume"),
                value=aquarium.volume_liters if aquarium else None,
                min=0,
            ).classes("w-full")
            description_input = ui.textarea(
                self._t("description"),
                value=aquarium.description if aquarium else "",
            ).classes("w-full")

            ui.label(self._t("aquarium_photo")).classes("text-subtitle1")
            image_preview = ui.image("").classes("w-full h-48 rounded-lg object-cover")
            image_preview.set_visibility(thumbnail_data is not None)
            image_placeholder = ui.label(self._t("no_photo")).classes("text-body2")
            image_placeholder.set_visibility(thumbnail_data is None)
            if thumbnail_data is not None:
                image_preview.set_source(image_data_uri(thumbnail_data))

            async def receive_image(event: UploadEventArguments) -> None:
                nonlocal thumbnail_data, thumbnail_changed
                thumbnail_data = await event.file.read()
                thumbnail_changed = True
                image_preview.set_source(
                    image_data_uri(
                        thumbnail_data,
                        event.file.content_type or "image/jpeg",
                    )
                )
                image_preview.set_visibility(True)
                image_placeholder.set_visibility(False)
                remove_photo_button.set_visibility(True)

            def remove_thumbnail() -> None:
                nonlocal thumbnail_data, thumbnail_changed
                thumbnail_data = None
                thumbnail_changed = True
                image_preview.set_visibility(False)
                image_placeholder.set_visibility(True)
                remove_photo_button.set_visibility(False)

            ui.upload(
                label=self._t("upload_photo"),
                auto_upload=True,
                max_file_size=MAX_IMAGE_SIZE_BYTES,
                on_upload=receive_image,
                on_rejected=lambda: ui.notify(
                    self._t("image_upload_rejected"),
                    type="negative",
                ),
            ).props('accept=".jpg,.jpeg,.png,.webp"').classes("w-full")
            remove_photo_button = ui.button(
                self._t("remove_photo"),
                icon="delete",
                on_click=remove_thumbnail,
            ).props("flat")
            remove_photo_button.set_visibility(thumbnail_data is not None)

            def save() -> None:
                try:
                    if aquarium is None:
                        self._aquarium_service.create_aquarium(
                            name_input.value or "",
                            volume_input.value,
                            description_input.value,
                            thumbnail_data=(
                                thumbnail_data if thumbnail_changed else None
                            ),
                        )
                    else:
                        self._aquarium_service.update_aquarium(
                            aquarium.id,
                            name_input.value or "",
                            volume_input.value,
                            description_input.value,
                            thumbnail_data=(
                                thumbnail_data if thumbnail_changed else None
                            ),
                            clear_thumbnail=(
                                thumbnail_changed and thumbnail_data is None
                            ),
                        )
                except (ValidationError, NotFoundError) as error:
                    self._on_error(error)
                    return
                dialog.close()
                ui.notify(self._t("saved_aquarium"), type="positive")
                self._on_saved()

            with ui.row().classes("justify-end"):
                ui.button(self._t("cancel"), on_click=dialog.close).props("flat")
                ui.button(self._t("save"), on_click=save, icon="save")
        dialog.open()

    def _t(self, key: str) -> str:
        return translate(self._language, key)
