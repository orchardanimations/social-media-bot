import os
import json
import requests
import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- CONFIGURATION FROM GITHUB SECRETS ---
GCP_SA_KEY = json.loads(os.environ.get("GCP_SA_KEY"))
TO_POST_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID")
API_KEY = os.environ.get("GEMINI_API_KEY")
WEBHOOK_URL = os.environ.get("PUSHCUT_WEBHOOK_URL")

# Initialize Gemini
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def get_drive_service():
    credentials = service_account.Credentials.from_service_account_info(
        GCP_SA_KEY, scopes=['https://www.googleapis.com/auth/drive.readonly']
    )
    return build('drive', 'v3', credentials=credentials)

def generate_description(activity):
    prompt = f"Write a 100 word description of movie Sonic, movie Tails, movie Knuckles and movie Shadow doing {activity}."
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Error generating text: {e}")
        return None

def process_queue():
    service = get_drive_service()

    # 1. Find the first subfolder inside the 'topost' directory
    query = f"'{TO_POST_FOLDER_ID}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)", pageSize=1).execute()
    folders = results.get('files', [])

    if not folders:
        print("No folders found in the queue.")
        return

    target_folder = folders[0]
    folder_name = target_folder['name']
    folder_id = target_folder['id']
    
    print(f"--- Processing: {folder_name} ---")

    # 2. Get the 4 images inside this subfolder
    img_query = f"'{folder_id}' in parents and trashed=false"
    img_results = service.files().list(q=img_query, fields="files(id, name, webContentLink)").execute()
    images = img_results.get('files', [])

    image_urls = [img.get('webContentLink') for img in images if img.get('webContentLink')]

    if len(image_urls) < 4:
        print(f"Found fewer than 4 images in {folder_name}. Exiting to prevent partial posts.")
        return

    # 3. Generate the AI Description
    description = generate_description(folder_name)
    if not description: return

    # 4. Fire the Webhook to your iPhone
    payload = {
        "description": description,
        "image_urls": image_urls,
        "folder_name": folder_name # Passing this so iOS can find and move it later
    }

    print("Firing Webhook to iPhone...")
    response = requests.post(WEBHOOK_URL, json=payload)
    print(f"Webhook Status: {response.status_code}")

if __name__ == "__main__":
    process_queue()
