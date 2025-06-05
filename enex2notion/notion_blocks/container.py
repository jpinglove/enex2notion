from enex2notion.notion_blocks.base import NotionBaseBlock


class NotionColumnListBlock(NotionBaseBlock):
    type = "column_list"


class NotionColumnBlock(NotionBaseBlock):
    type = "column"


class NotionPageBlock(NotionBaseBlock):
    type = "page"

    def __init__(self, title=None, **kwargs):
        super().__init__(**kwargs)

        if title:
            self.properties["title"] = title


class NotionToggleBlock(NotionBaseBlock):
    type = "toggle"

    def __init__(self, title=None, **kwargs):
        super().__init__(**kwargs)

        if title:
            self.properties["title"] = title
