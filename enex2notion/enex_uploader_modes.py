from enex2notion.utils_exceptions import NoteUploadFailException
from enex2notion.utils_rand_id import rand_id_list


def get_notebook_page(root, title):
    """
    Get or create a notebook page using the modern API.
    """
    try:
        return _get_notebook_page(root, title)
    except Exception as e:
        raise NoteUploadFailException from e


def _get_notebook_page(root, title):
    """Get or create a notebook page using the modern API."""
    client = root.get("_client")
    if not client:
        raise ValueError("No client available for page operations")
    
    # Use the root page ID as the parent
    parent_page_id = root.get("id")
    if not parent_page_id:
        raise ValueError("No parent page ID available for creating page")
    
    # Search for existing page with the title
    try:
        search_result = client.search(
            query=title,
            filter={
                "value": "page", 
                "property": "object"
            }
        )
        
        # Look for exact match
        for result in search_result.get("results", []):
            if result.get("object") == "page":
                page_title = ""
                if "properties" in result and "title" in result["properties"]:
                    title_prop = result["properties"]["title"]
                    if title_prop.get("type") == "title" and title_prop.get("title"):
                        page_title = "".join([
                            t.get("plain_text", "") for t in title_prop["title"]
                        ])
                
                if page_title == title:
                    result["_client"] = client
                    return result
        
        # Create new page if not found
        page_data = {
            "parent": {"page_id": parent_page_id},
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
        return new_page
        
    except Exception as e:
        raise NoteUploadFailException(f"Failed to get/create notebook page: {e}") from e


