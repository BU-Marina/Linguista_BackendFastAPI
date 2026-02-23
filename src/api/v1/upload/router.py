import os
import uuid
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, File, UploadFile, HTTPException

from utils.images import optimize_image

from .schemas import MediaResponse

router = APIRouter(prefix='/upload', tags=['upload'])


@router.post('/audio', response_model=MediaResponse)
async def upload_audio(file: UploadFile = File(...)):
    """..."""
    if not file.content_type.startswith('audio/'):
        raise HTTPException(400, 'Only audio files allowed')

    # Save file
    file_id = str(uuid.uuid4())
    file_path = f'media/audio/{file_id}.mp3'

    os.makedirs('media/audio', exist_ok=True)
    with open(file_path, 'wb') as f:
        f.write(await file.read())

    return MediaResponse(
        url=f'/media/audio/{file_id}.mp3',
        type=file.content_type,
        filename=file.filename,
        size=file.size or 0,
        uploaded_at=datetime.now(timezone.utc),
    )


ALLOWED_IMAGE_TYPES = {
    'image/jpeg',
    'image/jfif',
    'image/jpg',
    'image/png',
    'image/gif',
    'image/webp',
}


@router.post('/image', response_model=MediaResponse)
async def upload_image(
    file: UploadFile = File(...),
):
    """..."""
    # Validate content type
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail='Only image files are allowed: .jpg, .jpeg, .jfif, .png, .gif, .webp',
        )

    # Build date-based subpath: uploads/vocabulary/associations/images/YYYY/mm/dd/
    now = datetime.now(timezone.utc)
    date_subpath = now.strftime('%Y/%m/%d')
    rel_dir = f'uploads/vocabulary/associations/images/{date_subpath}'
    dir_path = os.path.join('media', rel_dir)
    os.makedirs(dir_path, exist_ok=True)

    # Generate unique filename
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    # Normalize extension (treat .jfif as .jpg so it serves reliably)
    if ext:
        ext = ext.lower()
        if ext == '.jfif':
            ext = '.jpg'
    if not ext:
        ext = '.jpg'  # fallback
    safe_filename = f'{file_id}{ext}'
    temp_file_path = os.path.join(dir_path, f'{file_id}_temp{ext}')
    file_path = os.path.join(dir_path, safe_filename)

    # Save file temporarily first
    try:
        with open(temp_file_path, 'wb') as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Failed to save image: {str(e)}')
    finally:
        file.file.close()

    # Optimize image with higher quality and reduced compression
    try:
        optimized_path, width, height = optimize_image(
            temp_file_path,
            output_path=file_path,
            max_width=4096,
            max_height=4096,
            quality=90,  # High quality (was 50 in old compress function)
            preserve_format=True,  # Keep PNG/WebP when appropriate
        )
        # Remove temp file if optimization created a new file
        if optimized_path != temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
    except Exception:
        # If optimization fails, use original file
        if os.path.exists(temp_file_path):
            if os.path.exists(file_path):
                os.remove(file_path)
            os.rename(temp_file_path, file_path)
        # Continue with original file

    # Get final file size
    final_size = (
        os.path.getsize(file_path) if os.path.exists(file_path) else (file.size or 0)
    )

    # Return response (URL path under /media/ must match rel_dir)
    return MediaResponse(
        url=f'/media/{rel_dir}/{safe_filename}',
        type=file.content_type,
        filename=file.filename,
        size=final_size,
        uploaded_at=datetime.now(timezone.utc),
    )
