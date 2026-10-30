from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_IMAGE_SIZE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
THUMBNAIL_SIZE = (480, 320)
SUPPORTED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


class ImageValidationError(ValueError):
    pass


def create_thumbnail(data: bytes) -> bytes:
    if not data:
        raise ImageValidationError("No image was selected.")
    if len(data) > MAX_IMAGE_SIZE_BYTES:
        raise ImageValidationError("Image must be no larger than 8 MB.")

    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in SUPPORTED_IMAGE_FORMATS:
                raise ImageValidationError("Supported image formats are JPEG, PNG, and WebP.")
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise ImageValidationError("Image resolution is too large.")
            image.verify()

        with Image.open(BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image)
            if "A" in image.getbands():
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, (15, 38, 45))
                background.paste(rgba, mask=rgba.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")
            thumbnail = ImageOps.fit(image, THUMBNAIL_SIZE, method=Image.Resampling.LANCZOS)
            output = BytesIO()
            thumbnail.save(output, format="JPEG", quality=82, optimize=True)
            return output.getvalue()
    except UnidentifiedImageError as error:
        raise ImageValidationError("Could not read a valid image from the selected file.") from error
    except (OSError, Image.DecompressionBombError) as error:
        raise ImageValidationError("Could not read a valid image from the selected file.") from error
