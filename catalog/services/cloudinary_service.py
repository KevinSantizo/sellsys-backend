import cloudinary
import cloudinary.uploader

from django.conf import settings


cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True,
)


def upload_product_image(image_file):
    result = cloudinary.uploader.upload(
        image_file,
        folder="sellsys/products",
        resource_type="image",
    )

    return {
        "image_url": result.get(
            "secure_url"
        ),
        "image_public_id": result.get(
            "public_id"
        ),
    }