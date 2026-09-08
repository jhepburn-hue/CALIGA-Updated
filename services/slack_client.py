import os
from typing import List
from dotenv import load_dotenv
import requests

load_dotenv()


class SlackNotificationManager:
    """Manager class for formatting and transmitting webhooks to Slack.

    Attributes:
        webhook_url (str | None): Configured Slack incoming webhook URL.
    """

    def __init__(self):
        """Initializes SlackNotificationManager with webhook URL configuration."""
        self.webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    def _get_webhook_url(self) -> str | None:
        """Retrieves the active webhook URL from instance state or environment.

        Returns:
            str | None: Slack incoming webhook URL string or None if unconfigured.
        """
        if not self.webhook_url:
            self.webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        return self.webhook_url

    def send_new_config_notification(
        self,
        config_name: str,
        dec_id: int,
        hex_id: str,
        updated_by: str = "J. Hepburn",
    ) -> bool:
        """Sends a dedicated Slack notification when a new configuration is created.

        Args:
            config_name (str): The configuration profile name.
            dec_id (int): Configuration integer decimal ID.
            hex_id (str): Formatted hex string representation of the config ID.
            updated_by (str, optional): User name triggering the creation. Defaults to "J. Hepburn".

        Returns:
            bool: True if Slack accepted the webhook (HTTP 200), False otherwise.
        """
        url = self._get_webhook_url()
        if not url:
            print("[Slack] Notification skipped: SLACK_WEBHOOK_URL not configured.")
            return False

        payload = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"New Configuration Created: {config_name}",
                        "emoji": False,
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Configuration:*\n`{config_name}`"},
                        {"type": "mrkdwn", "text": f"*Created By:*\n{updated_by}"},
                        {"type": "mrkdwn", "text": f"*Decimal ID:*\n{dec_id}"},
                        {"type": "mrkdwn", "text": f"*Hex ID:*\n`{hex_id}`"},
                        {"type": "mrkdwn", "text": "*Initial Status:*\n*POC*"},
                    ],
                },
            ]
        }

        try:
            res = requests.post(url, json=payload, timeout=5)
            if res.status_code == 200:
                print(f"[Slack] New config notification sent for {config_name}.")
                return True
            else:
                print(f"[Slack] Webhook error {res.status_code}: {res.text}")
                return False
        except Exception as e:
            print(f"[Slack] Error sending new config notification: {e}")
            return False

    def send_status_change_notification(
        self,
        config_name: str,
        old_status: str,
        new_status: str,
        updated_by: str = "J. Hepburn",
    ) -> bool:
        """Sends a Slack alert when a configuration profile status changes.

        Args:
            config_name (str): Configuration profile stem name.
            old_status (str): Previous status string.
            new_status (str): New updated status string.
            updated_by (str, optional): User name performing update. Defaults to "J. Hepburn".

        Returns:
            bool: True if message sent successfully, False otherwise.
        """
        url = self._get_webhook_url()
        if not url:
            print("[Slack] Notification skipped: SLACK_WEBHOOK_URL not configured.")
            return False

        payload = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"Configuration Status Update: {config_name}",
                        "emoji": False,
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Configuration:*\n`{config_name}`"},
                        {"type": "mrkdwn", "text": f"*Updated By:*\n{updated_by}"},
                        {"type": "mrkdwn", "text": f"*Previous Status:*\n{old_status}"},
                        {"type": "mrkdwn", "text": f"*New Status:*\n*{new_status}*"},
                    ],
                },
            ]
        }

        try:
            res = requests.post(url, json=payload, timeout=5)
            return res.status_code == 200
        except Exception as e:
            print(f"[Slack] Error sending status change notification: {e}")
            return False

    def send_batch_update_notification(
        self, config_name: str, changes: List[str], updated_by: str = "J. Hepburn"
    ) -> bool:
        """Sends a Slack notification summarizing batched field modifications.

        Args:
            config_name (str): Target configuration profile name.
            changes (List[str]): Itemized list of formatted setting diff strings.
            updated_by (str, optional): User performing batch save. Defaults to "J. Hepburn".

        Returns:
            bool: True if notification sent successfully, False otherwise.
        """
        url = self._get_webhook_url()
        if not url:
            print("[Slack] Notification skipped: SLACK_WEBHOOK_URL not configured.")
            return False

        if not changes:
            return True

        changes_formatted = "\n".join(changes)

        payload = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"Configuration Saved: {config_name}",
                        "emoji": False,
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Configuration:*\n`{config_name}`"},
                        {"type": "mrkdwn", "text": f"*Updated By:*\n{updated_by}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Modified Settings:*\n```{changes_formatted}```",
                    },
                },
            ]
        }

        try:
            res = requests.post(url, json=payload, timeout=5)
            return res.status_code == 200
        except Exception as e:
            print(f"[Slack] Error sending batch update notification: {e}")
            return False

    def send_test_failure_notification(
        self,
        config_name: str,
        version: str,
        tester_name: str,
        failed_tests: list,
        comments: str,
    ) -> bool:
        """Sends a richly formatted Slack notification when a test run failure is submitted.

        Args:
            config_name (str): Configuration under test.
            version (str): Target firmware version under test.
            tester_name (str): Assigned tester name submitting failure report.
            failed_tests (list): List of dicts containing 'title' and 'details' of failed checks.
            comments (str): Tester failure notes/comments.

        Returns:
            bool: True if alert successfully transmitted to Slack, False otherwise.
        """
        url = self._get_webhook_url()
        if not url:
            print("[Slack] Notification skipped: SLACK_WEBHOOK_URL not configured.")
            return False

        failed_bullets = "\n".join(
            [f"• *{test['title']}*\n   _{test['details']}_" for test in failed_tests]
        )

        payload = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"Test Failure Report: {config_name} ({version})",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Configuration:*\n`{config_name}`"},
                        {"type": "mrkdwn", "text": f"*Firmware Target:*\n`{version}`"},
                        {"type": "mrkdwn", "text": f"*Tester:*\n{tester_name}"},
                        {"type": "mrkdwn", "text": "*Status:*\n*FAILED*"},
                    ],
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Failed Checks:*\n{failed_bullets}",
                    },
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Tester Comments:*\n>{comments}",
                    },
                },
            ]
        }

        try:
            res = requests.post(url, json=payload, timeout=5)
            return res.status_code == 200
        except Exception as e:
            print(f"[Slack] Error sending failure notification: {e}")
            return False