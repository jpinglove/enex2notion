import io
import logging
import re
from typing import Any, Dict, Optional

import requests

from enex2notion.enex_types import EvernoteResource
from enex2notion.notion_blocks.uploadable import NotionUploadableBlock

logger = logging.getLogger(__name__)


def upload_block(page, block):
    """Upload a block to a page using the modern Notion API."""
    client = page.get("_client")
    if not client:
        raise ValueError("No client available for block upload")
    
    # For file blocks with resources, upload the file first to get the upload ID
    file_upload_id = None
    if (isinstance(block, NotionUploadableBlock) and 
        hasattr(block, 'resource') and 
        block.resource is not None):
        
        logger.info(f"Pre-uploading file for block: {block.resource.file_name}")
        auth_token = _extract_auth_token(client)
        if auth_token:
            file_upload_id = _try_direct_upload(auth_token, block.resource)
            if file_upload_id:
                logger.debug(f"Pre-upload successful, got file ID: {file_upload_id}")
    
    # Special handling for table blocks - they need to be created with their children
    if block.type == "table":
        _upload_table_with_children(page, block, file_upload_id)
        return
    
    # Convert our internal block representation to Notion API format
    block_data = _convert_block_to_api_format(block, file_upload_id)
    
    # Debug logging to see what's being sent
    logger.debug(f"Uploading block of type: {block.type}")
    logger.debug(f"Block data: {block_data}")
    
    # Validate the block data before sending
    if not _validate_block_data(block_data):
        logger.error(f"Invalid block data: {block_data}")
        raise ValueError("Invalid block data structure")
    
    try:
        # Append the block as a child to the page
        response = client.blocks.children.append(
            block_id=page["id"],
            children=[block_data]
        )
        
        # Get the created block ID for any file uploads or child blocks
        if response.get("results"):
            created_block = response["results"][0]
            
            # File upload is already handled for blocks with file_upload_id
            # No additional file upload needed
            
            # Recursively upload child blocks with fallback to top level
            for child_block in block.children:
                try:
                    # First, try to upload as a child block
                    child_page = {
                        "id": created_block["id"],
                        "_client": client
                    }
                    upload_block(child_page, child_block)
                except Exception as e:
                    # If child upload fails due to "does not support children", 
                    # upload at the parent level instead
                    if "does not support children" in str(e).lower():
                        logger.debug(f"Block type '{created_block['type']}' doesn't support children, uploading child at parent level")
                        upload_block(page, child_block)
                    else:
                        # Re-raise other errors
                        raise
                
    except Exception as e:
        logger.error(f"Failed to upload block: {e}")
        raise


def _upload_table_with_children(page, table_block, file_upload_id=None):
    """Upload a table block with its table_row children in a single request."""
    client = page.get("_client")
    
    # Convert table block
    table_data = _convert_block_to_api_format(table_block, file_upload_id)
    
    # Convert table_row children and add them to the table's children property
    table_row_children = []
    
    for child_block in table_block.children:
        if child_block.type == "table_row":
            child_data = _convert_block_to_api_format(child_block, file_upload_id)
            table_row_children.append(child_data)
    
    # If no table_row children found, create at least one empty row
    if len(table_row_children) == 0:
        table_width = table_block.attrs.get("table_width", 2)
        empty_cells = [[{"type": "text", "text": {"content": ""}}] for _ in range(table_width)]
        empty_row = {
            "object": "block",
            "type": "table_row",
            "table_row": {
                "cells": empty_cells
            }
        }
        table_row_children.append(empty_row)
    
    # Add the table rows as children to the table block
    table_data[table_data["type"]]["children"] = table_row_children
    
    logger.debug(f"Uploading table with {len(table_row_children)} rows as children")
    logger.debug(f"Table data: {table_data}")
    
    try:
        # Upload table with its rows as children in a single request
        response = client.blocks.children.append(
            block_id=page["id"],
            children=[table_data]
        )
        
        logger.debug("Table and rows uploaded successfully")
        
    except Exception as e:
        logger.error(f"Failed to upload table with children: {e}")
        raise


