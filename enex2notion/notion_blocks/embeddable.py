from enex2notion.notion_blocks.base import NotionBaseBlock


class NotionEmbedBlock(NotionBaseBlock):
    def __init__(self, url, **kwargs):
        super().__init__(**kwargs)

        self.attrs["url"] = url

        self.properties["title"] = [[url]]


class NotionImageEmbedBlock(NotionEmbedBlock):
    type = "image"


class NotionBookmarkBlock(NotionEmbedBlock):
    type = "bookmark"


class NotionCodepenBlock(NotionEmbedBlock):
    type = "codepen"


class NotionDriveBlock(NotionEmbedBlock):
    type = "drive"


class NotionFigmaBlock(NotionEmbedBlock):
    type = "figma"


class NotionMapsBlock(NotionEmbedBlock):
    type = "maps"


class NotionTweetBlock(NotionEmbedBlock):
    type = "tweet"


class NotionGistBlock(NotionEmbedBlock):
    type = "gist"


class NotionFramerBlock(NotionEmbedBlock):
    type = "framer"


class NotionInvisionBlock(NotionEmbedBlock):
    type = "invision"


class NotionLoomBlock(NotionEmbedBlock):
    type = "loom"


class NotionWhimsicalBlock(NotionEmbedBlock):
    type = "whimsical"


class NotionMiroBlock(NotionEmbedBlock):
    type = "miro"


class NotionPDFBlock(NotionEmbedBlock):
    type = "pdf"
