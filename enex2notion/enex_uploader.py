import logging
import threading
from datetime import datetime

from notion_client.errors import APIResponseError
from tqdm import tqdm

from enex2notion.enex_types import EvernoteNote
from enex2notion.enex_uploader_block import upload_blocks_batch
from enex2notion.utils_exceptions import NoteUploadFailException

logger = logging.getLogger(__name__)

PROGRESS_BAR_WIDTH = 80

# Global lock for page creation to prevent conflicts on parent pages
_page_creation_lock = threading.Lock()


def upload_note(root, note: EvernoteNote, note_blocks, keep_failed):
    try:
        _upload_note(root, note, note_blocks, keep_failed)
    except Exception as e:
        raise NoteUploadFailException from e


def _upload_note(root, note: EvernoteNote, note_blocks, keep_failed):
    logger.debug(f"Looking for existing incomplete upload for note '{note.title}'")
    
    # First, try to find existing "[UNFINISHED UPLOAD]" page
    existing_page = _find_existing_unfinished_page(root, note)
    
    if existing_page:
        logger.info(f"Found existing incomplete upload for note '{note.title}', resuming...")
        new_page = existing_page
        
        # Clear existing blocks from the page to avoid partial upload issues
        try:
            _clear_page_blocks(new_page)
            logger.debug(f"Cleared existing blocks from incomplete page for note '{note.title}'")
        except Exception as e:
            logger.warning(f"Failed to clear existing blocks, will try to continue: {e}")
    else:
        logger.debug(f"Creating new page for note '{note.title}'")
        new_page = _make_page(note, root)

    try:
        _upload_note_blocks(new_page, note_blocks)
        
    except APIResponseError:
        if not keep_failed:
            _delete_page(new_page)
        raise

    # Set proper name after everything is uploaded
    _update_page_title(new_page, note.title)
    _update_edit_time(new_page, note.updated)


def _find_existing_unfinished_page(root, note: EvernoteNote):
    """Find existing [UNFINISHED UPLOAD] page for this note."""
    try:
        client = root.get("_client")
        if not client:
            return None
        
        # Search for pages with "[UNFINISHED UPLOAD]" in the title
        unfinished_title = f"{note.title} [UNFINISHED UPLOAD]"
        
        search_result = client.search(
            query=unfinished_title,
            filter={
                "value": "page", 
                "property": "object"
            }
        )
        
        # Look for exact match
        for result in search_result.get("results", []):
            if result.get("object") == "page":
                page_title = ""
                if "properties" in result and "title" in result["properties"]:
                    title_prop = result["properties"]["title"]
                    if title_prop.get("type") == "title" and title_prop.get("title"):
                        page_title = "".join([
                            t.get("plain_text", "") for t in title_prop["title"]
                        ])
                
                # Check if this is the exact unfinished page we're looking for
                if page_title == unfinished_title:
                    # Verify it's under the correct parent
                    parent = result.get("parent", {})
                    if parent.get("type") == "page_id" and parent.get("page_id") == root.get("id"):
                        result["_client"] = client
                        result["_note"] = note
                        logger.debug(f"Found existing unfinished page: {page_title}")
                        return result
        
        return None
        
    except Exception as e:
        logger.warning(f"Failed to search for existing unfinished page: {e}")
        return None


def _clear_page_blocks(page):
    """Clear all blocks from a page to prepare for re-upload."""
    try:
        client = page.get("_client")
        if not client or not page.get("id"):
            return
        
        # Get all blocks from the page
        blocks_response = client.blocks.children.list(block_id=page["id"])
        blocks = blocks_response.get("results", [])
        
        # Delete all blocks
        for block in blocks:
            try:
                client.blocks.delete(block_id=block["id"])
            except APIResponseError as e:
                logger.warning(f"Failed to delete block {block.get('id', 'unknown')}: {e}")
        
        logger.debug(f"Cleared {len(blocks)} blocks from page")
        
    except Exception as e:
        logger.warning(f"Failed to clear page blocks: {e}")
        raise


def _update_edit_time(page, date):
    """Update the last edited time of a page using the modern API."""
    try:
        client = page.get("_client")
        if client and page.get("id"):
            # The modern API doesn't allow direct manipulation of last_edited_time
            # This is handled automatically by Notion
            pass
    except Exception as e:
        logger.warning(f"Could not update edit time: {e}")


def _make_page(note, root):
    """Create a new page using the modern API with synchronized page creation."""
    # Use global lock to serialize page creation and prevent conflicts on parent page
    with _page_creation_lock:
        client = root.get("_client")
        
        if not client:
            raise ValueError("No client available for page creation")
        
        # Handle the case where we need to create the root page first
        if root.get("_needs_creation"):
            # Create a new page at the top level
            # For the modern API, we need to specify a parent
            # We'll create it as a standalone page for now
            tmp_name = f"{root.get('_title', 'Import Root')} [UNFINISHED UPLOAD]"
            
            # Since we can't create top-level pages directly, we need the user to 
            # specify a parent page or database. For now, we'll raise an error with instructions.
            raise ValueError(
                "The modern Notion API requires a parent page or database to create new pages. "
                "Please create a page in Notion, share it with your integration, and specify "
                "it using the --pageid option."
            )
        
        # Create a child page under the root
        tmp_name = f"{note.title} [UNFINISHED UPLOAD]"
        
        page_data = {
            "parent": {"page_id": root["id"]},
            "properties": {
                "title": {
                    "title": [
                        {
                            "text": {
                                "content": tmp_name
                            }
                        }
                    ]
                }
            },
            "children": []  # We'll add blocks later
        }
        
        try:
            logger.debug(f"Creating page for note '{note.title}' (with lock)")
            new_page = client.pages.create(**page_data)
            new_page["_client"] = client
            new_page["_note"] = note
            logger.debug(f"Successfully created page for note '{note.title}'")
            return new_page
        except APIResponseError as e:
            logger.error(f"Failed to create page: {e}")
            raise


def _update_page_title(page, title):
    """Update the page title using the modern API."""
    try:
        client = page.get("_client")
        if client and page.get("id"):
            client.pages.update(
                page_id=page["id"],
                properties={
                    "title": {
                        "title": [
                            {
                                "text": {
                                    "content": title
                                }
                            }
                        ]
                    }
                }
            )
            logger.debug(f"Updated page title from '[UNFINISHED UPLOAD]' to '{title}'")
    except APIResponseError as e:
        logger.warning(f"Could not update page title: {e}")


def _delete_page(page):
    """Delete a page using the modern API with better error handling."""
    try:
        client = page.get("_client")
        if client and page.get("id"):
            # Archive the page (Notion's equivalent of deletion)
            client.pages.update(
                page_id=page["id"],
                archived=True
            )
            logger.debug(f"Successfully archived failed page")
    except APIResponseError as e:
        logger.error(f"Failed to delete page: {e}")
        # Re-raise to ensure the caller knows deletion failed
        raise


def _upload_note_blocks(page, note_blocks):
    """Upload blocks to an existing page using batched approach."""
    logger.info(f"Uploading {len(note_blocks)} blocks using batched approach")
    
    # Show progress with real-time updates as batches are uploaded
    with tqdm(total=len(note_blocks), unit="block", leave=False, ncols=PROGRESS_BAR_WIDTH, desc="Uploading blocks") as pbar:
        def progress_callback(num_processed):
            pbar.update(num_processed)
        
        # Use sequential batched upload to avoid page conflicts
        upload_blocks_batch(page, note_blocks, progress_callback)
