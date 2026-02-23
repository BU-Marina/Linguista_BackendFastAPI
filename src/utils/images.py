"""..."""

import shutil
from pathlib import Path
from pydantic import AnyUrl

try:
    from PIL import Image, UnidentifiedImageError

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    UnidentifiedImageError = Exception


def _coerce_url(val):
    """..."""
    if val is None:
        return None

    # если это pydantic AnyUrl — привести к строке
    if isinstance(val, AnyUrl):
        return str(val)

    return val


def optimize_image(
    input_path: str | Path,
    output_path: str | Path | None = None,
    max_width: int = 4096,
    max_height: int = 4096,
    quality: int = 90,
    preserve_format: bool = True,
) -> tuple[str, int, int]:
    """
    Optimize image with higher quality and reduced compression.

    Args:
        input_path: Path to input image file
        output_path: Path to save optimized image (if None, overwrites input)
        max_width: Maximum width (resize if larger)
        max_height: Maximum height (resize if larger)
        quality: JPEG/WebP quality (1-100, higher = better quality)
        preserve_format: If True, keep original format when possible

    Returns:
        Tuple of (output_path, width, height)
    """
    if not PIL_AVAILABLE:
        # If PIL not available, just copy the file without optimization
        if output_path is None:
            output_path = input_path
        else:
            # Just copy the file if PIL is not available
            shutil.copy2(input_path, output_path)
        # Return 0,0 for dimensions since we can't determine without PIL
        return str(output_path), 0, 0

    try:
        img = Image.open(input_path)
    except (UnidentifiedImageError, OSError):
        # If image can't be opened, return original
        if output_path is None:
            output_path = input_path
        return str(output_path), 0, 0

    original_format = img.format
    width, height = img.size

    # Resize if image is too large
    if width > max_width or height > max_height:
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        width, height = img.size

    # Determine output format
    if output_path is None:
        output_path = input_path
    else:
        output_path = Path(output_path)

    output_path = Path(output_path)
    output_format = original_format if preserve_format else 'JPEG'

    # Preserve transparency for PNG/WebP
    if original_format in ('PNG', 'WEBP') and preserve_format:
        if img.mode in ('RGBA', 'LA', 'P'):
            # Keep transparency
            save_kwargs = {'format': output_format}
            if output_format == 'PNG':
                save_kwargs['optimize'] = True
                save_kwargs['compress_level'] = 6  # 0-9, 6 is good balance
            elif output_format == 'WEBP':
                save_kwargs['quality'] = quality
                save_kwargs['method'] = 6  # 0-6, 6 is best quality
        else:
            # No transparency, can convert to RGB
            if img.mode != 'RGB':
                img = img.convert('RGB')
            save_kwargs = {'format': output_format}
            if output_format == 'JPEG':
                save_kwargs['quality'] = quality
                save_kwargs['optimize'] = True
            elif output_format == 'WEBP':
                save_kwargs['quality'] = quality
                save_kwargs['method'] = 6
    else:
        # Convert to RGB for JPEG or if not preserving format
        if img.mode != 'RGB':
            img = img.convert('RGB')
        output_format = 'JPEG'
        save_kwargs = {
            'format': output_format,
            'quality': quality,
            'optimize': True,
        }
        # Update extension if format changed
        if output_path.suffix.lower() not in ('.jpg', '.jpeg'):
            output_path = output_path.with_suffix('.jpg')

    # Save optimized image
    img.save(output_path, **save_kwargs)
    img.close()

    return str(output_path), width, height
