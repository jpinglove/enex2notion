from bs4 import Tag

from enex2notion.note_parser.string_extractor import extract_string
from enex2notion.notion_blocks.header import (
    NotionHeaderBlock,
    NotionSubHeaderBlock,
    NotionSubSubHeaderBlock,
)

HEADER_MAPPING = {
    "h1": NotionHeaderBlock,
    "h2": NotionSubHeaderBlock,
    "h3": NotionSubSubHeaderBlock,
}


def parse_header(element):
    header_type = element.name

    return HEADER_MAPPING[header_type](text_prop=extract_string(element))
