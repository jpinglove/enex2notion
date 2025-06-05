from enex2notion.notion_blocks.base import NotionBaseBlock


def _lstrip_properties(properties):
    strip_properties = []

    for i, prop in enumerate(properties):
        if not prop[0].strip():
            continue

        if len(prop) == 1:
            strip_properties.append([prop[0].lstrip()])
        else:
            strip_properties.append([prop[0].lstrip(), prop[1]])

        strip_properties.extend(properties[i + 1 :])

        break

    return strip_properties


def _rstrip_properties(properties):
    strip_properties = []

    for i, prop in sorted(enumerate(properties), reverse=True):
        if not prop[0].strip():
            continue

        strip_properties.extend(properties[:i])

        if len(prop) == 1:
            strip_properties.append([prop[0].rstrip()])
        else:
            strip_properties.append([prop[0].rstrip(), prop[1]])

        break

    return strip_properties


class TextProp(object):
    def __init__(self, text, properties=None):
        self.text = text

        self.properties = [[text]] if properties is None else properties

        if properties is None:
            self.properties = [[text]] if text else []

    def strip(self):
        strip_properties = _rstrip_properties(_lstrip_properties(self.properties))

        return TextProp(text=self.text.strip(), properties=strip_properties)

    def __eq__(self, other):
        return self.text == other.text and self.properties == other.properties

    def __repr__(self):  # pragma: no cover
        return "<{0}> {1}".format(self.__class__.__name__, self.text)


class NotionTextBased(NotionBaseBlock):
    def __init__(self, text_prop=None, **kwargs):
        super().__init__(**kwargs)

        if text_prop:
            self.attrs["title_plaintext"] = text_prop.text
            self.properties["properties.title"] = text_prop.properties
        else:
            self.attrs["title_plaintext"] = ""
            self.properties["properties.title"] = []

    @property
    def text_prop(self):
        return TextProp(
            text=self.attrs["title_plaintext"],
            properties=self.properties["properties.title"],
        )

    @text_prop.setter
    def text_prop(self, text_prop):
        self.attrs["title_plaintext"] = text_prop.text
        self.properties["properties.title"] = text_prop.properties


class NotionTextBlock(NotionBaseBlock):
    type = "text"

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

    def append_line(self, line):
        if "title" in self.properties:
            # Simple concatenation for new API
            if isinstance(self.properties["title"], list) and isinstance(line, list):
                self.properties["title"].extend(line)
            else:
                self.properties["title"] = line
        else:
            self.properties["title"] = line


class NotionCodeBlock(NotionBaseBlock):
    type = "code"

    def __init__(self, language="plain text", title=None, text_prop=None, **kwargs):
        super().__init__(**kwargs)

        self.attrs["language"] = language

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


class NotionQuoteBlock(NotionBaseBlock):
    type = "quote"

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


class NotionCalloutBlock(NotionBaseBlock):
    type = "callout"

    def __init__(self, title=None, text_prop=None, icon="⚠️", **kwargs):
        super().__init__(**kwargs)

        self.attrs["icon"] = icon

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


class NotionEquationBlock(NotionBaseBlock):
    type = "equation"

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


class NotionDividerBlock(NotionBaseBlock):
    type = "divider"
