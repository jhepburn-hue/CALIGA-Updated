import os
import httpx


class RelayClient:
    """Client for performing Relay Server requests.

    Attributes:
        is_staging (bool): Flag indicating whether to target the staging environment.
        relay_env (str): String identifier for the relay environment ('staging' or 'prod').
        base_url (str): Base endpoint URL for the Relay API.
    """

    def __init__(self, is_staging: bool = True):
        """Initializes RelayClient with environmental plane settings.

        Args:
            is_staging (bool, optional): True to use staging environment, False for production. Defaults to True.
        """
        self.is_staging = is_staging
        self.relay_env = "staging" if is_staging else "prod"
        self.base_url = os.getenv(
            "RELAY_BASE_URL", "https://wallet-bastion.wavelynxdev.com"
        ).rstrip("/")

    def create_corporate_weblink(
        self, group_id: int, cardholder_data: dict = None
    ) -> dict:
        """Requests creation of a corporate wallet pass web link for a specific group ID.

        Args:
            group_id (int): Target relay group identifier.
            cardholder_data (dict, optional): Dict containing first_name and last_name fields. Defaults to None.

        Returns:
            dict: Status dictionary containing provisioning link and card ID on success, or error details on failure.
        """
        url = f"{self.base_url}/relay/wallet-api/v2/groups/{group_id}/add-corporate-weblink"
        headers = {
            "Content-Type": "application/json",
            "X-Relay-Env": self.relay_env,
        }

        oidc_token = os.getenv("RELAY_OIDC_TOKEN")
        if oidc_token:
            headers["Authorization"] = f"Bearer {oidc_token}"

        payload = {
            "raw_badge_data": "01020304",
            "num_bits_badge": 40,
            "card_profile_data": cardholder_data
            or {"first_name": "Test", "last_name": "User"},
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, headers=headers, json=payload)
                origin = response.headers.get("X-Relay-Origin", "unknown")

                if origin == "relay":
                    stage = response.headers.get("X-Relay-Error-Stage", "unknown")
                    return {
                        "success": False,
                        "error": (
                            f"Relay Error ({stage}):"
                            f" {response.json().get('error', 'Unknown relay issue')}"
                        ),
                    }

                if response.status_code in (200, 201):
                    data = response.json()
                    return {
                        "success": True,
                        "provisioning_link": data.get("provisioning_link"),
                        "virtual_card_id": data.get("virtual_card_id"),
                    }
                return {
                    "success": False,
                    "error": f"Erebus Error ({response.status_code}): {response.text}",
                }
        except Exception as e:
            return {"success": False, "error": str(e)}