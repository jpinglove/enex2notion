import io
import logging
import re
from typing import Optional

import requests

from enex2notion.enex_types import EvernoteResource
from enex2notion.notion_blocks.uploadable import NotionUploadableBlock

logger = logging.getLogger(__name__)


def upload_block(page, block):
    """Upload a block to a page using the modern Notion API."""
    client = page.get("_client")
    if not client:
        raise ValueError("No client available for block upload")
    
    # Convert our internal block representation to Notion API format
    block_data = _convert_block_to_api_format(block)
    
    try:
        # Append the block as a child to the page
        response = client.blocks.children.append(
            block_id=page["id"],
            children=[block_data]
        )
        
        # Get the created block ID for any file uploads or child blocks
        if response.get("results"):
            created_block = response["results"][0]
            
            # Handle file uploads if this is an uploadable block
            if (isinstance(block, NotionUploadableBlock) and 
                hasattr(block, 'resource') and 
                block.resource is not None):
                _upload_file_to_block(client, created_block, block.resource)
            
            # Recursively upload child blocks
            for child_block in block.children:
                child_page = {
                    "id": created_block["id"],
                    "_client": client
                }
                upload_block(child_page, child_block)
                
    except Exception as e:
        logger.error(f"Failed to upload block: {e}")
        raise


def _convert_block_to_api_format(block):
    """Convert internal block representation to Notion API format."""
    notion_type = _get_notion_block_type(block.type)
    
    api_block = {
        "object": "block",
        "type": notion_type
    }
    
    # Add type-specific content
    if notion_type in ["paragraph", "heading_1", "heading_2", "heading_3", "quote", "bulleted_list_item", "numbered_list_item", "to_do", "toggle"]:
        # These blocks use rich text
        rich_text = _convert_properties_to_rich_text(block.properties)
        api_block[notion_type] = {
            "rich_text": rich_text
        }
        
        # Add specific properties for certain types
        if notion_type == "to_do":
            api_block[notion_type]["checked"] = block.attrs.get("checked", False)
            
    elif notion_type == "code":
        rich_text = _convert_properties_to_rich_text(block.properties)
        api_block[notion_type] = {
            "rich_text": rich_text,
            "language": block.attrs.get("language", "plain text")
        }
        
    elif notion_type == "divider":
        api_block[notion_type] = {}
        
    elif notion_type in ["image", "video", "audio", "file"]:
        # File blocks need special handling - we'll set up the structure 
        # and handle the actual upload separately
        if hasattr(block, 'resource') and block.resource:
            api_block[notion_type] = {
                "type": "external",
                "external": {
                    "url": "https://via.placeholder.com/1x1.png"  # Placeholder, will be updated after upload
                }
            }
        else:
            # Handle URL-based media
            url = block.attrs.get("url", "")
            if url:
                api_block[notion_type] = {
                    "type": "external",
                    "external": {"url": url}
                }
                
    elif notion_type == "bookmark":
        url = block.attrs.get("url", "")
        api_block[notion_type] = {
            "url": url
        }
        
    elif notion_type == "embed":
        url = block.attrs.get("url", "")
        api_block[notion_type] = {
            "url": url
        }
        
    return api_block


def _convert_properties_to_rich_text(properties):
    """Convert block properties to Notion API rich text format."""
    if not properties:
        return []
    
    rich_text = []
    
    # Handle the "title" property which contains the text content
    title_properties = properties.get("title", [])
    
    for prop in title_properties:
        if isinstance(prop, list) and len(prop) >= 1:
            text_content = prop[0]
            formatting = prop[1] if len(prop) > 1 else []
            
            if text_content:  # Only add non-empty text
                text_obj = {
                    "type": "text",
                    "text": {"content": text_content}
                }
                
                # Apply formatting if present
                annotations = {}
                if formatting:
                    for format_item in formatting:
                        if isinstance(format_item, list) and len(format_item) >= 2:
                            format_type = format_item[0]
                            if format_type == "b":  # bold
                                annotations["bold"] = True
                            elif format_type == "i":  # italic
                                annotations["italic"] = True
                            elif format_type == "s":  # strikethrough
                                annotations["strikethrough"] = True
                            elif format_type == "c":  # code
                                annotations["code"] = True
                            elif format_type == "_":  # underline
                                annotations["underline"] = True
                            elif format_type == "a":  # link
                                if len(format_item) > 1:
                                    text_obj["text"]["link"] = {"url": format_item[1]}
                
                if annotations:
                    text_obj["annotations"] = annotations
                
                rich_text.append(text_obj)
        elif isinstance(prop, str):
            # Handle simple string properties
            text_obj = {
                "type": "text",
                "text": {"content": prop}
            }
            rich_text.append(text_obj)
    
    return rich_text


def _get_notion_block_type(block_type):
    """Map our block types to Notion API block types."""
    type_mapping = {
        "text": "paragraph",
        "header": "heading_1", 
        "sub_header": "heading_2",
        "sub_sub_header": "heading_3",
        "code": "code",
        "quote": "quote",
        "divider": "divider",
        "bulleted_list": "bulleted_list_item",
        "numbered_list": "numbered_list_item",
        "to_do": "to_do",
        "toggle": "toggle",
        "image": "image",
        "file": "file",
        "video": "video",
        "audio": "audio",
        "bookmark": "bookmark",
        "embed": "embed",
        "table": "table",
    }
    
    return type_mapping.get(block_type, "paragraph")


