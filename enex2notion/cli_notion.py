import logging
import sys

from notion_client import Client
from notion_client.errors import APIResponseError

from enex2notion.utils_exceptions import BadTokenException

logger = logging.getLogger(__name__)


def get_root(token, name, pageid=None):
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

    return get_import_root(client, name, pageid)


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


def get_import_root(client, title, pageid):
    """
    Find or create the root page for importing.
    
    Uses the provided pageid as the parent for creating the import root.
    """
    try:
        # First, let's search for an existing page with this title under the parent
        search_result = client.search(
            query=title,
            filter={
                "value": "page",
                "property": "object"
            }
        )
        
        # Look for an exact match that's a child of our parent page
        for result in search_result.get("results", []):
            if result.get("object") == "page":
                page_title = ""
                if "properties" in result and "title" in result["properties"]:
                    title_prop = result["properties"]["title"]
                    if title_prop.get("type") == "title" and title_prop.get("title"):
                        page_title = "".join([
                            t.get("plain_text", "") for t in title_prop["title"]
                        ])
                
                # Check if this page has the right parent
                if page_title == title and result.get("parent", {}).get("page_id") == pageid:
                    logger.info(f"'{title}' page found")
                    result["_client"] = client
                    return result
        
        # If not found, create a new page under the specified parent
        logger.info(f"Creating '{title}' page...")
        
        page_data = {
            "parent": {"page_id": pageid},
            "properties": {
                "title": {
                    "title": [
                        {
                            "text": {
                                "content": title
                            }
                        }
                    ]
                }
            }
        }
        
        new_page = client.pages.create(**page_data)
        new_page["_client"] = client
        logger.info(f"'{title}' page created successfully")
        return new_page
        
    except APIResponseError as e:
        logger.error(f"Failed to create/find import root: {e}")
        raise
