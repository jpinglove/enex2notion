import logging

from enex2notion.enex_types import EvernoteNote
from enex2notion.notion_blocks.uploadable import NotionUploadableBlock

logger = logging.getLogger(__name__)


def resolve_resources(note_blocks, note: EvernoteNote):
    for block in note_blocks.copy():
        # Resolve resource hash to actual resource
        if isinstance(block, NotionUploadableBlock):
            if block.resource is None:
                # This shouldn't happen with our current approach, but handle it
                logger.debug(f"Block has no resource in '{note.title}'")
                note_blocks.remove(block)
            elif block.resource.data_bin == b"":
                # This is a placeholder resource, try to resolve it
                actual_resource = note.resource_by_md5(block.resource.md5)
                if actual_resource is not None:
                    logger.debug(f"Resolved resource {block.resource.md5} in '{note.title}'")
                    block.resource = actual_resource
                else:
                    logger.warning(f"Failed to resolve resource {block.resource.md5} in '{note.title}' - removing block")
                    note_blocks.remove(block)
        
        # Recursively process child blocks
        if hasattr(block, 'children') and block.children:
            resolve_resources(block.children, note)
