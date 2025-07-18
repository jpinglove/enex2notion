import logging
import re

from bs4 import Tag

from enex2notion.note_parser.string_extractor import extract_string
from enex2notion.notion_blocks.list import NotionTodoBlock
from enex2notion.notion_blocks.minor import NotionBookmarkBlock
from enex2notion.notion_blocks.text import NotionCodeBlock, NotionTextBlock

logger = logging.getLogger(__name__)


def parse_div(element: Tag):
    style = element.get("style", "")
    if not isinstance(style, str):
        style = ""

    # Tasks, skipping those
    if "en-task-group" in style:
        logger.debug("Skipping task block")
        return None

    # Google drive links
    if "en-richlink" in style:
        return parse_richlink(element)

    # Code blocks
    if "en-codeblock" in style:
        return parse_codeblock(element)

    # Text paragraph
    return parse_text(element)


def parse_codeblock(element: Tag):
    return NotionCodeBlock(text_prop=extract_string(element))


def parse_text(element: Tag):
    element_text = extract_string(element)

    todo = element.find("en-todo")
    if todo and isinstance(todo, Tag):
        is_checked = todo.get("checked") == "true"
        return NotionTodoBlock(text_prop=element_text, checked=is_checked)

    return NotionTextBlock(text_prop=element_text)


def parse_richlink(element: Tag):
    style = element.get("style", "")
    if isinstance(style, str):
        match = re.match(".*en-href:(.*?);", style)
        if match:
            url = match.group(1).strip()
            return NotionBookmarkBlock(url=url)
    return None