def _convert_block_to_api_format(block, file_upload_id=None):
    """Convert internal block representation to Notion API format."""
    notion_type = _get_notion_block_type(block.type)
    
    api_block: Dict[str, Any] = {
        "object": "block",
        "type": notion_type
    }
    
    # Add type-specific content
    if notion_type in ["paragraph", "heading_1", "heading_2", "heading_3", "quote", "bulleted_list_item", "numbered_list_item", "to_do", "toggle"]:
        # These blocks use rich text
        rich_text = _convert_properties_to_rich_text(block.properties)
        
        # Ensure we have at least an empty rich text array
        if not rich_text:
            rich_text = [{"type": "text", "text": {"content": ""}}]
        
        api_block[notion_type] = {
            "rich_text": rich_text
        }
        
        # Add specific properties for certain types
        if notion_type == "to_do":
            api_block[notion_type]["checked"] = block.attrs.get("checked", False)
            
    elif notion_type == "code":
        rich_text = _convert_properties_to_rich_text(block.properties)
        
        # Ensure we have at least an empty rich text array
        if not rich_text:
            rich_text = [{"type": "text", "text": {"content": ""}}]
        
        api_block[notion_type] = {
            "rich_text": rich_text,
            "language": block.attrs.get("language", "plain text")
        }
        
    elif notion_type == "divider":
        api_block[notion_type] = {}
        
    elif notion_type == "table":
        # Table blocks need specific structure for Notion API
        table_width = block.attrs.get("table_width", 2)
        has_column_header = block.attrs.get("has_column_header", False)
        has_row_header = block.attrs.get("has_row_header", False)
        
        api_block[notion_type] = {
            "table_width": table_width,
            "has_column_header": has_column_header,
            "has_row_header": has_row_header
        }
        
    elif notion_type == "table_row":
        # Table row blocks contain cells with rich text
        cells = []
        
        # Extract cell data from the block's properties
        if hasattr(block, 'properties') and block.properties:
            # Look for cell properties (they are stored as cell_0, cell_1, etc.)
            cell_index = 0
            while f"cell_{cell_index}" in block.properties:
                cell_data = block.properties[f"cell_{cell_index}"]
                
                # Handle different cell data formats
                if isinstance(cell_data, str):
                    # Simple string content
                    cell_rich_text = [{"type": "text", "text": {"content": cell_data}}]
                elif isinstance(cell_data, list):
                    # Already in properties format (from TextProp)
                    cell_rich_text = _convert_properties_to_rich_text({"title": cell_data})
                else:
                    # Fallback to empty cell
                    cell_rich_text = [{"type": "text", "text": {"content": ""}}]
                
                # Ensure we have at least an empty rich text array for each cell
                if not cell_rich_text:
                    cell_rich_text = [{"type": "text", "text": {"content": ""}}]
                
                cells.append(cell_rich_text)
                cell_index += 1
        
        # If no cells found, create empty cells based on table width (default to 2)
        if not cells:
            # Default to 2 columns if we can't determine the width
            cells = [[{"type": "text", "text": {"content": ""}}] for _ in range(2)]
        
        api_block[notion_type] = {
            "cells": cells
        }
        
    elif notion_type in ["image", "video", "audio", "file", "pdf"]:
        # File blocks need special handling
        if hasattr(block, 'resource') and block.resource and file_upload_id:
            # Use the pre-uploaded file ID
            api_block[notion_type] = {
                "type": "file_upload",
                "file_upload": {"id": file_upload_id}
            }
        else:
            # Handle URL-based media or fallback to external URL
            url = block.attrs.get("url", "")
            if url and _is_valid_url(url):
                api_block[notion_type] = {
                    "type": "external",
                    "external": {"url": url}
                }
            else:
                # For file resources without successful upload, convert to paragraph
                logger.warning(f"No valid file upload or URL for {notion_type} block, converting to paragraph")
                api_block = {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": f"[File upload failed: {getattr(block.resource, 'file_name', 'unknown')}]"}}]
                    }
                }
                
    elif notion_type == "bookmark":
        url = block.attrs.get("url", "")
        if _is_valid_url(url):
            api_block[notion_type] = {
                "url": url
            }
        else:
            logger.warning(f"Invalid URL for bookmark, converting to paragraph: {url}")
            # Convert to paragraph instead
            api_block = {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": f"[Invalid bookmark: {url}]"}}]
                }
            }
        
    elif notion_type == "embed":
        url = block.attrs.get("url", "")
        if _is_valid_url(url):
            api_block[notion_type] = {
                "url": url
            }
        else:
            logger.warning(f"Invalid URL for embed, converting to paragraph: {url}")
            # Convert to paragraph instead
            api_block = {
                "object": "block", 
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": f"[Invalid embed: {url}]"}}]
                }
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
                                    url = format_item[1]
                                    if _is_valid_url(url):
                                        text_obj["text"]["link"] = {"url": url}
                                    else:
                                        logger.warning(f"Skipping invalid URL in link: {url}")
                
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
        "pdf": "pdf",
        "video": "video",
        "audio": "audio",
        "bookmark": "bookmark",
        "embed": "embed",
        "table": "table",
        "table_row": "table_row",
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
    if block_type not in {"image", "video", "audio", "file", "pdf"}:
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


