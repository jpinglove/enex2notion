import logging
from datetime import datetime

from notion_client.errors import APIResponseError
from tqdm import tqdm

from enex2notion.enex_types import EvernoteNote
from enex2notion.enex_uploader_block import upload_block
from enex2notion.utils_exceptions import NoteUploadFailException

logger = logging.getLogger(__name__)

PROGRESS_BAR_WIDTH = 80


def upload_note(root, note: EvernoteNote, note_blocks, keep_failed):
    try:
        _upload_note(root, note, note_blocks, keep_failed)
    except Exception as e:
        raise NoteUploadFailException from e


def _upload_note(root, note: EvernoteNote, note_blocks, keep_failed):
    logger.debug(f"Creating new page for note '{note.title}'")
    new_page = _make_page(note, root)

    progress_iter = tqdm(
        iterable=note_blocks, unit="block", leave=False, ncols=PROGRESS_BAR_WIDTH
    )

    try:
        for block in progress_iter:
            upload_block(new_page, block)
    except APIResponseError:
        if not keep_failed:
            _delete_page(new_page)
        raise

    # Set proper name after everything is uploaded
    _update_page_title(new_page, note.title)
    _update_edit_time(new_page, note.updated)


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
    """Create a new page using the modern API."""
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
        new_page = client.pages.create(**page_data)
        new_page["_client"] = client
        new_page["_note"] = note
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
    except APIResponseError as e:
        logger.warning(f"Could not update page title: {e}")


def _delete_page(page):
    """Delete a page using the modern API."""
    try:
        client = page.get("_client")
        if client and page.get("id"):
            # Archive the page (Notion's equivalent of deletion)
            client.pages.update(
                page_id=page["id"],
                archived=True
            )
    except APIResponseError as e:
        logger.warning(f"Could not delete page: {e}")
