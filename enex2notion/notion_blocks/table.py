from typing import Iterable

from enex2notion.notion_blocks.base import NotionBaseBlock
from enex2notion.notion_blocks.text import TextProp


class NotionTableBlock(NotionBaseBlock):
    type = "table"

    def __init__(self, width=None, has_column_header=False, has_row_header=False, **kwargs):
        super().__init__(**kwargs)

        self.attrs["table_width"] = width if width else 2
        self.attrs["has_column_header"] = has_column_header
        self.attrs["has_row_header"] = has_row_header
        self._columns = []

    def add_row(self, row: Iterable):
        t_row = NotionTableRowBlock()
        
        # For the new API, we'll store the row data directly
        if hasattr(row, '__iter__'):
            for i, cell in enumerate(row):
                if hasattr(cell, 'properties'):
                    t_row.properties[f"cell_{i}"] = cell.properties
                else:
                    t_row.properties[f"cell_{i}"] = str(cell)

        self.children.append(t_row)

    def iter_rows(self):
        """Iterate through table rows."""
        for row in self.children:
            yield row.properties


class NotionTableRowBlock(NotionBaseBlock):
    type = "table_row"


class NotionTableCellBlock(NotionBaseBlock):
    type = "table_cell"

    def __init__(self, title=None, **kwargs):
        super().__init__(**kwargs)

        if title:
            self.properties["title"] = title
