from enex2notion.utils_exceptions import NoteUploadFailException
from enex2notion.utils_rand_id import rand_id_list


def get_notebook_page(root, title):
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


def get_notebook_database(root, title):
    """
    Get or create a notebook database.
    
    Note: The modern Notion API has different database creation requirements.
    For now, we'll create a simple page instead and add a note about manual setup.
    """
    try:
        return _get_notebook_database(root, title)
    except Exception as e:
        raise NoteUploadFailException from e


def _get_notebook_database(root, title):
    """
    Create a database-like structure using the modern API.
    
    Note: Database creation with the modern API requires more setup.
    For now, we'll create a regular page and suggest manual database creation.
    """
    client = root.get("_client")
    if not client:
        raise ValueError("No client available for database operations")
    
    # Use the root page ID as the parent
    parent_page_id = root.get("id")
    if not parent_page_id:
        raise ValueError("No parent page ID available for creating database")
    
    # For now, create a regular page with instructions
    page_data = {
        "parent": {"page_id": parent_page_id},
        "properties": {
            "title": {
                "title": [
                    {
                        "text": {
                            "content": f"{title} (Database)"
                        }
                    }
                ]
            }
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": "This would be a database in the legacy version. "
                                         "Please manually create a database here if needed."
                            }
                        }
                    ]
                }
            }
        ]
    }
    
    try:
        new_page = client.pages.create(**page_data)
        new_page["_client"] = client
        return new_page
    except Exception as e:
        raise NoteUploadFailException(f"Failed to create database page: {e}") from e


def _make_notebook_db_schema():
    """Legacy function - not used in modern API."""
    col_ids = rand_id_list(4, 4)
    return {
        col_ids[0]: {"name": "Tags", "type": "multi_select", "options": []},
        col_ids[1]: {"name": "URL", "type": "url"},
        col_ids[2]: {"name": "Created", "type": "created_time"},
        col_ids[3]: {"name": "Updated", "type": "last_edited_time"},
        "title": {"name": "Title", "type": "title"},
    }


def _get_existing_notebook_database(root, title):
    """Legacy function - not used in modern API."""
    return None


def _cleanup_empty_databases(root):
    """Legacy function - not used in modern API."""
    pass


def _properties_order(schema, *fields):
    """Legacy function - not used in modern API."""
    return [
        {"property": col_id, "visible": col["name"] in fields}
        for col_id, col in schema.items()
        if col_id != "title"
    ]
