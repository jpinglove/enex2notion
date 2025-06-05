import hashlib
import logging
import mimetypes
import re

from bs4 import Tag

from enex2notion.enex_types import EvernoteResource
from enex2notion.notion_blocks.embeddable import NotionImageEmbedBlock
from enex2notion.notion_blocks.uploadable import (
    NotionAudioBlock,
    NotionFileBlock,
    NotionImageBlock,
    NotionPDFBlock,
    NotionVideoBlock,
)
from enex2notion.utils_notion_filetypes import (
    NOTION_AUDIO_MIMES,
    NOTION_IMAGE_MIMES,
    NOTION_VIDEO_MIMES,
)

logger = logging.getLogger(__name__)


def parse_media(element: Tag):
    type_map = {
        NOTION_IMAGE_MIMES: NotionImageBlock,
        NOTION_VIDEO_MIMES: NotionVideoBlock,
        NOTION_AUDIO_MIMES: NotionAudioBlock,
        ("application/pdf",): NotionPDFBlock,
    }

    element_type = _get_attr_as_string(element, "type")
    md5_hash = _get_attr_as_string(element, "hash")
    
    # Skip elements without valid hash
    if not md5_hash:
        logger.warning(f"Skipping media element with missing hash: {element}")
        return None
    
    for types, block_type in type_map.items():
        if element_type in types:
            return _parse_media(block_type, element)

    # For file blocks, create a placeholder resource that will be resolved later
    file_ext = mimetypes.guess_extension(element_type) or ".bin"
    placeholder_resource = EvernoteResource(
        data_bin=b"",
        size=0,
        md5=md5_hash,
        mime=element_type,
        file_name=f"{md5_hash}{file_ext}",
    )
    
    return NotionFileBlock(resource=placeholder_resource, file_name=placeholder_resource.file_name)


def parse_img(element: Tag):
    w, h = _parse_dimensions(element)
    src = _get_attr_as_string(element, "src")

    if not src.startswith("data:"):
        return NotionImageEmbedBlock(
            width=w,
            height=h,
            url=src,
        )

    try:
        img_resource = _parse_img_resource(src)
    except ValueError:
        logger.warning(f"Failed to parse image: '{src}'")
        return None

    # Make SVG small by default to avoid them spreading too much
    if "svg" in img_resource.mime and not any((w, h)):
        w, h = 50, 50

    return NotionImageBlock(
        width=w,
        height=h,
        resource=img_resource,
    )


def _get_attr_as_string(element: Tag, attr_name: str) -> str:
    """Get an attribute value as a string, handling cases where it might be a list or None."""
    value = element.get(attr_name, "")
    if isinstance(value, list):
        result = value[0] if value else ""
    else:
        result = value or ""
    
    # Handle common problematic values
    if result in ["undefined", "null", ""]:
        logger.warning(f"Invalid or missing {attr_name} attribute in media element: {result}")
        return ""
    
    return result


def _parse_img_resource(bin_src: str):
    # For now, return a placeholder since w3lib is not available
    logger.warning("Image data parsing not fully implemented")
    img_md5 = hashlib.md5(bin_src.encode()).hexdigest()
    
    return EvernoteResource(
        data_bin=b"",
        size=0,
        md5=img_md5,
        mime="image/png",
        file_name=f"{img_md5}.png",
    )


def _parse_media(block_type, element):
    # Create a placeholder resource that will be resolved later
    md5_hash = _get_attr_as_string(element, "hash")
    
    # Skip elements without valid hash
    if not md5_hash:
        logger.warning(f"Skipping media element with missing hash: {element}")
        return None
        
    mime_type = _get_attr_as_string(element, "type") or "application/octet-stream"
    file_ext = mimetypes.guess_extension(mime_type) or ".bin"
    
    placeholder_resource = EvernoteResource(
        data_bin=b"",
        size=0,
        md5=md5_hash,
        mime=mime_type,
        file_name=f"{md5_hash}{file_ext}",
    )

    block = block_type(resource=placeholder_resource)

    w, h = _parse_dimensions(element)

    # Make SVG small by default to avoid them spreading too much
    if "svg" in mime_type and not any((w, h)):
        w, h = 50, 50

    if hasattr(block, 'width'):
        block.width = w
    if hasattr(block, 'height'):
        block.height = h

    return block


def _parse_dimensions(element: Tag):
    width_str = _get_attr_as_string(element, "width")
    width_m = re.match("^([0-9]+)", width_str) if width_str else None
    width = int(width_m.group(1)) if width_m else None

    height_str = _get_attr_as_string(element, "height")
    height_m = re.match("^([0-9]+)", height_str) if height_str else None
    height = int(height_m.group(1)) if height_m else None

    return width, height
