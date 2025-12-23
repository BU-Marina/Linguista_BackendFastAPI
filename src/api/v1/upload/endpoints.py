import os
import uuid
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, File, UploadFile, HTTPException

from .schemas import MediaResponse

router = APIRouter()


@router.post("/audio", response_model=MediaResponse)
async def upload_audio(file: UploadFile = File(...)):
    """..."""
    if not file.content_type.startswith("audio/"):
        raise HTTPException(400, "Only audio files allowed")

    # Save file
    file_id = str(uuid.uuid4())
    file_path = f"media/audio/{file_id}.mp3"

    os.makedirs("media/audio", exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(await file.read())

    return MediaResponse(
        url=f"/media/audio/{file_id}.mp3",
        type=file.content_type,
        filename=file.filename,
        size=file.size or 0,
        uploaded_at=datetime.now(timezone.utc)
    )


ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/jfif",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/webp",
}


@router.post("/image", response_model=MediaResponse)
async def upload_image(
    file: UploadFile = File(...),
):
    """..."""
    # Validate content type
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only image files are allowed: .jpg, .jpeg, .jfif, .png, .gif, .webp"
        )

    # Ensure directory exists
    os.makedirs("media/images", exist_ok=True)

    # Generate unique filename
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    if not ext:
        ext = ".jpg"  # fallback
    safe_filename = f"{file_id}{ext}"
    file_path = f"media/images/{safe_filename}"

    # Save file in chunks
    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save image: {str(e)}")
    finally:
        file.file.close()

    # Return response
    return MediaResponse(
        url=f"/media/images/{safe_filename}",
        type=file.content_type,
        filename=file.filename,
        size=file.size or 0,
        uploaded_at=datetime.now(timezone.utc)
    )
