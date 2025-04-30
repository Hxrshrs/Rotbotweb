from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import requests
import os
import json
from datetime import datetime
import base64
import io
import traceback
import uuid
from dotenv import load_dotenv
import google.generativeai as genai
import tempfile
import cloudinary
import cloudinary.uploader
import cloudinary.api
from threading import Thread

# Load environment variables
load_dotenv()

# Configure Cloudinary
cloudinary.config(
    cloud_name='douy5mfmn',
    api_key='652237757436661',
    api_secret='jam3Q4qo3d-wNCc1RiSiN5JSHR8'
)

# Configure Google Gemini API
GOOGLE_API_KEY = 'AIzaSyDn591Ry1jcclt282hRUAzfx8NVbdKAN0U'
genai.configure(api_key=GOOGLE_API_KEY)
# Use Gemini 2.5 Flash Preview
MODEL_NAME = 'gemini-2.5-flash-preview-04-17'
model = genai.GenerativeModel(model_name=MODEL_NAME)

# Path for storing custom prompts
CUSTOM_PROMPTS_FILE = os.path.join(os.getcwd(), 'custom_prompts.json')

# Notion database for profiles
PROFILES_DATABASE_ID = '1e1e05ebc9e280dd8e82e6ff12f17936'

# Configuration
IMGUR_CLIENT_ID = ''  # Add your Imgur client ID if needed
NOTION_API_TOKEN = os.environ.get('NOTION_API_TOKEN', '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')  # Use env or fallback to hardcoded
NOTION_DATABASE_ID = os.environ.get('NOTION_DATABASE_ID', '1dde05ebc9e2804aae01f673cb3302fa')  # Updated to correct database ID
NOTION_TARGET_ID = '1dee05eb-c9e2-80b5-a512-d5e2af5617f9'

# Print important configuration values at startup
print("\n=== APPLICATION CONFIGURATION ===")
print(f"NOTION_API_TOKEN: {NOTION_API_TOKEN[:5]}...{NOTION_API_TOKEN[-5:] if NOTION_API_TOKEN else 'NOT SET'}")
print(f"NOTION_DATABASE_ID: {NOTION_DATABASE_ID}")
print(f"PROFILES_DATABASE_ID: {PROFILES_DATABASE_ID}")

# Validate Notion configuration
if not NOTION_API_TOKEN or not NOTION_DATABASE_ID or not PROFILES_DATABASE_ID:
    print("WARNING: Missing Notion configuration! Profile functionality may not work correctly.")
    print(f"  NOTION_API_TOKEN: {'SET' if NOTION_API_TOKEN else 'MISSING'}")
    print(f"  NOTION_DATABASE_ID: {'SET' if NOTION_DATABASE_ID else 'MISSING'}")
    print(f"  PROFILES_DATABASE_ID: {'SET' if PROFILES_DATABASE_ID else 'MISSING'}")
else:
    print("Notion configuration looks good!")
print("================================\n")

# Initialize custom prompts file if it doesn't exist
def init_custom_prompts_file():
    if not os.path.exists(CUSTOM_PROMPTS_FILE):
        with open(CUSTOM_PROMPTS_FILE, 'w') as f:
            json.dump({"custom_prompt": "generate one story", "system_instruction": ""}, f)

# Load custom prompts from file
def load_custom_prompts():
    init_custom_prompts_file()
    try:
        with open(CUSTOM_PROMPTS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"custom_prompt": "generate one story", "system_instruction": ""}

# Save custom prompts to file
def save_custom_prompts(custom_prompt, system_instruction):
    try:
        with open(CUSTOM_PROMPTS_FILE, 'w') as f:
            json.dump({
                "custom_prompt": custom_prompt, 
                "system_instruction": system_instruction
            }, f)
        return True
    except Exception as e:
        print(f"Error saving custom prompts: {e}")
        return False