def _validate_block_data(block_data):
    """Validate that block data has required structure for Notion API."""
    if not isinstance(block_data, dict):
        return False
    
    if "type" not in block_data:
        return False
    
    block_type = block_data["type"]
    
    # Check that the block type has its corresponding content
    if block_type not in block_data:
        return False
    
    # Validate rich text blocks
    if block_type in ["paragraph", "heading_1", "heading_2", "heading_3", "quote", "bulleted_list_item", "numbered_list_item", "to_do", "toggle", "code"]:
        content = block_data[block_type]
        if "rich_text" not in content:
            return False
        
        # Validate rich text structure
        for rich_text_item in content["rich_text"]:
            if not _validate_rich_text_item(rich_text_item):
                return False
    
    # Validate table blocks
    elif block_type == "table":
        content = block_data[block_type]
        if not isinstance(content, dict):
            return False
        
        # Check required table properties
        required_props = ["table_width", "has_column_header", "has_row_header"]
        for prop in required_props:
            if prop not in content:
                return False
        
        # Validate property types
        if not isinstance(content["table_width"], int) or content["table_width"] <= 0:
            return False
        if not isinstance(content["has_column_header"], bool):
            return False
        if not isinstance(content["has_row_header"], bool):
            return False
        
        # Validate children if present (for table creation with rows)
        if "children" in content:
            if not isinstance(content["children"], list):
                return False
            
            # Validate each child table_row
            for child in content["children"]:
                if not isinstance(child, dict):
                    return False
                if child.get("type") != "table_row":
                    return False
                
                # Validate table_row structure
                table_row_content = child.get("table_row", {})
                if not isinstance(table_row_content, dict):
                    return False
                
                if "cells" not in table_row_content:
                    return False
                
                cells = table_row_content["cells"]
                if not isinstance(cells, list):
                    return False
                
                # Validate each cell contains rich text
                for cell in cells:
                    if not isinstance(cell, list):
                        return False
                    
                    # Validate rich text structure in each cell
                    for rich_text_item in cell:
                        if not _validate_rich_text_item(rich_text_item):
                            return False
    
    # Validate table_row blocks
    elif block_type == "table_row":
        content = block_data[block_type]
        if not isinstance(content, dict):
            return False
        
        # Check required table_row properties
        if "cells" not in content:
            return False
        
        cells = content["cells"]
        if not isinstance(cells, list):
            return False
        
        # Validate each cell contains rich text
        for cell in cells:
            if not isinstance(cell, list):
                return False
            
            # Validate rich text structure in each cell
            for rich_text_item in cell:
                if not _validate_rich_text_item(rich_text_item):
                    return False
    
    return True


def _validate_rich_text_item(rich_text_item):
    """Validate a rich text item structure."""
    if not isinstance(rich_text_item, dict):
        return False
    
    if rich_text_item.get("type") != "text":
        return False
    
    text_obj = rich_text_item.get("text", {})
    if not isinstance(text_obj, dict):
        return False
    
    # Validate URL if present
    if "link" in text_obj:
        link_obj = text_obj["link"]
        if not isinstance(link_obj, dict):
            return False
        
        url = link_obj.get("url")
        if not _is_valid_url(url):
            logger.warning(f"Invalid URL found in link: {url}")
            return False
    
    return True


def _is_valid_url(url):
    """Validate if a URL is valid and not empty for Notion API."""
    if not url or not isinstance(url, str):
        return False
    
    # Strip whitespace
    url = url.strip()
    
    if not url:
        return False
    
    # Reject bare anchors and incomplete URLs common in web clips
    if url in ['#', '#/', '#!']:
        return False
    
    # Must be a complete URL with protocol for external links
    if url.startswith(('http://', 'https://')):
        # Basic check that it's not just the protocol
        if len(url) > 8 and '.' in url:
            return True
        return False
    
    # Allow well-formed mailto links
    if url.startswith('mailto:') and '@' in url and len(url) > 8:
        return True
    
    # Allow other protocols but be more strict
    if ':' in url and not url.startswith(('javascript:', 'data:', 'about:')):
        # Must have content after the protocol
        if len(url.split(':', 1)[1]) > 2:
            return True
    
    # For relative paths, they must have actual content and be meaningful
    if url.startswith('/') and len(url) > 1:
        return True
    
    # Reject everything else including bare anchors, incomplete fragments
    return False



