import logging
import sys

from notion_client import Client
from notion_client.errors import APIResponseError

from enex2notion.utils_exceptions import BadTokenException

logger = logging.getLogger(__name__)


def get_root(token, pageid=None):
    if not token:
        logger.warning(
            "No token provided, dry run mode. Nothing will be uploaded to Notion!"
        )
        return None

    if not pageid:
        logger.warning(
            "No parent page ID provided! Please use --pageid to specify where to create pages."
        )
        return None

    try:
        client = get_notion_client(token)
    except BadTokenException:
        logger.error("Invalid token provided!")
        sys.exit(1)

    return get_import_root(client, pageid)


def get_notion_client(token):
    try:
        client = Client(auth=token)
        # Test the client by trying to list users
        client.users.list()
        # Make token discoverable
        client.auth = token
        client._auth = token
        client._token = token
        return client
    except APIResponseError as e:
        if e.status == 401:
            raise BadTokenException
        raise
    except Exception:
        raise BadTokenException


def get_import_root(client, pageid):
    """
    Get the page specified by pageid to use as the import root.
    
    This will be the direct parent for all imported notebooks.
    """
    try:
        # Get the page specified by pageid
        page = client.pages.retrieve(page_id=pageid)
        page["_client"] = client
        logger.info(f"Using page as import root: {pageid}")
        return page
        
    except APIResponseError as e:
        logger.error(f"Failed to retrieve import root page {pageid}: {e}")
        raise