# Fetch profiles from Notion database
def fetch_profiles_from_notion():
    try:
        print("\n=== FETCHING PROFILES FROM NOTION ===")
        print(f"Using Profiles Database ID: {PROFILES_DATABASE_ID}")
        print(f"Using Notion token: {NOTION_API_TOKEN}")
        
        # First, get the database schema to check available properties
        schema_response = requests.get(
            f"https://api.notion.com/v1/databases/{PROFILES_DATABASE_ID}",
            headers={
                "Authorization": f"Bearer {NOTION_API_TOKEN}",
                "Notion-Version": "2022-06-28"
            }
        )
        
        print(f"Database schema response status: {schema_response.status_code}")
        
        if schema_response.status_code == 200:
            schema_data = schema_response.json()
            properties = schema_data.get('properties', {})
            
            print("\n=== ACTUAL DATABASE PROPERTIES ===")
            print(f"Available property names in database: {list(properties.keys())}")
            for prop_name, prop_info in properties.items():
                prop_type = prop_info.get('type', 'unknown')
                print(f"Property '{prop_name}' has type: {prop_type}")
            print("=================================\n")
            
            print("\n=== EXPECTED PROPERTY MAPPING ===")
            expected_props = {
                'Name': 'title',
                'ProfileID': 'rich_text',
                'ThumbnailBackground': 'files',
                'ProfileImage': 'files',
                'NotionDatabaseID': 'rich_text',
                'SystemPrompt': 'rich_text',
                'FillColor': 'rich_text',
                'HighlightColor': 'rich_text',
                'Font': 'rich_text',
                'Active': 'checkbox'
            }
            
            for expected_name, expected_type in expected_props.items():
                if expected_name in properties:
                    actual_type = properties[expected_name].get('type', 'unknown')
                    match = actual_type == expected_type
                    print(f"Property '{expected_name}': FOUND - Type Match: {match} (expected {expected_type}, actual {actual_type})")
                else:
                    print(f"Property '{expected_name}': NOT FOUND")
            print("=================================\n")
            
            # Map our expected names to actual database names if needed
            property_mapping = {}
            for actual_name, prop_info in properties.items():
                actual_type = prop_info.get('type')
                for expected_name, expected_type in expected_props.items():
                    # Check for similar names (case insensitive) and same type
                    if (expected_name.lower() == actual_name.lower() or 
                        expected_name.lower().replace(' ', '') == actual_name.lower().replace(' ', '')):
                        if property_mapping.get(expected_name) is None:  # Don't overwrite existing mappings
                            property_mapping[expected_name] = actual_name
                            print(f"Mapping '{expected_name}' to '{actual_name}'")
            
            print(f"Final property mapping: {property_mapping}")
        else:
            print(f"ERROR fetching database schema: {schema_response.status_code} - {schema_response.text}")
        
        # Proceed with querying for profiles
        response = requests.post(
            f"https://api.notion.com/v1/databases/{PROFILES_DATABASE_ID}/query",
            headers={
                "Authorization": f"Bearer {NOTION_API_TOKEN}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            },
            json={}
        )
        
        print(f"Notion API response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"ERROR fetching profiles: {response.status_code} - {response.text}")
            return {"profiles": []}
            
        data = response.json()
        results = data.get('results', [])
        print(f"Found {len(results)} profiles in Notion")
        
        # Print the database structure from actual results
        if results and len(results) > 0:
            print("\n=== EXAMPLE PROFILE DATA ===")
            first_page = results[0]
            properties = first_page.get('properties', {})
            print(f"Available property keys in result: {list(properties.keys())}")
            for key, value in properties.items():
                print(f"Property '{key}' has type: {value.get('type', 'unknown')}")
            print("=========================\n")
        
        profiles = []
        for i, page in enumerate(results):
            properties = page.get('properties', {})
            print(f"\n--- RAW PROPERTIES FOR PROFILE {i+1} ---")
            print(json.dumps(properties, indent=2))
            print("--------------------------------")
            
            # Use our property mapping if we have one
            if 'property_mapping' in locals() and property_mapping:
                # Extract profile data from properties with mapping
                profile = {
                    'id': page.get('id'),
                    'name': get_property_value(properties.get(property_mapping.get('Name', 'Name')), 'title'),
                    'profileId': get_property_value(properties.get(property_mapping.get('ProfileID', 'ProfileID')), 'rich_text'),
                    'thumbnailBackground': get_property_value(properties.get(property_mapping.get('ThumbnailBackground', 'ThumbnailBackground')), 'files'),
                    'profileImage': get_property_value(properties.get(property_mapping.get('ProfileImage', 'ProfileImage')), 'files'),
                    'notionDbId': get_property_value(properties.get(property_mapping.get('NotionDatabaseID', 'NotionDatabaseID')), 'rich_text'),
                    'fillColor': get_property_value(properties.get(property_mapping.get('FillColor', 'FillColor')), 'rich_text', '#333333'),
                    'highlightColor': get_property_value(properties.get(property_mapping.get('HighlightColor', 'HighlightColor')), 'rich_text', '#2196F3'),
                    'font': get_property_value(properties.get(property_mapping.get('Font', 'Font')), 'rich_text', 'Arial'),
                    'active': get_property_value(properties.get(property_mapping.get('Active', 'Active')), 'checkbox', False)
                }
                
                # Get system prompt from page content instead of property
                system_prompt = get_system_prompt_from_content(page.get('id'))
                if system_prompt:
                    profile['systemPrompt'] = system_prompt
                else:
                    # Fallback to property value if page content is empty
                    profile['systemPrompt'] = get_property_value(properties.get(property_mapping.get('SystemPrompt', 'SystemPrompt')), 'rich_text')
            else:
                # Extract profile data from properties using original names
                profile = {
                    'id': page.get('id'),
                    'name': get_property_value(properties.get('Name'), 'title'),
                    'profileId': get_property_value(properties.get('ProfileID'), 'rich_text'),
                    'thumbnailBackground': get_property_value(properties.get('ThumbnailBackground'), 'files'),
                    'profileImage': get_property_value(properties.get('ProfileImage'), 'files'),
                    'notionDbId': get_property_value(properties.get('NotionDatabaseID'), 'rich_text'),
                    'fillColor': get_property_value(properties.get('FillColor'), 'rich_text', '#333333'),
                    'highlightColor': get_property_value(properties.get('HighlightColor'), 'rich_text', '#2196F3'),
                    'font': get_property_value(properties.get('Font'), 'rich_text', 'Arial'),
                    'active': get_property_value(properties.get('Active'), 'checkbox', False)
                }
                
                # Get system prompt from page content
                system_prompt = get_system_prompt_from_content(page.get('id'))
                if system_prompt:
                    profile['systemPrompt'] = system_prompt
                else:
                    # Fallback to property value if page content is empty
                    profile['systemPrompt'] = get_property_value(properties.get('SystemPrompt'), 'rich_text')
            
            print(f"Extracted profile: {json.dumps(profile, indent=2)}")
            profiles.append(profile)
            
        print(f"Successfully fetched {len(profiles)} profiles from Notion")
        return {"profiles": profiles}
    except Exception as e:
        print(f"ERROR fetching profiles from Notion: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return {"profiles": []}

# Get system prompt from page content
def get_system_prompt_from_content(page_id):
    try:
        print(f"Fetching system prompt from page content for page {page_id}")
        
        # Get blocks from the page
        response = requests.get(
            f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100",
            headers={
                "Authorization": f"Bearer {NOTION_API_TOKEN}",
                "Notion-Version": "2022-06-28"
            }
        )
        
        if response.status_code != 200:
            print(f"Error getting page blocks: {response.status_code} - {response.text}")
            return None
            
        blocks = response.json().get('results', [])
        print(f"Retrieved {len(blocks)} blocks from page {page_id}")
        
        if not blocks:
            print("No blocks found in page")
            return None
            
        # Extract all content from the page - we don't rely on "System Prompt" heading
        # as this gives more flexibility in how content is stored
        content_parts = []
        
        for block in blocks:
            block_type = block.get('type')
            
            # Skip headings and other non-content blocks
            if block_type == 'paragraph':
                text_content = ""
                rich_text = block.get('paragraph', {}).get('rich_text', [])
                
                for text_part in rich_text:
                    text_content += text_part.get('plain_text', '')
                
                if text_content.strip():
                    content_parts.append(text_content)
        
        if not content_parts:
            print("No text content found in page")
            return None
            
        # Combine all content with newlines
        system_prompt = '\n'.join(content_parts)
        print(f"Found content in page: {len(system_prompt)} characters")
        return system_prompt
        
    except Exception as e:
        print(f"Error extracting content from page: {str(e)}")
        print(traceback.format_exc())
        return None

# Helper to extract values from Notion properties
def get_property_value(property_data, property_type, default=None):
    try:
        if not property_data:
            return default
            
        print(f"  Extracting {property_type} from property: {json.dumps(property_data, indent=2)}")
        
        actual_type = property_data.get('type')
        if actual_type != property_type:
            print(f"  WARNING: Expected property type '{property_type}', but got '{actual_type}'")
            
            # Special handling for files properties instead of URL
            if actual_type == 'files' and (property_type == 'url' or property_type == 'files'):
                print(f"  Converting 'files' property to URL value")
                files = property_data.get('files', [])
                if files and len(files) > 0:
                    first_file = files[0]
                    file_type = first_file.get('type')
                    if file_type == 'external':
                        result = first_file.get('external', {}).get('url', default)
                        print(f"  Extracted external file URL: {result}")
                        return result
                    elif file_type == 'file':
                        result = first_file.get('file', {}).get('url', default)
                        print(f"  Extracted file URL: {result}")
                        return result
                print(f"  No files found, returning default: {default}")
                return default
        
        if property_type == 'title':
            title_array = property_data.get('title', [])
            if title_array and len(title_array) > 0:
                result = title_array[0].get('plain_text', default)
                print(f"  Extracted title value: {result}")
                return result
            print(f"  No title value found, returning default: {default}")
            return default
            
        elif property_type == 'rich_text':
            rich_text_array = property_data.get('rich_text', [])
            if rich_text_array and len(rich_text_array) > 0:
                result = rich_text_array[0].get('plain_text', default)
                print(f"  Extracted rich_text value: {result}")
                return result
            print(f"  No rich_text value found, returning default: {default}")
            return default
            
        elif property_type == 'url':
            result = property_data.get('url', default)
            print(f"  Extracted URL value: {result}")
            return result
            
        elif property_type == 'files':
            files = property_data.get('files', [])
            if files and len(files) > 0:
                first_file = files[0]
                file_type = first_file.get('type')
                if file_type == 'external':
                    result = first_file.get('external', {}).get('url', default)
                    print(f"  Extracted external file URL: {result}")
                    return result
                elif file_type == 'file':
                    result = first_file.get('file', {}).get('url', default)
                    print(f"  Extracted file URL: {result}")
                    return result
            print(f"  No files found, returning default: {default}")
            return default
            
        elif property_type == 'checkbox':
            result = property_data.get('checkbox', default)
            print(f"  Extracted checkbox value: {result}")
            return result
            
        print(f"  Unsupported property type: {property_type}, returning default: {default}")
        return default
    except Exception as e:
        print(f"  ERROR extracting property value: {str(e)}")
        return default

# Create or update a profile in Notion
def save_profile_to_notion(profile):
    try:
        print("\n=== SAVING PROFILE TO NOTION (DEBUG) ===")
        print(f"Profile data to save: {json.dumps(profile, indent=2)}")
        
        # Get the database schema
        print("Attempting to fetch database schema...")
        schema_response = requests.get(
            f"https://api.notion.com/v1/databases/{PROFILES_DATABASE_ID}",
            headers={
                "Authorization": f"Bearer {NOTION_API_TOKEN}",
                "Notion-Version": "2022-06-28"
            }
        )
        
        print(f"Schema response status: {schema_response.status_code}")
        
        property_mapping = {}
        db_properties = {}
        if schema_response.status_code == 200:
            schema = schema_response.json()
            db_properties = schema.get('properties', {})
            
            for prop_name, prop_data in db_properties.items():
                if prop_name.lower() == 'name':
                    property_mapping['Name'] = prop_name
                elif prop_name.lower() == 'profileid':
                    property_mapping['ProfileID'] = prop_name
                elif prop_name.lower() == 'thumbnailbackground':
                    property_mapping['ThumbnailBackground'] = prop_name
                elif prop_name.lower() == 'profileimage':
                    property_mapping['ProfileImage'] = prop_name
                elif prop_name.lower() == 'notiondatabaseid':
                    property_mapping['NotionDatabaseID'] = prop_name
                elif prop_name.lower() == 'systempromt' or prop_name.lower() == 'systemprompt':
                    property_mapping['SystemPrompt'] = prop_name
                elif prop_name.lower() == 'fillcolor':
                    property_mapping['FillColor'] = prop_name
                elif prop_name.lower() == 'highlightcolor':
                    property_mapping['HighlightColor'] = prop_name
                elif prop_name.lower() == 'font':
                    property_mapping['Font'] = prop_name

        profile_id = profile.get('profileId') or str(uuid.uuid4())
        existing_profile_id = None

        if 'id' in profile:
            existing_profile_id = profile['id']
            print(f"Found existing Notion page ID in profile: {existing_profile_id}")
        else:
            print(f"Searching for existing profile with profileId: {profile_id}")
            query_filter = {
                "filter": {
                    "property": property_mapping.get('ProfileID', 'ProfileID'),
                    "rich_text": {
                        "equals": profile_id
                    }
                }
            }
            
            query_response = requests.post(
                f"https://api.notion.com/v1/databases/{PROFILES_DATABASE_ID}/query",
                headers={
                    "Authorization": f"Bearer {NOTION_API_TOKEN}",
                    "Notion-Version": "2022-06-28",
                    "Content-Type": "application/json"
                },
                json=query_filter
            )
            
            if query_response.status_code == 200:
                results = query_response.json().get('results', [])
                if results:
                    existing_profile_id = results[0].get('id')
        
        # Property keys
        name_prop = property_mapping.get('Name', 'Name')
        profile_id_prop = property_mapping.get('ProfileID', 'ProfileID')
        bg_prop = property_mapping.get('ThumbnailBackground', 'ThumbnailBackground')
        img_prop = property_mapping.get('ProfileImage', 'ProfileImage')
        db_id_prop = property_mapping.get('NotionDatabaseID', 'NotionDatabaseID')
        fill_color_prop = property_mapping.get('FillColor', 'FillColor')
        highlight_color_prop = property_mapping.get('HighlightColor', 'HighlightColor')
        font_prop = property_mapping.get('Font', 'Font')
        system_prompt_prop = property_mapping.get('SystemPrompt', 'SystemPrompt')

        # Properties dictionary
        properties = {}

        properties[name_prop] = {
            "title": [
                {
                    "text": {
                        "content": profile.get('name', 'Unnamed Profile')
                    }
                }
            ]
        }

        if profile_id_prop in db_properties:
            properties[profile_id_prop] = {
                "rich_text": [
                    {
                        "text": {
                            "content": profile_id
                        }
                    }
                ]
            }

        if db_id_prop in db_properties:
            properties[db_id_prop] = {
                "rich_text": [
                    {
                        "text": {
                            "content": profile.get('notionDbId', '')
                        }
                    }
                ]
            }

        if fill_color_prop in db_properties:
            properties[fill_color_prop] = {
                "rich_text": [
                    {
                        "text": {
                            "content": profile.get('fillColor', '#333333')
                        }
                    }
                ]
            }

        if highlight_color_prop in db_properties:
            properties[highlight_color_prop] = {
                "rich_text": [
                    {
                        "text": {
                            "content": profile.get('highlightColor', '#2196F3')
                        }
                    }
                ]
            }

        if font_prop in db_properties:
            properties[font_prop] = {
                "rich_text": [
                    {
                        "text": {
                            "content": profile.get('font', 'Arial')
                        }
                    }
                ]
            }

        # IMPORTANT: Explicitly set SystemPrompt property to empty if it exists
        # This ensures we don't try to store it in the property anymore
        if system_prompt_prop in db_properties:
            properties[system_prompt_prop] = {
                "rich_text": []  # Empty array = no content
            }

        # Handle image properties
        def process_image_url(image_url, default_name):
            if not image_url:
                return {"files": []}
            if image_url.startswith('data:'):
                try:
                    image_data = image_url.split(',')[1]
                    image_bytes = base64.b64decode(image_data)
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                        temp_file.write(image_bytes)
                        temp_file_path = temp_file.name
                    imgur_url = upload_to_imgur(temp_file_path)
                    os.unlink(temp_file_path)
                    if imgur_url:
                        return {
                            "files": [
                                {
                                    "name": default_name,
                                    "type": "external",
                                    "external": {
                                        "url": imgur_url
                                    }
                                }
                            ]
                        }
                except Exception as e:
                    print(f"Failed to process image: {str(e)}")
                    return {"files": []}
            return {
                "files": [
                    {
                        "name": default_name,
                        "type": "external",
                        "external": {
                            "url": image_url
                        }
                    }
                ]
            }

        if bg_prop in db_properties:
            bg_url = profile.get('thumbnailBackground', '')
            properties[bg_prop] = process_image_url(bg_url, "thumbnail.jpg")

        if img_prop in db_properties:
            img_url = profile.get('profileImage', '')
            properties[img_prop] = process_image_url(img_url, "profile.jpg")

        headers = {
            "Authorization": f"Bearer {NOTION_API_TOKEN}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }

        # Create page content blocks from system prompt
        system_prompt = profile.get('systemPrompt', '')
        children_blocks = []
        
        if system_prompt:
            # We don't need a heading, just put the system prompt as paragraph blocks
            # This makes the content easier to edit in Notion if needed
            MAX_BLOCK_SIZE = 1900  # Notion has a 2000 char limit per block
            
            # Split system prompt by paragraphs first
            paragraphs = system_prompt.split('\n')
            
            current_block = ""
            for paragraph in paragraphs:
                # If this paragraph would make the block too large, create a new block
                if len(current_block) + len(paragraph) + 1 > MAX_BLOCK_SIZE:
                    # Add current block to blocks list
                    if current_block:
                        children_blocks.append({
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [{
                                    "type": "text",
                                    "text": {"content": current_block}
                                }]
                            }
                        })
                    current_block = paragraph
                else:
                    # Add to current block
                    if current_block:
                        current_block += "\n" + paragraph
                    else:
                        current_block = paragraph
            
            # Add any remaining content as a final block
            if current_block:
                children_blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": current_block}
                        }]
                    }
                })

        # Use a transaction for updating existing pages to ensure consistency
        if existing_profile_id:
            try:
                # Update the existing page properties
                property_response = requests.patch(
                    f"https://api.notion.com/v1/pages/{existing_profile_id}",
                    headers=headers,
                    json={
                        "properties": properties
                    }
                )
                
                if property_response.status_code != 200:
                    print(f"Error updating properties: {property_response.status_code} - {property_response.text}")
                    return None
                
                # Clear existing content
                print(f"Clearing existing content for page {existing_profile_id}")
                clear_response = requests.patch(
                    f"https://api.notion.com/v1/blocks/{existing_profile_id}/children",
                    headers=headers,
                    json={
                        "children": []
                    }
                )
                
                if clear_response.status_code != 200:
                    print(f"Error clearing content: {clear_response.status_code} - {clear_response.text}")
                    # Continue anyway, even if clearing failed
                
                # Only add content if we have blocks to add
                if children_blocks:
                    print(f"Adding {len(children_blocks)} content blocks to page {existing_profile_id}")
                    content_response = requests.patch(
                        f"https://api.notion.com/v1/blocks/{existing_profile_id}/children",
                        headers=headers,
                        json={
                            "children": children_blocks
                        }
                    )
                    
                    if content_response.status_code != 200:
                        print(f"Error adding content: {content_response.status_code} - {content_response.text}")
                        # Still return the page since properties were updated
                
                print(f"Successfully updated profile {existing_profile_id}")
                return property_response.json()
                
            except Exception as e:
                print(f"Error in transaction for updating profile: {str(e)}")
                print(traceback.format_exc())
                return None
        else:
            # Create a new page with properties and content
            request_body = {
                "parent": {
                    "database_id": PROFILES_DATABASE_ID
                },
                "properties": properties,
                "children": children_blocks
            }
            
            response = requests.post(
                "https://api.notion.com/v1/pages",
                headers=headers,
                json=request_body
            )

            if response.status_code not in [200, 201]:
                print(f"ERROR creating profile: {response.status_code} - {response.text}")
                return None

            print(f"Successfully created new profile")
            return response.json()

    except Exception as e:
        print(f"ERROR in save_profile_to_notion: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return None

# Delete a profile from Notion
def delete_profile_from_notion(profile_id):
    try:
        # Notion uses soft deletes by archiving pages
        response = requests.patch(
            f"https://api.notion.com/v1/pages/{profile_id}",
            headers={
                "Authorization": f"Bearer {NOTION_API_TOKEN}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            },
            json={
                "archived": True
            }
        )
        
        if response.status_code != 200:
            print(f"Error deleting profile: {response.status_code} - {response.text}")
            return False
            
        return True
    except Exception as e:
        print(f"Error deleting profile from Notion: {str(e)}")
        return False

# Initialize Flask app with absolute paths
app = Flask(__name__, 
           static_folder=os.path.join(os.getcwd(), 'public'),
           static_url_path='')

# Get the base path from environment variable or use empty string
# Ensure it starts with a slash but doesn't end with one
BASE_PATH = os.environ.get('BASE_PATH', '')
if BASE_PATH and not BASE_PATH.startswith('/'):
    BASE_PATH = '/' + BASE_PATH
if BASE_PATH.endswith('/'):
    BASE_PATH = BASE_PATH[:-1]

# Configure CORS
ALLOWED_ORIGINS = [
    'https://web-thumbmaker.vercel.app',  # Vercel production
    'https://rotbot-backend.onrender.com', # Render production
    'https://pointshift.design',         # Custom domain
    'http://localhost:3000',              # Local frontend development
    'http://127.0.0.1:5001',             # Local backend development
    'http://localhost:5001',             # Additional local development
    'http://127.0.0.1:5500',            # VS Code Live Server
    'http://localhost:5500',            # VS Code Live Server
    'null'                              # Local file system
]

if os.environ.get('FLASK_ENV') == 'development':
    # In development, allow all origins
    CORS(app, resources={
        r"/*": {
            "origins": "*",
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
else:
    # In production, use specific origins
    CORS(app, resources={
        r"/*": {
            "origins": ALLOWED_ORIGINS,
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

def save_base64_image(base64_data, filename=None):
    """Save base64 image data to Cloudinary and return the URL"""
    try:
        if not filename:
            filename = str(uuid.uuid4())
            
        # Upload to Cloudinary
        cloudinary_url = upload_to_cloudinary(base64_data, public_id=filename)
        
        if cloudinary_url:
            return cloudinary_url
        
        # Fallback to local storage if Cloudinary upload fails
        if base64_data.startswith('data:'):
            # Extract the actual base64 data
            base64_data = base64_data.split(',')[1]
            
        # Decode base64 data
        image_data = base64.b64decode(base64_data)
        
        # Ensure the images directory exists
        os.makedirs('images', exist_ok=True)
        image_path = os.path.join('images', f"{filename}.jpg")
        with open(image_path, 'wb') as f:
            f.write(image_data)
            
        return f"/images/{filename}.jpg"
        
    except Exception as e:
        print(f"Error saving image: {str(e)}")
        traceback.print_exc()
        return None

def upload_to_cloudinary(image_data, public_id=None):
    """Upload image to Cloudinary and return the URL"""
    try:
        # If image_data is a data URL, extract the base64 data
        if isinstance(image_data, str) and image_data.startswith('data:'):
            # Extract base64 data
            image_data = image_data.split(',')[1]
            # Convert to bytes
            image_bytes = base64.b64decode(image_data)
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                temp_file.write(image_bytes)
                temp_file_path = temp_file.name
                
            try:
                # Upload to Cloudinary
                upload_result = cloudinary.uploader.upload(
                    temp_file_path,
                    public_id=public_id,
                    folder='web-thumbmaker',  # Optional: organize images in a folder
                    resource_type="auto"
                )
                
                # Clean up temp file
                os.unlink(temp_file_path)
                
                return upload_result['secure_url']
            except Exception as e:
                # Clean up temp file in case of error
                os.unlink(temp_file_path)
                raise e
        else:
            # If it's a file path, upload directly
            upload_result = cloudinary.uploader.upload(
                image_data,
                public_id=public_id,
                folder='web-thumbmaker',
                resource_type="auto"
            )
            return upload_result['secure_url']
            
    except Exception as e:
        print(f"Error uploading to Cloudinary: {str(e)}")
        return None

# Replace the old upload_to_imgur function with Cloudinary
def upload_to_imgur(image_path):
    """Upload image to Cloudinary instead of Imgur"""
    try:
        cloudinary_url = upload_to_cloudinary(image_path)
        if cloudinary_url:
            return cloudinary_url
        else:
            print("Cloudinary upload failed, serving image locally")
            return f"/images/{os.path.basename(image_path)}"
    except Exception as e:
        print(f"Error uploading to Cloudinary: {str(e)}")
        return f"/images/{os.path.basename(image_path)}"

@app.route(f'{BASE_PATH}/')
def serve_app():
    try:
        return send_from_directory('public', 'index.html')
    except Exception as e:
        print(f"Error serving index.html: {str(e)}")
        return str(e), 500

@app.route(f'{BASE_PATH}/settings')
def serve_settings():
    try:
        return send_from_directory('public', 'settings.html')
    except Exception as e:
        print(f"Error serving settings.html: {str(e)}")
        return str(e), 500

@app.route('/api/test-notion', methods=['GET'])
def test_notion():
    try:
        # Fetch database information
        response = requests.get(
            f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}",
            headers={
                "Authorization": f"Bearer {NOTION_API_TOKEN}",
                "Notion-Version": "2022-06-28"
            }
        )
        
        print(f"Database Info Response Status: {response.status_code}")
        print(f"Database Info Response Body: {response.text}")
        
        if response.status_code == 200:
            database_info = response.json()
            return jsonify({
                "message": "Successfully connected to Notion",
                "database": {
                    "title": database_info.get("title", []),
                    "properties": database_info.get("properties", {})
                }
            })
        else:
            return jsonify({"error": "Failed to fetch database information"}), response.status_code
            
    except Exception as e:
        print(f"Error testing Notion connection: {str(e)}")
        return jsonify({"error": str(e)}), 500

def split_content_into_blocks(content):
    """Split long content into multiple paragraph blocks that Notion can handle"""
    if not content:
        return []

    MAX_BLOCK_LENGTH = 1900  # Slightly less than 2000 to be safe
    blocks = []
    
    # Split content into paragraphs and clean up excessive line breaks
    paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
    
    current_block = ""
    for paragraph in paragraphs:
        # If paragraph itself is too long, split it into smaller chunks
        if len(paragraph) > MAX_BLOCK_LENGTH:
            # First, add any existing content as a block
            if current_block:
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": current_block.strip()}
                        }]
                    }
                })
                current_block = ""
            
            # Split long paragraph into chunks
            words = paragraph.split(' ')
            chunk = ""
            
            for word in words:
                if len(chunk) + len(word) + 1 <= MAX_BLOCK_LENGTH:
                    chunk += (" " + word if chunk else word)
                else:
                    # Add current chunk as a block
                    blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{
                                "type": "text",
                                "text": {"content": chunk.strip()}
                            }]
                        }
                    })
                    chunk = word
            
            # Add remaining chunk if any
            if chunk:
                current_block = chunk
        else:
            # If adding this paragraph would exceed block limit, create new block
            if len(current_block) + len(paragraph) + 1 > MAX_BLOCK_LENGTH:  # +1 for \n
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": current_block.strip()}
                        }]
                    }
                })
                current_block = paragraph
            else:
                # Add paragraph to current block with single line break
                current_block += ("\n" + paragraph if current_block else paragraph)
    
    # Add remaining content as final block
    if current_block:
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": current_block.strip()}
                }]
            }
        })
    
    return blocks

