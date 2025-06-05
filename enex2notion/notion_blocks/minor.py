from enex2notion.notion_blocks.base import NotionBaseBlock


class NotionDividerBlock(NotionBaseBlock):
    type = "divider"


class NotionBookmarkBlock(NotionBaseBlock):
    type = "bookmark"

    def __init__(self, url, **kwargs):
        super().__init__(**kwargs)

        self.attrs["link"] = url


class NotionEquationBlock(NotionBaseBlock):
    type = "equation"

    def __init__(self, title=None, **kwargs):
        super().__init__(**kwargs)

        if title:
            self.properties["title"] = title
