
import ast
import requests

def notreturn():
    NOTION_TOKEN = "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"
    DATABASE_ID = "1dde05eb-c9e2-804a-ae01-f673cb3302fa"
    HEADERS = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    pages_data = []

    def fetch_database_entries():
        url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
        response = requests.post(url, headers=HEADERS)
        data = response.json()
        def get_title(page):
            title_property = page["properties"].get("Title", {}).get("title", [])
            return "".join(t["text"]["content"] for t in title_property if "text" in t)
        for page in data.get("results", []):
            page_id = page["id"]
            title = get_title(page)
            status = get_property(page, "Status")
            status=ast.literal_eval(status)
            status1=status['name']
            thumb = get_property(page, "Thumbnail_Params")
            content = fetch_page_content(page_id)
            
            pages_data.append({
                "id": page_id,
                "title": title,
                "status": status1,   
                "thumbnail_params": thumb,
                "content": content.strip()  # strip to remove trailing whitespace
            })# Preview first 100 chars

    def get_title(page):
        title_property = page["properties"].get("Title", {}).get("title", [])
        return title_property[0]["text"]["content"] if title_property else "Untitled"

    def get_property(page, prop_name):
        prop = page["properties"].get(prop_name)
        if prop is None:
            return None

        prop_type = prop["type"]
        if prop_type == "select":
            return prop["select"]  # returns a dict with "name", "color", etc.
        elif prop_type == "rich_text":
            return prop["rich_text"][0]["text"]["content"] if prop["rich_text"] else ""
        return str(prop.get(prop_type))



    def fetch_page_content(page_id):
        url = f"https://api.notion.com/v1/blocks/{page_id}/children"
        response = requests.get(url, headers=HEADERS)
        blocks = response.json().get("results", [])
        texts = []
        for block in blocks:
            if block.get("type") == "paragraph":
                texts += [text["text"]["content"] for text in block["paragraph"]["rich_text"]]
        return " ".join(texts)
    fetch_database_entries()
    return pages_data

'''
for i in p:
    print(i['title'])
    print(i['id'])
    print(i['status'])
    print(i['thumbnail_params'])
    print(i['content'])
    print('\n')
'''
def notupdate(page_id, status=None, thumb=None):
    NOTION_TOKEN = "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"
    DATABASE_ID = "1dde05eb-c9e2-804a-ae01-f673cb3302fa"
    HEADERS = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    url = f"https://api.notion.com/v1/pages/{page_id}"
    
    update_data = {"properties": {}}
    
    if status:
        update_data["properties"]["Status"] = {
            "status": {
                "name": status
            }
        }
    
    if thumb:
        update_data["properties"]["Thumbnail_Params"] = {
            "rich_text": [{
                "text": {
                    "content": thumb
                }
            }]
        }
    
    response = requests.patch(url, headers=HEADERS, json=update_data)
    if response.status_code == 200:
        return True
    else:
        print(f"Error updating page: {response.status_code}")
        print(response.json())
        return False