@app.route(f'{BASE_PATH}/api/save-to-notion', methods=['POST', 'OPTIONS'])
def save_to_notion():
    if request.method == 'OPTIONS':
        return '', 204
        
    try:
        data = request.get_json()
        print("Received data:", json.dumps(data, indent=2))
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        title = data.get('title')
        content = data.get('content')
        thumbnail_image = data.get('thumbnailImage')
        # Get the database ID from the request, or use the default
        database_id = data.get('notionDbId', NOTION_DATABASE_ID)
        saved_image_path = None
        
        print("Title:", title)
        print("Content length:", len(content) if content else 0)
        print("Using Notion Database ID:", database_id)
        
        if not title:
            return jsonify({"error": "Title is required"}), 400

        # Truncate title if too long (Notion limit is 2000 characters)
        MAX_TITLE_LENGTH = 1900  # Slightly less than 2000 to be safe
        if len(title) > MAX_TITLE_LENGTH:
            title = title[:MAX_TITLE_LENGTH] + "..."
            print(f"Title truncated to {len(title)} characters")

        # First, fetch the database schema to get correct property names
        db_response = requests.get(
            f"https://api.notion.com/v1/databases/{database_id}",
            headers={
                "Authorization": f"Bearer {NOTION_API_TOKEN}",
                "Notion-Version": "2022-06-28"
            }
        )
        
        if db_response.status_code != 200:
            print("Database fetch failed:", db_response.text)
            return jsonify({"error": "Failed to fetch database schema"}), db_response.status_code
            
        database_schema = db_response.json()
        
        # Debug: Print database properties
        print("\n=== Database Properties ===")
        properties = database_schema.get('properties', {})
        print("Available properties:", json.dumps(properties, indent=2))
        print("=========================\n")
        
        # Save and upload image if we have one
        image_url = None
        try:
            if thumbnail_image:
                # Try to save and get the image URL (will try Cloudinary first)
                saved_image_path = save_base64_image(thumbnail_image, title)
                if not saved_image_path:
                    return jsonify({"error": "Failed to save image"}), 500
                print("Saved image at:", saved_image_path)
                
                # If it's a Cloudinary URL, use it directly
                if saved_image_path.startswith('http'):
                    image_url = saved_image_path
                    print("Using Cloudinary URL:", image_url)
                else:
                    # If it's a local path, try Imgur as fallback
                    image_url = upload_to_imgur(saved_image_path)
                    print("Imgur upload result:", image_url)
                    
                    if image_url and not image_url.startswith('/images/'):
                        # Successfully uploaded to Imgur, we can delete the local file
                        try:
                            os.remove(saved_image_path)
                            print(f"Cleaned up local file after Imgur upload: {saved_image_path}")
                        except Exception as e:
                            print(f"Failed to clean up local file: {str(e)}")
                    else:
                        # If Imgur upload failed, keep the local file and use local path
                        print("Imgur upload failed or not configured, using local path")
                        image_url = f"/images/{os.path.basename(saved_image_path)}"
                    
                print("Final image URL to use:", image_url)
        except Exception as e:
            print(f"Error handling image: {str(e)}")
            # If anything fails, try to use local path as fallback
            if saved_image_path:
                image_url = f"/images/{os.path.basename(saved_image_path)}"
                print("Using local path as fallback:", image_url)

        # Split content into blocks that Notion can handle
        blocks = split_content_into_blocks(content)
        
        # Construct the Notion page data
        notion_data = {
            "parent": {
                "type": "database_id",
                "database_id": database_id
            },
            "properties": {
                "Title": {
                    "title": [
                        {
                            "text": {
                                "content": title
                            }
                        }
                    ]
                },
                "Status": {
                    "status": {
                        "name": "READY"
                    }
                },
                "Date": {
                    "date": {
                        "start": datetime.now().isoformat()
                    }
                }
            },
            "children": blocks
        }

        # Add image to Files & media property if we have URL
        if image_url:
            # If using local path, construct full URL
            if image_url.startswith('/images/'):
                # Use request.host_url to get the base URL
                base_url = request.host_url.rstrip('/')
                full_url = f"{base_url}{image_url}"
                notion_data["properties"]["Files & media"] = {
                    "files": [
                        {
                            "type": "external",
                            "name": "thumbnail.png",
                            "external": {
                                "url": full_url
                            }
                        }
                    ]
                }
            else:
                notion_data["properties"]["Files & media"] = {
                    "files": [
                        {
                            "type": "external",
                            "name": "thumbnail.png",
                            "external": {
                                "url": image_url
                            }
                        }
                    ]
                }

        print("Notion request data:", json.dumps(notion_data, indent=2))

        # Make the request to Notion API
        response = requests.post(
            "https://api.notion.com/v1/pages",
            headers={
                "Authorization": f"Bearer {NOTION_API_TOKEN}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28"
            },
            json=notion_data
        )
        
        print(f"Create Page Response Status: {response.status_code}")
        print(f"Create Page Response Body: {response.text}")
        
        if response.status_code != 200:
            error_message = f"Notion API Error: {response.status_code} - {response.text}"
            print(error_message)
            return jsonify({"error": error_message}), response.status_code
            
        return jsonify({"message": "Successfully saved to Notion", "data": response.json()}), 200
        
    except requests.exceptions.RequestException as e:
        print(f"Notion API Error: {str(e)}")
        if hasattr(e.response, 'text'):
            print(f"Notion API Error Response: {e.response.text}")
        return jsonify({"error": f"Failed to communicate with Notion API: {str(e)}"}), 500
    except Exception as e:
        print(f"Server Error: {str(e)}")
        print("Traceback:", traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route(f'{BASE_PATH}/images/<path:filename>')
def serve_image(filename):
    try:
        return send_from_directory('static/images', filename)
    except Exception as e:
        print(f"Error serving image {filename}: {str(e)}")
        return jsonify({'error': 'Image not found'}), 404

# Add a route to serve static images directly
@app.route('/static/images/<path:filename>')
def serve_static_image(filename):
    try:
        return send_from_directory('static/images', filename)
    except Exception as e:
        print(f"Error serving static image {filename}: {str(e)}")
        return jsonify({'error': 'Image not found'}), 404

@app.route('/api/machine-status')
def get_machine_status():
    try:
        url = f'https://api.notion.com/v1/pages/{NOTION_TARGET_ID}'
        headers = {
            'Authorization': f'Bearer {NOTION_API_TOKEN}',
            'Notion-Version': '2022-06-28'
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        status = data['properties'].get('Status', {}).get('status', {}).get('name', 'Idle')
        return jsonify({'status': status})
    except Exception as e:
        print(f"Error fetching machine status: {e}")
        return jsonify({'status': 'Idle'})

@app.route('/api/generate', methods=['POST'])
def generate_content():
    try:
        system_prompt = """You are a creative writing assistant. Your task is to generate engaging stories based on the user's input.
Please provide your response in the following JSON structure:
{
    "title": "Story Title",
    "story": "Full story content...",
    "summary": {
        "points": [
            "First key point in simple 6th-grade language",
            "Second key point explaining what happens next",
            "Third point about how the story ends",
            // Add 2-3 more points as needed
        ]
    },
    "metadata": {
        "tone": "happy/sad/mysterious/etc",
        "wordCount": 123,
        "targetAudience": "children/young adult/adult",
        "genre": "fantasy/mystery/etc"
    }
}

Keep the summary points simple and easy to understand, as if explaining to a 6th-grade student.
Each point should be a complete thought that helps understand the story's progression.
IMPORTANT: Do not use asterisks (*) anywhere in your response.
"""
        response = model.generate_content(system_prompt)
        content = response.text
        
        # Remove any asterisks from the response
        content = content.replace('*', '')
        
        try:
            content_json = json.loads(content)
            title = content_json.get('title', '')
            story = content_json.get('story', '')
            
            # Ensure no asterisks in the output
            title = title.replace('*', '')
            story = story.replace('*', '')
        except json.JSONDecodeError:
            lines = content.split('\n')
            title = next((line for line in lines if line.strip()), '')
            story = ' '.join(line for line in lines[1:] if line.strip())
            
            # Ensure no asterisks in the output
            title = title.replace('*', '')
            story = story.replace('*', '')
            
        return jsonify({'success': True, 'title': title, 'story': story})
    except Exception as e:
        print(f"Error generating content: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/generate-custom', methods=['POST'])
def generate_custom():
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        system_instruction = data.get('system_instruction', '')
        if not prompt:
            return jsonify({'success': False, 'error': 'Prompt is required'}), 400

        # Add structured output requirements
        structured_output_guide = """
You MUST respond in the following JSON format ONLY:
{
    "title": "The story title here",
    "story": "The full story content here",
    "summary": {
        "points": [
            "First key point in simple 6th-grade language",
            "Second key point explaining what happens next",
            "Third point about how the story ends",
            "Add 2-3 more points as needed"
        ]
    }
}

Rules:
1. The response must be valid JSON
2. Do not include any text outside the JSON structure
3. Do not use markdown or formatting in the content
4. Avoid using double quotes (") inside story text
5. Keep the title concise and engaging
6. Keep summary points simple and easy to understand, as if explaining to a 6th-grade student
7. Each summary point should be a complete thought that helps understand the story's progression
8. IMPORTANT: Do not use asterisks (*) anywhere in your response
"""
        complete_system_instruction = f"{system_instruction}\n\n{structured_output_guide}"

        # Gemini expects a list of content parts with valid roles
        contents = []
        if complete_system_instruction:
            contents.append({'role': 'user', 'parts': [{'text': complete_system_instruction}]})
        contents.append({'role': 'user', 'parts': [{'text': prompt}]})
        
        response = model.generate_content(contents)
        content = response.text
        
        # Remove any asterisks from the response
        content = content.replace('*', '')
        
        return jsonify({'success': True, 'result': content})
    except Exception as e:
        print(f"Error in custom generate: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def update_status_background(new_status):
    try:
        url = f'https://api.notion.com/v1/pages/{NOTION_TARGET_ID}'
        headers = {
            'Authorization': f'Bearer {NOTION_API_TOKEN}',
            'Notion-Version': '2022-06-28',
            'Content-Type': 'application/json'
        }
        
        data = {
            "properties": {
                "Status": {
                    "status": {
                        "name": new_status
                    }
                }
            }
        }
        
        response = requests.patch(url, headers=headers, json=data)
        response.raise_for_status()
        print(f"Background status update completed: {new_status}")
    except Exception as e:
        print(f"Error in background status update: {e}")

@app.route('/api/update-status', methods=['POST'])
def update_status():
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        if not new_status:
            return jsonify({'error': 'Status is required'}), 400

        # Start background thread for status update
        Thread(target=update_status_background, args=(new_status,)).start()
        
        return jsonify({'success': True, 'status': new_status, 'message': 'Status update initiated'})
    except Exception as e:
        print(f"Error initiating status update: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/save-prompt', methods=['POST'])
def save_prompt():
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        system_instruction = data.get('system_instruction', '')
        api_key = data.get('api_key', '')
        
        if not prompt:
            return jsonify({'success': False, 'error': 'Prompt is required'}), 400
            
        # Add structured output requirements to system instruction
        structured_output_guide = """
You MUST respond in the following JSON format ONLY:
{
    "title": "The story title here",
    "story": "The full story content here",
    "metadata": {
        "tone": "emotional/funny/serious/etc",
        "wordCount": number,
        "targetAudience": "children/adults/etc",
        "genre": "story genre here"
    }
}

Rules:
1. The response must be valid JSON
2. Do not include any text outside the JSON structure
3. Do not use markdown or formatting in the content
4. Avoid using double quotes (") inside story text
5. Keep the title concise and engaging
6. Include all metadata fields
7. IMPORTANT: Do not use asterisks (*) anywhere in your response
"""
        complete_system_instruction = f"{system_instruction}\n\n{structured_output_guide}"
            
        # Save to backend file
        success = save_custom_prompts(prompt, system_instruction)
        if not success:
            return jsonify({'success': False, 'error': 'Failed to save prompts'}), 500
            
        # Generate content with the new prompts
        contents = []
        if complete_system_instruction:
            contents.append({'role': 'user', 'parts': [{'text': complete_system_instruction}]})
        contents.append({'role': 'user', 'parts': [{'text': prompt}]})
        
        # Use provided API key if available, otherwise use default model
        if api_key:
            try:
                # Initialize a new model instance with the provided API key
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                custom_model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17s')
                response = custom_model.generate_content(contents)
            except Exception as e:
                print(f"Error with custom API key: {e}")
                # Fall back to default model
                response = model.generate_content(contents)
        else:
            response = model.generate_content(contents)
            
        content = response.text
        
        # Remove any asterisks from the response
        content = content.replace('*', '')
        
        return jsonify({'success': True, 'result': content})
    except Exception as e:
        print(f"Error in save_prompt: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/get-custom-prompt', methods=['GET'])
def get_custom_prompt():
    try:
        custom_prompts = load_custom_prompts()
        return jsonify({
            'success': True,
            'custom_prompt': custom_prompts.get('custom_prompt', ''),
            'system_instruction': custom_prompts.get('system_instruction', '')
        })
    except Exception as e:
        print(f"Error getting custom prompt: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/update-system-prompt', methods=['POST'])
def update_system_prompt():
    try:
        data = request.get_json()
        system_instruction = data.get('system_instruction', '')
        
        # Get existing custom prompts
        custom_prompts = load_custom_prompts()
        custom_prompt = custom_prompts.get('custom_prompt', '')
        
        # Update system instruction but keep the custom prompt
        save_custom_prompts(custom_prompt, system_instruction)
        
        return jsonify({
            'success': True,
            'message': 'System prompt updated successfully'
        })
    except Exception as e:
        print(f"Error updating system prompt: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/generate-summary', methods=['POST'])
def generate_summary():
    try:
        data = request.get_json()
        story = data.get('story', '')
        
        if not story:
            return jsonify({'success': False, 'error': 'No story provided'})
        
        # Prepare the prompt for the AI
        summary_prompt = f"""Please summarize this story in 4-5 simple points (one line each) that a 7th grader could understand. 
        Don't include names or complex details. Make it simple and clear.
        Do NOT use asterisks (*) anywhere in your response.
        
        Story:
        {story}
        
        Please respond in this exact format:
        {{
            "summary": [
                "First point",
                "Second point",
                "Third point",
                "Fourth point",
                "Fifth point"
            ]
        }}
        """
        
        # Get the AI response
        response = model.generate_content(summary_prompt)
        
        # Extract and parse the response
        result = response.text
        
        # Remove any asterisks from the response
        result = result.replace('*', '')
        
        try:
            # Clean up any markdown formatting
            cleaned_result = result.replace('```json', '').replace('```', '').strip()
            summary_data = json.loads(cleaned_result)
            
            # Ensure no asterisks in summary points
            if 'summary' in summary_data and isinstance(summary_data['summary'], list):
                summary_data['summary'] = [point.replace('*', '') for point in summary_data['summary']]
                
            return jsonify({'success': True, 'summary': summary_data['summary']})
        except json.JSONDecodeError:
            return jsonify({'success': False, 'error': 'Failed to parse AI response'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Update the profiles API endpoints to use Notion
@app.route(f'{BASE_PATH}/api/profiles', methods=['GET'])
def get_profiles():
    try:
        print("\n=== GET PROFILES API CALLED ===")
        profiles_data = fetch_profiles_from_notion()
        print(f"Returning {len(profiles_data['profiles'])} profiles to client")
        return jsonify({'success': True, 'profiles': profiles_data['profiles']})
    except Exception as e:
        print(f"ERROR in get_profiles API: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route(f'{BASE_PATH}/api/profiles', methods=['POST'])
def save_profile():
    try:
        print("\n=== SAVE PROFILE API CALLED ===")
        data = request.get_json()
        profile = data.get('profile')
        print(f"Received profile data: {json.dumps(profile, indent=2) if profile else None}")
        
        if not profile:
            print("ERROR: Invalid profile data received")
            return jsonify({'success': False, 'error': 'Invalid profile data'}), 400
            
        result = save_profile_to_notion(profile)
        if not result:
            print("ERROR: Failed to save profile to Notion")
            return jsonify({'success': False, 'error': 'Failed to save profile'}), 500
            
        # Fetch updated profiles list
        print("Fetching updated profiles list after save")
        profiles_data = fetch_profiles_from_notion()
        print(f"Returning {len(profiles_data['profiles'])} profiles to client")
            
        return jsonify({
            'success': True, 
            'message': 'Profile saved successfully',
            'profiles': profiles_data['profiles']
        })
    except Exception as e:
        print(f"ERROR in save_profile API: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route(f'{BASE_PATH}/api/profiles/<profile_id>', methods=['DELETE'])
def delete_profile(profile_id):
    try:
        print(f"\n=== DELETE PROFILE API CALLED FOR {profile_id} ===")
        success = delete_profile_from_notion(profile_id)
        
        if not success:
            print(f"ERROR: Failed to delete profile {profile_id}")
            return jsonify({'success': False, 'error': 'Failed to delete profile'}), 500
            
        # Fetch updated profiles list
        print("Fetching updated profiles list after delete")
        profiles_data = fetch_profiles_from_notion()
        print(f"Returning {len(profiles_data['profiles'])} profiles to client")
            
        return jsonify({
            'success': True, 
            'message': 'Profile deleted successfully',
            'profiles': profiles_data['profiles']
        })
    except Exception as e:
        print(f"ERROR in delete_profile API: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route(f'{BASE_PATH}/api/profiles/<profile_id>/set-active', methods=['POST'])
def set_active_profile(profile_id):
    try:
        print(f"\n=== SET ACTIVE PROFILE API CALLED FOR {profile_id} ===")
        
        # First, set all profiles to inactive
        profiles_response = requests.post(
            f"https://api.notion.com/v1/databases/{PROFILES_DATABASE_ID}/query",
            headers={
                "Authorization": f"Bearer {NOTION_API_TOKEN}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            }
        )
        
        if profiles_response.status_code != 200:
            print("Failed to fetch profiles")
            return jsonify({'success': False, 'error': 'Failed to fetch profiles'}), 500
            
        profiles = profiles_response.json().get('results', [])
        
        # Update all profiles to inactive
        for profile in profiles:
            if profile.get('id') != profile_id:  # Skip the profile we want to make active
                requests.patch(
                    f"https://api.notion.com/v1/pages/{profile.get('id')}",
                    headers={
                        "Authorization": f"Bearer {NOTION_API_TOKEN}",
                        "Notion-Version": "2022-06-28",
                        "Content-Type": "application/json"
                    },
                    json={
                        "properties": {
                            "Active": {
                                "checkbox": False
                            }
                        }
                    }
                )
        
        # Set the target profile to active
        response = requests.patch(
            f"https://api.notion.com/v1/pages/{profile_id}",
            headers={
                "Authorization": f"Bearer {NOTION_API_TOKEN}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            },
            json={
                "properties": {
                    "Active": {
                        "checkbox": True
                    }
                }
            }
        )
        
        if response.status_code != 200:
            print(f"Failed to update active status: {response.status_code}")
            return jsonify({'success': False, 'error': 'Failed to update active status'}), 500
            
        # Fetch updated profiles list
        print("Fetching updated profiles list after setting active")
        profiles_data = fetch_profiles_from_notion()
        print(f"Returning {len(profiles_data['profiles'])} profiles to client")
            
        return jsonify({
            'success': True, 
            'message': 'Active profile updated successfully',
            'profiles': profiles_data['profiles']
        })
    except Exception as e:
        print(f"ERROR in set_active_profile API: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Fix the root route to always have a leading slash
@app.route(f'{BASE_PATH}' if BASE_PATH else '/')
def serve_root():
    return serve_app()

@app.route('/api/upload-image', methods=['POST'])
def upload_image():
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({"success": False, "error": "No image data provided"}), 400
            
        image_data = data.get('image')
        file_name = data.get('fileName', f'image_{uuid.uuid4()}.png')
        image_type = 'thumbnail' if 'thumbnail' in file_name else 'profile'
        
        # Save the image and get the path
        image_path = save_base64_image(image_data, file_name)
        if not image_path:
            return jsonify({"error": "Failed to save image"}), 500
            
        # If we got a Cloudinary URL back, use it directly
        if image_path.startswith('http'):
            return jsonify({
                "url": image_path,
                "success": True
            })
            
        # Otherwise use the local path
        public_url = f"/images/{os.path.basename(image_path)}"
        return jsonify({
            "url": public_url,
            "success": True
        })
        
    except Exception as e:
        print(f"Error uploading image: {e}")
        print(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/notion-stats', methods=['POST'])
def get_notion_stats():
    try:
        data = request.get_json()
        database_id = data.get('databaseId')
        
        if not database_id:
            return jsonify({'success': False, 'error': 'Database ID is required'}), 400
        
        # Fetch all items from the database
        response = requests.post(
            f"https://api.notion.com/v1/databases/{database_id}/query",
            headers={
                "Authorization": f"Bearer {NOTION_API_TOKEN}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            },
            json={}
        )
        
        if response.status_code != 200:
            print(f"Error fetching database: {response.status_code} - {response.text}")
            return jsonify({'success': False, 'error': 'Failed to query Notion database'}), response.status_code
        
        # Parse the response
        data = response.json()
        results = data.get('results', [])
        
        # Count the statuses
        status_counts = {}
        
        for page in results:
            properties = page.get('properties', {})
            status_property = properties.get('Status', {})
            
            # Get the status
            status_value = None
            status_type = status_property.get('type', '')
            
            if status_type == 'status':
                status_value = status_property.get('status', {}).get('name')
            elif status_type == 'select':
                status_value = status_property.get('select', {}).get('name')
            
            # Use "No Status" if no status is found
            status_value = status_value or "No Status"
            
            # Increment the counter for this status
            if status_value in status_counts:
                status_counts[status_value] += 1
            else:
                status_counts[status_value] = 1
        
        return jsonify({
            'success': True,
            'stats': status_counts,
            'total': len(results)
        })
        
    except Exception as e:
        print(f"Error getting Notion stats: {e}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

# Development server
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=5001, debug=False)

# For Vercel serverless deployment
app = app
