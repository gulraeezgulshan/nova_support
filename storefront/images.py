"""Product images: content-checked uploads, ordering (first = main image) and removal."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Product, ProductImage
from src.core.storage import Storage

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGES = 5
EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


class ImageError(ValueError):
    pass


def image_type(data: bytes) -> str | None:
    """Media type from the file's first bytes (never trust the file name)."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


async def add_image(
    db: AsyncSession, product: Product, data: bytes, storage: Storage
) -> ProductImage:
    if not data:
        raise ImageError("The file is empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageError("Images must be 5 MB or smaller.")
    media_type = image_type(data)
    if media_type is None:
        raise ImageError("Only JPG, PNG and WebP images are accepted.")
    if len(product.images) >= MAX_IMAGES:
        raise ImageError(f"A product can have at most {MAX_IMAGES} images.")
    image_id = uuid.uuid4()
    key = f"products/{product.sku}/{image_id}.{EXTENSIONS[media_type]}"
    storage.put(key, data, media_type)
    image = ProductImage(
        id=image_id,
        product_id=product.id,
        storage_key=key,
        media_type=media_type,
        size_bytes=len(data),
        position=len(product.images),
    )
    product.images.append(image)
    await db.flush()
    return image


def reorder(product: Product, image_ids: list[uuid.UUID]) -> None:
    current = {image.id: image for image in product.images}
    if sorted(map(str, image_ids)) != sorted(map(str, current)):
        raise ImageError("The new order must list every image of the product exactly once.")
    for position, image_id in enumerate(image_ids):
        current[image_id].position = position
    product.images.sort(key=lambda image: image.position)


def remove(product: Product, image_id: uuid.UUID, storage: Storage) -> None:
    image = next((i for i in product.images if i.id == image_id), None)
    if image is None:
        raise LookupError("Image not found")
    product.images.remove(image)
    for position, remaining in enumerate(product.images):
        remaining.position = position
    storage.delete(image.storage_key)
