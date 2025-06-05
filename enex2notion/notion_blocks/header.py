from enex2notion.notion_blocks.base import NotionBaseBlock
from enex2notion.notion_blocks.text import TextProp


class NotionHeaderBlock(NotionBaseBlock):
    type = "header"

    def __init__(self, title=None, text_prop=None, **kwargs):
        super().__init__(**kwargs)

        if text_prop:
            self.properties["title"] = text_prop.properties
        elif title:
            self.properties["title"] = title

    @property
    def text_prop(self):
        if "title" in self.properties:
            # Extract text from properties
            text = ""
            for prop in self.properties["title"]:
                if isinstance(prop, list) and len(prop) > 0:
                    text += prop[0]
            return TextProp(text=text, properties=self.properties["title"])
        return TextProp(text="", properties=[])

    @text_prop.setter
    def text_prop(self, text_prop):
        self.properties["title"] = text_prop.properties


class NotionSubHeaderBlock(NotionBaseBlock):
    type = "sub_header"

    def __init__(self, title=None, text_prop=None, **kwargs):
        super().__init__(**kwargs)

        if text_prop:
            self.properties["title"] = text_prop.properties
        elif title:
            self.properties["title"] = title

    @property
    def text_prop(self):
        if "title" in self.properties:
            # Extract text from properties
            text = ""
            for prop in self.properties["title"]:
                if isinstance(prop, list) and len(prop) > 0:
                    text += prop[0]
            return TextProp(text=text, properties=self.properties["title"])
        return TextProp(text="", properties=[])

    @text_prop.setter
    def text_prop(self, text_prop):
        self.properties["title"] = text_prop.properties


class NotionSubSubHeaderBlock(NotionBaseBlock):
    type = "sub_sub_header"

    def __init__(self, title=None, text_prop=None, **kwargs):
        super().__init__(**kwargs)

        if text_prop:
            self.properties["title"] = text_prop.properties
        elif title:
            self.properties["title"] = title

    @property
    def text_prop(self):
        if "title" in self.properties:
            # Extract text from properties
            text = ""
            for prop in self.properties["title"]:
                if isinstance(prop, list) and len(prop) > 0:
                    text += prop[0]
            return TextProp(text=text, properties=self.properties["title"])
        return TextProp(text="", properties=[])

    @text_prop.setter
    def text_prop(self, text_prop):
        self.properties["title"] = text_prop.properties
