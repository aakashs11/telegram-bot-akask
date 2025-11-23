"""
Google Drive Service.
Handles interaction with Google Drive API to list and retrieve files.
"""

import logging
import os
from typing import List, Dict, Any
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from config.settings import CREDENTIALS_FILE

logger = logging.getLogger(__name__)

class DriveService:
    """
    Service to interact with Google Drive API.
    """
    
    # Scopes: Read/Write access to Drive
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
    def __init__(self):
        self.creds = self._get_credentials()
        self.service = build('drive', 'v3', credentials=self.creds)

    def _get_credentials(self):
        """Load credentials from service account file"""
        if os.path.exists(CREDENTIALS_FILE):
            return Credentials.from_service_account_file(
                CREDENTIALS_FILE, scopes=self.SCOPES
            )
        else:
            # Fallback to default (not ideal for service account but good for local dev)
            import google.auth
            creds, _ = google.auth.default(scopes=self.SCOPES)
            return creds

    def list_files_in_folder(self, folder_id: str, current_path: str = "") -> List[Dict[str, Any]]:
        """
        Recursively list all files in a folder, including their path.
        
        Args:
            folder_id: The ID of the Google Drive folder to scan.
            current_path: The path to the current folder (used for recursion).
            
        Returns:
            List of file dictionaries containing metadata and 'path'.
        """
        files = []
        page_token = None
        
        try:
            while True:
                query = f"'{folder_id}' in parents and trashed = false"
                
                results = self.service.files().list(
                    q=query,
                    pageSize=1000,
                    fields="nextPageToken, files(id, name, mimeType, webViewLink, parents)",
                    pageToken=page_token
                ).execute()
                
                items = results.get('files', [])
                
                for item in items:
                    if item['mimeType'] == 'application/vnd.google-apps.folder':
                        # Track folder metadata
                        folder_name = item['name']
                        new_path = f"{current_path}/{folder_name}" if current_path else folder_name
                        item['path'] = new_path
                        files.append(item)  # Add folder to list
                        
                        # Recursively scan subfolders
                        logger.info(f"Scanning subfolder: {new_path}")
                        files.extend(self.list_files_in_folder(item['id'], new_path))
                    else:
                        item['path'] = current_path
                        files.append(item)
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
                    
            return files
            
        except Exception as e:
            logger.error(f"Error listing Drive files: {e}")
            return []
                    
    def get_or_create_folder(self, folder_name: str, parent_id: str = None) -> str:
        """Get folder ID by name, creating it if it doesn't exist."""
        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
            
        results = self.service.files().list(q=query, fields="files(id)").execute()
        files = results.get('files', [])
        
        if files:
            return files[0]['id']
            
        # Create folder
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            file_metadata['parents'] = [parent_id]
            
        file = self.service.files().create(body=file_metadata, fields='id').execute()
        return file.get('id')

    def upload_json_file(self, filename: str, content: Dict, folder_id: str):
        """Upload a JSON dictionary as a file to Drive."""
        import json
        from googleapiclient.http import MediaIoBaseUpload
        import io
        
        # Check if file exists to update it
        query = f"name = '{filename}' and '{folder_id}' in parents and trashed = false"
        results = self.service.files().list(q=query, fields="files(id)").execute()
        files = results.get('files', [])
        
        file_content = json.dumps(content, indent=2)
        media = MediaIoBaseUpload(io.BytesIO(file_content.encode('utf-8')), mimetype='application/json')
        
        if files:
            # Update existing
            file_id = files[0]['id']
            self.service.files().update(
                fileId=file_id,
                media_body=media
            ).execute()
            logger.info(f"Updated {filename} in Drive (ID: {file_id})")
        else:
            # Create new
            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            logger.info(f"Created {filename} in Drive")

    def download_json_file(self, filename: str, folder_id: str) -> Dict:
        """Download and parse a JSON file from Drive."""
        import json
        
        query = f"name = '{filename}' and '{folder_id}' in parents and trashed = false"
        results = self.service.files().list(q=query, fields="files(id)").execute()
        files = results.get('files', [])
        
        if not files:
            return None
            
        file_id = files[0]['id']
        content = self.service.files().get_media(fileId=file_id).execute()
        return json.loads(content.decode('utf-8'))
