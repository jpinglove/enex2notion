from enex2notion.enex_types import EvernoteResource
from enex2notion.notion_blocks.base import NotionBaseBlock


class NotionUploadableBlock(NotionBaseBlock):
    def __init__(self, resource: EvernoteResource, **kwargs):
        super().__init__(**kwargs)

        self.resource = resource


class NotionEmbedBlock(NotionBaseBlock):
    def __init__(self, url, **kwargs):
        super().__init__(**kwargs)

        self.attrs["url"] = url

        self.properties["title"] = [[url]]


class NotionVideoBlock(NotionEmbedBlock):
    type = "video"


class NotionAudioBlock(NotionEmbedBlock):
    type = "audio"


class NotionFileBlock(NotionUploadableBlock):
    type = "file"

    def __init__(self, resource, file_name, **kwargs):
        super().__init__(resource, **kwargs)

        self.properties["title"] = [[file_name]]


class NotionPDFBlock(NotionUploadableBlock):
    type = "pdf"

    def __init__(self, resource, **kwargs):
        super().__init__(resource, **kwargs)

        self.properties["title"] = [[""]]


class NotionImageBlock(NotionUploadableBlock):
    type = "image"

    def __init__(self, resource, **kwargs):
        super().__init__(resource, **kwargs)

        self.properties["title"] = [[""]]
