import json
import os
import requests
from services.pocketbase_client import PocketBaseClient

class TestSessionManager:
    """Manages persistence and retrieval of QA testing session records."""

    def __init__(self, pb_client: PocketBaseClient | None = None):
        self.pb_client = pb_client or PocketBaseClient()
        self.collection_id_or_name = os.getenv("PB_TEST_SESSIONS_COLLECTION", "test_sessions")

    def create_session(self, session_data: dict) -> dict:
        """Saves a new testing session record to PocketBase."""
        url = f"{self.pb_client.base_url}/collections/{self.collection_id_or_name}/records"
        payload = {
            "session_id": session_data.get("id"),
            "title": session_data.get("title"),
            "version": session_data.get("version"),
            "status": session_data.get("status", "IN_PROGRESS"),
            "session_data": json.dumps(session_data),  # Stores full nested config structure
        }
        
        response = requests.post(
            url, 
            headers=self.pb_client._get_headers(), 
            json=payload, 
            timeout=10
        )
        
        if response.status_code in (200, 201):
            return response.json()
        raise RuntimeError(f"Failed to create test session ({response.status_code}): {response.text}")

    def fetch_all_sessions(self) -> list[dict]:
        """Fetches all existing test sessions ordered by creation date."""
        url = f"{self.pb_client.base_url}/collections/{self.collection_id_or_name}/records?sort=-created"
        try:
            response = requests.get(
                url, 
                headers=self.pb_client._get_headers(), 
                timeout=10
            )
            if response.status_code == 200:
                items = response.json().get("items", [])
                parsed_sessions = []
                for item in items:
                    if "session_data" in item and item["session_data"]:
                        parsed_sessions.append(json.loads(item["session_data"]))
                    else:
                        parsed_sessions.append(item)
                return parsed_sessions
        except Exception as e:
            print(f"[TestSessionManager Warning] Failed to retrieve sessions: {e}")
        return []