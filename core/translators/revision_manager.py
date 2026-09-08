import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any
from zoneinfo import ZoneInfo


class RevisionManager:
    def __init__(self, storage_dir: str | Path = "revisions"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_history_file(self, filename: str) -> Path:
        clean_stem = Path(filename).stem
        return self.storage_dir / f"{clean_stem}_history.json"

    def get_history(self, filename: str) -> List[Dict[str, Any]]:
        """Retrieves revision records sorted by revision number descending."""
        file_path = self._get_history_file(filename)
        if not file_path.is_file():
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                history = json.load(f)
                return sorted(history, key=lambda x: x.get("revision_number", 0), reverse=True)
        except Exception:
            return []

    def add_revision(self, filename: str, summary: str, updated_by: str = "J. Hepburn") -> Dict[str, Any]:
        """Logs a new revision entry with MST timestamp and change summary."""
        file_path = self._get_history_file(filename)
        history = []

        if file_path.is_file():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []

        next_rev_num = len(history) + 1
        
        # Calculate Mountain Standard Time (MST / UTC-7)
        try:
            local_tz = ZoneInfo("America/Denver")
            now_str = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M %Z")
        except Exception:
            # Fallback for Mountain Daylight Time (UTC-6)
            local_tz = timezone(timedelta(hours=-6))
            now_str = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M MDT")

        new_entry = {
            "revision_number": next_rev_num,
            "timestamp": now_str,
            "updated_by": updated_by,
            "summary": summary or "Saved setting modifications."
        }

        history.append(new_entry)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

        return new_entry