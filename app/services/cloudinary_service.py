import cloudinary
import cloudinary.uploader
from app.core.config import settings

# Configure Cloudinary
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET
)

def upload_image(file_or_path, folder="vision_pulse/images"):
    """
    Upload an image to Cloudinary.
    file_or_path: Path to the local file, or a file-like object, or a URL.
    Returns the secure URL of the uploaded image.
    """
    try:
        response = cloudinary.uploader.upload(
            file_or_path,
            folder=folder,
            resource_type="image"
        )
        return response.get("secure_url")
    except Exception as e:
        print(f"Error uploading image to Cloudinary: {e}")
        return None

def upload_video(file_or_path, folder="vision_pulse/videos"):
    """
    Upload a video to Cloudinary.
    file_or_path: Path to the local file, or a file-like object, or a URL.
    Returns the secure URL of the uploaded video.
    """
    try:
        response = cloudinary.uploader.upload(
            file_or_path,
            folder=folder,
            resource_type="video"
        )
        return response.get("secure_url")
    except Exception as e:
        print(f"Error uploading video to Cloudinary: {e}")
        return None
