import requests
import os
import time
import subprocess
import signal
import sys

# Notion API configuration
NOTION_API_KEY = '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'
DATABASE_ID = '1dde05eb-c9e2-804a-ae01-f673cb3302fa'
TARGET_ID = '1dee05eb-c9e2-80b5-a512-d5e2af5617f9'
TARGET_STATUS = 'Rendering'

def update_status(new_status):
    url = f'https://api.notion.com/v1/pages/{TARGET_ID}'
    
    headers = {
        'Authorization': f'Bearer {NOTION_API_KEY}',
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
    
    try:
        response = requests.patch(url, headers=headers, json=data)
        response.raise_for_status()
        print(f"Status updated to: {new_status}")
    except requests.exceptions.RequestException as e:
        print(f"Error updating status: {e}")

def fetch_database_item():
    url = f'https://api.notion.com/v1/databases/{DATABASE_ID}/query'
    
    headers = {
        'Authorization': f'Bearer {NOTION_API_KEY}',
        'Notion-Version': '2022-06-28',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if data['results']:
            for item in data['results']:
                if item['id'] == TARGET_ID:
                    status = item['properties'].get('Status', {}).get('status', {}).get('name', 'No status')
                    return {
                        'id': item['id'],
                        'status': status
                    }
        return None
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching from Notion: {e}")
        return None

def run_apprun():
    try:
        print("\n=== Starting apprun.py ===")
        process = subprocess.Popen(['python', 'apprun.py'], 
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,
                                 universal_newlines=True)
        
        # Read and print output in real-time
        for line in process.stdout:
            print(line.strip())
            
        process.wait()
        print("Run completed ===> [Status: Cooldown] <=== Wait 20 seconds")
        update_status("Cooldown")
        time.sleep(20)
        update_status("Idle")
    except Exception as e:
        print(f"Error running apprun.py: {e}")

def signal_handler(sig, frame):
    print("\nScript is stopping...")
    update_status("Idle")
    sys.exit(0)

def monitor_status():
    print("\n" + "="*50)
    print(f"Starting monitoring for ID: {TARGET_ID}")
    print("Waiting for status to change to 'Rendering'...")
    print("="*50 + "\n")
    
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        while True:
            result = fetch_database_item()
            if result:
                current_time = time.strftime("%H:%M:%S")
                print(f"[{current_time}] Current status: {result['status']}")
                if result['status'] == TARGET_STATUS:
                    print("\n" + "*"*50)
                    print(f"Status changed to {TARGET_STATUS}! Triggering apprun.py...")
                    print("*"*50 + "\n")
                    run_apprun()
                else:
                    time.sleep(2)  # Check every 2 seconds
            else:
                print("\n[-] No matching item found in database")
                time.sleep(60)  # Wait 1 minute before retrying
    except Exception as e:
        print("\n" + "!"*50)
        print(f"An error occurred: {e}")
        print("!"*50 + "\n")
        update_status("Idle")
        raise

if __name__ == "__main__":
    try:
        monitor_status()
    except KeyboardInterrupt:
        print("\nScript interrupted by user")
        update_status("Idle")
    except Exception as e:
        print(f"Script stopped due to error: {e}")
        update_status("Idle")