def _extract_auth_token(client) -> Optional[str]:
    """
    Best-effort extraction of the integration token from a notion-client
    instance.  Covers several SDK versions.
    """
    # 1. Public attribute on recent SDKs
    token = getattr(client, "auth", None)
    # 2. Private attributes used by older versions
    token = token or getattr(client, "_token", None) or getattr(client, "_auth", None) or getattr(client, "token", None)

    # 3. Fall back to the underlying requests.Session headers
    if not token and hasattr(client, "_session"):
        auth_header = client._session.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer "):]
    return token


def _attach_file_to_block(client, block, file_upload_id: str) -> None:
    block_type = block.get("type")
    if block_type not in {"image", "video", "audio", "file"}:
        logger.debug("Block type %s cannot carry a file upload", block_type)
        return

    payload = {
        block_type: {
            "file_upload": {"id": file_upload_id},
        }
    }
    client.blocks.update(block_id=block["id"], **payload)
    logger.debug("Attached file-upload %s to block %s", file_upload_id, block["id"])


def _upload_file_to_block(client, block, resource: EvernoteResource):
    """Upload a file to a block using the modern Notion API Direct Upload method."""
    if not resource or not resource.data_bin:
        logger.warning(f"No resource data available for upload: {resource.file_name if resource else 'unknown'}")
        return
    
    try:
        logger.info(f"Processing file: {resource.file_name} ({resource.mime}, {_sizeof_fmt(resource.size)})")
        
        # Check file size limits based on Notion's documentation
        max_size = 20 * 1024 * 1024  # 20MB for Direct Upload (single-part)
        if resource.size > max_size:
            logger.error(f"File {resource.file_name} ({_sizeof_fmt(resource.size)}) exceeds Notion's 20MB Direct Upload limit")
            logger.info("Files larger than 20MB require multi-part upload which is not yet implemented")
            return
        
        # Fetch the integration token (several SDK versions hide it differently)
        auth_token = _extract_auth_token(client)
        
        if not auth_token:
            logger.error("Unable to access auth token from Notion client")
            logger.warning(f"File upload failed for {resource.file_name}")
            logger.info(f"Leaving placeholder block for manual replacement in Notion")
            return
        
        # Perform the 3-step direct upload; receive the resulting file_upload_id
        file_upload_id = _try_direct_upload(auth_token, resource)
        if file_upload_id:
            _attach_file_to_block(client, block, file_upload_id)
            logger.info("Successfully uploaded and attached %s", resource.file_name)
            return
        
    except Exception as e:
        logger.error(f"Error processing file {resource.file_name}: {e}")


def _try_direct_upload(auth_token: str, resource: EvernoteResource) -> Optional[str]:
    """Try to upload a file using Notion's Direct Upload API (3-step process)."""
    try:
        # Step 1: Create a file upload object
        logger.debug(f"Step 1: Creating file upload object for {resource.file_name}")
        
        # Create the authorization header
        auth_header = f"Bearer {auth_token}"
        headers = {
            'Authorization': auth_header,
            'Content-Type': 'application/json',
            'Notion-Version': '2022-06-28'
        }
        
        # Create file upload object
        create_payload = {
            "filename": resource.file_name,
            "content_type": resource.mime
        }
        
        create_response = requests.post(
            'https://api.notion.com/v1/file_uploads',
            json=create_payload,
            headers=headers,
            timeout=60
        )
        
        if create_response.status_code != 200:
            logger.debug(f"File upload object creation failed: HTTP {create_response.status_code}")
            return None
            
        upload_object = create_response.json()
        file_upload_id = upload_object.get('id')
        upload_url = upload_object.get('upload_url')
        
        if not file_upload_id:
            logger.debug("No file upload ID returned from creation")
            return None
        
        logger.debug(f"Step 2: Sending file content for {resource.file_name}")
        
        # Step 2: Send the file content using multipart/form-data
        file_obj = io.BytesIO(resource.data_bin)
        file_obj.name = resource.file_name
        
        files = {
            'file': (resource.file_name, file_obj, resource.mime)
        }
        
        # Remove Content-Type header for multipart request (requests will set it automatically)
        send_headers = {
            'Authorization': auth_header,
            'Notion-Version': '2022-06-28'
        }
        
        send_response = requests.post(
            f'https://api.notion.com/v1/file_uploads/{file_upload_id}/send',
            files=files,
            headers=send_headers,
            timeout=60
        )
        
        if send_response.status_code != 200:
            logger.debug(f"File content upload failed: HTTP {send_response.status_code}")
            return None
        
        upload_result = send_response.json()
        if upload_result.get('status') != 'uploaded':
            logger.debug(f"File upload status is not 'uploaded': {upload_result.get('status')}")
            return None
        
        logger.debug(f"Step 3: Attaching file to block for {resource.file_name}")
        
        # ─── Step-3 will be executed by _attach_file_to_block ───
        logger.debug("Direct upload successful, id=%s", file_upload_id)
        return file_upload_id
            
    except Exception as e:
        logger.debug(f"Direct Upload failed for {resource.file_name}: {e}")
        
    return None


def _extract_file_id(url):
    # aws_host/space_id/file_id/filename
    aws_re = r"^https://(.*?\.amazonaws\.com)/([a-f0-9\-]+)/([a-f0-9\-]+)/(.*?)$"

    aws_match = re.search(aws_re, url)

    if not aws_match:
        raise ValueError(f"Uploaded file URL format changed: {url}")

    return aws_match.group(3)


def _sizeof_fmt(num, suffix='B'):
    """Convert bytes to human readable format."""
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"
