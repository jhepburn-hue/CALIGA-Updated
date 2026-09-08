import csv
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import time
import requests

try:
    from google.cloud import storage
except ImportError:
    storage = None

from core.translators.csv_loader import CSVConfigLoader

# Target Firmware Version to Forge GitLab Build ID Mapping (from Caliga core)
FIRMWARE_IDS = {
    "v5.4.11": "422313",
    "v5.4.10": "371132",
    "v5.4.9": "389089",
    "v5.4.8": "320365",
    "v5.4.7": "316551",
    "v5.4.6": "75898",
    "v5.4.5": "66999",
    "v5.4.4": "66999",
    "v5.4.3": "66999",
    "v5.4.2": "3811",
    "v5.4.1": "5480",
    "v5.4.0": "3780",
}


class ForgeClient:
    """Client for interacting with the Forge API and GCS build storage.

    Handles uploading configuration CSVs, triggering build tasks, and
    fetching compiled profile/firmware binary artifacts.

    Attributes:
        base_url (str): Base endpoint URL for the Forge service.
        bucket_name (str): Google Cloud Storage bucket name containing build artifacts.
        user_email (str): Active user email used to structure GCS object key prefixes.
        gcp_project (str): GCP project identifier.
        loader (CSVConfigLoader): CSV loader service instance.
    """

    def __init__(self):
        """Initializes ForgeClient with environment variables and defaults."""
        self.base_url = os.getenv(
            "FORGE_BASE_URL", "https://forge.wavelynxdev.com"
        ).rstrip("/")
        self.bucket_name = os.getenv(
            "FORGE_GCS_BUCKET", "wavelynx_apex_config"
        )
        self.user_email = (
            os.getenv("CALIGA_USER_EMAIL", "jhepburn@wavelynx.com")
            .lower()
            .strip()
        )
        self.gcp_project = os.getenv("GCP_PROJECT_ID", "erebus-257721")
        self.loader = CSVConfigLoader()

    def _get_auth_headers(self) -> dict:
        """Constructs Identity-Aware Proxy (IAP) headers for Forge requests.

        Returns:
            dict: Header mapping containing IAP cookies and User-Agent.
        """
        iap_cookie = os.getenv("ACTIVE_IAP_COOKIE", "").strip()
        iap_uid = os.getenv("ACTIVE_IAP_UID", "112564004525954034965").strip()

        return {
            "Cookie": (
                f"__Host-GCP_IAP_AUTH_TOKEN_A82A7FE83D3A1171={iap_cookie};"
                f" GCP_IAP_UID={iap_uid}"
            ),
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
                " AppleWebKit/537.36 (KHTML, like Gecko)"
            ),
        }

    def _normalize_csv_structure(
        self, raw_csv_path: Path, config_obj=None
    ) -> Path:
        """Sanitizes CSV files prior to Forge POST while preserving data fidelity.

        1. Strips leading/trailing whitespace and flattens embedded newlines.
        2. Preserves exact 'Config ID' values from disk (including 0).
        3. Fills default secondary header fields only when missing.

        Args:
            raw_csv_path (Path): Path to the target raw CSV file.
            config_obj (optional): Loaded configuration instance. Defaults to None.

        Returns:
            Path: Path to the sanitized, normalized output CSV file in debug_output.
        """
        raw_rows = []
        with open(
            raw_csv_path, mode="r", encoding="utf-8", errors="ignore"
        ) as f:
            reader = csv.reader(f)
            for row in reader:
                raw_rows.append([" ".join(cell.split()) for cell in row])

        cleaned_rows = []
        for row in raw_rows:
            clean_row = list(row)
            col_f_header = clean_row[5].lower() if len(clean_row) >= 6 else ""

            if col_f_header == "card type" and (
                len(clean_row) < 7 or not clean_row[6]
            ):
                while len(clean_row) < 6:
                    clean_row.append("")
                clean_row.append("Standard")
            elif col_f_header in [
                "format/bitstream",
                "bitstream",
            ] and (len(clean_row) < 7 or not clean_row[6]):
                while len(clean_row) < 6:
                    clean_row.append("")
                clean_row.append("W26-0")
            elif col_f_header == "facility code" and (
                len(clean_row) < 7 or not clean_row[6]
            ):
                while len(clean_row) < 6:
                    clean_row.append("")
                clean_row.append("0")
            elif col_f_header == "starting badge" and (
                len(clean_row) < 7 or not clean_row[6]
            ):
                while len(clean_row) < 6:
                    clean_row.append("")
                clean_row.append("1")
            else:
                while len(clean_row) > 2 and clean_row[-1] == "":
                    clean_row.pop()
                while len(clean_row) < 6:
                    clean_row.append("")

            cleaned_rows.append(clean_row)

        debug_dir = Path.cwd() / "debug_output"
        debug_dir.mkdir(parents=True, exist_ok=True)

        debug_file_path = debug_dir / f"normalized_{raw_csv_path.name}"

        with open(
            debug_file_path, mode="w", newline="", encoding="utf-8"
        ) as f:
            writer = csv.writer(f)
            writer.writerows(cleaned_rows)

        print(
            "[Forge Client] Normalized CSV generated at:"
            f" {debug_file_path.resolve()}"
        )
        return debug_file_path

    def upload_csv_and_generate_ini(
        self, csv_file_path: Path, target_version: str, config_obj=None
    ) -> str:
        """Uploads a CSV to Forge to generate an INI file in GCS.

        Args:
            csv_file_path (Path): Path to source configuration CSV file.
            target_version (str): Target firmware version (e.g. 'v5.4.11').
            config_obj (optional): Configuration domain object. Defaults to None.

        Returns:
            str: Generated INI file string contents.

        Raises:
            RuntimeError: If connection fails or Forge fails to output the INI.
        """
        headers = self._get_auth_headers()
        import_url = f"{self.base_url}/configs/import"

        normalized_csv_path = self._normalize_csv_structure(
            csv_file_path, config_obj=config_obj
        )

        print(
            f"[Forge Client] POSTing normalized file {normalized_csv_path.name}"
            f" to {import_url}"
        )

        response_text = ""
        try:
            with open(normalized_csv_path, "rb") as f:
                files = {"upload": (csv_file_path.name, f, "text/csv")}
                data = {"target_version": target_version}

                response = requests.post(
                    import_url,
                    files=files,
                    data=data,
                    headers=headers,
                    allow_redirects=True,
                    timeout=30,
                )

            response_text = response.text
            print(
                "[Forge Client] Import POST returned HTTP status:"
                f" {response.status_code}"
            )

        except Exception as e:
            raise RuntimeError(
                f"Network error connecting to Forge service: {e}"
            )

        config_stem = csv_file_path.stem.lower().strip()
        if storage is not None:
            target_prefix = f"forge/{self.user_email}/{target_version}/"
            print(
                "[Forge Client] Polling GCS bucket path for INI:"
                f" gs://{self.bucket_name}/{target_prefix}"
            )

            for attempt in range(1, 10):
                try:
                    storage_client = storage.Client(project=self.gcp_project)
                    blobs = list(
                        storage_client.list_blobs(
                            self.bucket_name, prefix=target_prefix
                        )
                    )

                    for b in blobs:
                        blob_filename = Path(b.name).name.lower()
                        if (
                            blob_filename.endswith(".ini")
                            and config_stem in blob_filename
                        ):
                            print(
                                "[Forge Client] Success! Retrieved INI from"
                                f" GCS: {b.name}"
                            )
                            return b.download_as_bytes().decode(
                                "utf-8", errors="ignore"
                            )

                except Exception as e:
                    print(
                        f"[Forge Client] GCS Exception on attempt {attempt}:"
                        f" {e}"
                    )

                time.sleep(1)

        error_reason = "Forge failed to generate the INI file."
        if response_text:
            body_match = re.search(
                r"<body[^>]*>(.*?)</body>",
                response_text,
                re.DOTALL | re.IGNORECASE,
            )
            if body_match:
                clean_body = re.sub(r"<[^>]+>", " ", body_match.group(1))
                clean_body = " ".join(clean_body.split())
                if (
                    "failed" in clean_body.lower()
                    or "error" in clean_body.lower()
                ):
                    reason_match = re.search(
                        r"(failed.*?\.|error.*?\.)", clean_body, re.IGNORECASE
                    )
                    if reason_match:
                        error_reason = reason_match.group(1)

        raise RuntimeError(f"Forge INI Error: {error_reason}")

    def resolve_actual_ini_name(self, config_name: str, version: str) -> str:
        """Scans GCS for any INI file containing `config_name` in its filename.

        Example: Searching 'CTH2' finds 'CTH2-LK10022.ini' and returns
        'CTH2-LK10022'.

        Args:
            config_name (str): Configuration stem name to search for.
            version (str): Firmware target version string.

        Returns:
            str: Resolved base stem name matching the GCS object.
        """
        if storage is None:
            return config_name
        try:
            storage_client = storage.Client(project=self.gcp_project)
            prefix_path = f"forge/{self.user_email}/{version}/"
            blobs = list(
                storage_client.list_blobs(
                    self.bucket_name, prefix=prefix_path
                )
            )

            cfg_lower = config_name.lower().strip()
            for b in blobs:
                fn_lower = Path(b.name).name.lower()
                if fn_lower.endswith(".ini"):
                    base_name = Path(b.name).stem
                    if (
                        base_name.lower() == cfg_lower
                        or base_name.lower().startswith(f"{cfg_lower}-")
                        or base_name.lower().startswith(f"{cfg_lower}_")
                    ):
                        print(
                            f"[GCS Resolver] Matched INI for '{config_name}' ->"
                            f" '{base_name}' in GCS"
                        )
                        return base_name
        except Exception as e:
            print(f"[GCS Resolver Exception] {e}")

        return config_name

    def trigger_config_build(
        self,
        config_name: str,
        version: str,
        firmware_build_id: str = "",
        source: str = "user",
        firmware_source: str = "Release",
        include_partials: str = "0",
        partial_config_name: str | None = None,
        gitlab_ref: str = "master",
        is_firmware: bool = False,
    ) -> requests.Response:
        """Triggers a compilation job on Forge for a profile or firmware binary artifact.

        Args:
            config_name (str): Configuration profile name.
            version (str): Firmware target version string.
            firmware_build_id (str, optional): Custom build ID override.
              Defaults to "".
            source (str, optional): Trigger source. Defaults to "user".
            firmware_source (str, optional): Firmware build channel source.
              Defaults to "Release".
            include_partials (str, optional): Flag indicating partial builds.
              Defaults to "0".
            partial_config_name (str | None, optional): Partial config stem.
              Defaults to None.
            gitlab_ref (str, optional): GitLab branch reference. Defaults to
              "master".
            is_firmware (bool, optional): Whether compiling firmware or profile.
              Defaults to False.

        Returns:
            requests.Response: Response object returned by Forge endpoint.
        """
        url = f"{self.base_url}/configs/build"
        headers = self._get_auth_headers()

        resolved_name = self.resolve_actual_ini_name(config_name, version)
        build_id = (
            firmware_build_id
            if firmware_build_id
            else FIRMWARE_IDS.get(version, "422313")
        )

        payload = {
            "version": version,
            "cfg": resolved_name,
            "config_name": resolved_name,
            "partial_config_name": (
                partial_config_name if partial_config_name else ""
            ),
            "target_ini": f"{resolved_name}.ini",
            "build_type": "firmware" if is_firmware else "profile",
            "source": source,
            "firmware_source": "Release" if is_firmware else "",
            "firmware_build_id": build_id,
            "gitlab_ref": gitlab_ref,
            "include_partials": include_partials,
        }
        print(f"[Forge Build Request] POST {url}")
        print(f"[Forge Payload] {payload}")

        return requests.post(
            url, data=payload, headers=headers, allow_redirects=False, timeout=30
        )

    def fetch_bin_from_gcs(
        self,
        config_name: str,
        version: str,
        is_firmware: bool = False,
        min_updated_time=None,
    ) -> tuple[bytes | None, str | None]:
        """Searches GCS for any binary file (.bin / .dck) matching the config prefix.

        Args:
            config_name (str): Configuration stem name.
            version (str): Target firmware version string.
            is_firmware (bool, optional): True for .dck files, False for .bin.
              Defaults to False.
            min_updated_time (datetime, optional): Minimal timestamp threshold
              to avoid stale objects. Defaults to None.

        Returns:
            tuple[bytes | None, str | None]: Tuple of (raw binary bytes, filename) if found, else (None, None).
        """
        if storage is None:
            return None, None
        try:
            storage_client = storage.Client(project=self.gcp_project)
            prefix_path = f"forge/{self.user_email}/{version}/"
            blobs = list(
                storage_client.list_blobs(
                    self.bucket_name, prefix=prefix_path
                )
            )

            search_query = config_name.lower().strip().split("-")[0].split("_")[0]
            matching_blob = None

            # Sort blobs by updated timestamp descending so we inspect newest artifacts first
            sorted_blobs = sorted(
                blobs, key=lambda x: x.updated, reverse=True
            )

            for b in sorted_blobs:
                name_lower = Path(b.name).name.lower()

                # Ignore stale leftover blobs updated before this build request started
                if min_updated_time and b.updated < min_updated_time:
                    continue

                if (
                    search_query in name_lower
                    and name_lower.endswith((".bin", ".dck"))
                    and b.size > 0
                ):
                    if is_firmware:
                        if "dck" in name_lower and "module" not in name_lower:
                            matching_blob = b
                            break
                    else:
                        if "dck" not in name_lower and "module" not in name_lower:
                            matching_blob = b
                            break

            if matching_blob:
                filename = Path(matching_blob.name).name
                print(
                    "[GCS Success] Found compiled artifact:"
                    f" {filename} ({matching_blob.size} bytes)"
                )
                return matching_blob.download_as_bytes(), filename
        except Exception as e:
            print(f"[GCS Exception] {e}")

        return None, None

    def upload_csv_and_generate_bin(
        self, csv_file_path: Path, target_version: str, config_obj=None
    ) -> tuple[bytes, str]:
        """Executes full 2-step Forge pipeline for Profile compilation.

        1. Uploads CSV to /configs/import to generate INI in GCS.
        2. Calls /configs/build with build_type='profile' to compile BIN artifact.
        3. Polls GCS for compiled output binary (.bin or .dck).

        Args:
            csv_file_path (Path): Path to source configuration CSV.
            target_version (str): Target firmware version string.
            config_obj (optional): Loaded configuration domain object. Defaults to None.

        Returns:
            tuple[bytes, str]: Tuple containing compiled binary bytes and output filename.

        Raises:
            RuntimeError: If profile compilation times out polling GCS.
        """
        request_start_time = datetime.now(timezone.utc)

        # Step 1: Upload CSV to create INI
        self.upload_csv_and_generate_ini(
            csv_file_path, target_version, config_obj=config_obj
        )
        time.sleep(2)

        config_name = csv_file_path.stem
        resolved_name = self.resolve_actual_ini_name(
            config_name, target_version
        )
        selected_build_id = FIRMWARE_IDS.get(target_version, "422313")

        # Step 2: Trigger Profile BIN Build on Forge
        build_resp = self.trigger_config_build(
            config_name=resolved_name,
            version=target_version,
            firmware_build_id=selected_build_id,
            is_firmware=False,
            include_partials="0",
            gitlab_ref="master",
        )
        print(
            "[Forge Client] Build POST returned status:"
            f" {build_resp.status_code}"
        )

        # Step 3: Poll GCS bucket for output binary artifact (20 attempts x 3s)
        target_prefix = f"forge/{self.user_email}/{target_version}/"
        print(
            "[GCS Polling] Waiting for Forge build output for"
            f" '{resolved_name}' ({target_version})..."
        )

        for attempt in range(1, 21):
            time.sleep(3)
            bin_bytes, downloaded_filename = self.fetch_bin_from_gcs(
                config_name=resolved_name,
                version=target_version,
                is_firmware=False,
                min_updated_time=request_start_time,
            )
            if bin_bytes:
                print(
                    "[GCS Polling] Artifact ready on attempt"
                    f" #{attempt}: {downloaded_filename}"
                )
                return bin_bytes, downloaded_filename

        raise RuntimeError(
            "Forge BIN Error: Profile compilation timed out waiting for GCS"
            f" artifact for '{config_name}'."
        )

    def upload_csv_and_generate_firmware(
        self, csv_file_path: Path, target_version: str, config_obj=None
    ) -> tuple[bytes, str]:
        """Executes the 2-step Forge pipeline for Firmware DCK compilation.

        1. Uploads CSV to /configs/import to ensure target INI exists in GCS.
        2. Calls /configs/build with build_type='firmware' and firmware_source='Release'.
        3. Polls GCS for the compiled firmware DCK artifact (.dck).

        Args:
            csv_file_path (Path): Path to configuration CSV file.
            target_version (str): Target firmware version string.
            config_obj (optional): Loaded configuration domain object. Defaults to None.

        Returns:
            tuple[bytes, str]: Tuple containing compiled firmware bytes and filename.

        Raises:
            RuntimeError: If firmware compilation times out polling GCS.
        """
        request_start_time = datetime.now(timezone.utc)

        # Step 1: Ensure INI exists in GCS
        self.upload_csv_and_generate_ini(
            csv_file_path, target_version, config_obj=config_obj
        )
        time.sleep(2)

        config_name = csv_file_path.stem
        resolved_name = self.resolve_actual_ini_name(
            config_name, target_version
        )
        selected_build_id = FIRMWARE_IDS.get(target_version, "422313")

        # Step 2: Trigger Firmware DCK Build on Forge
        build_resp = self.trigger_config_build(
            config_name=resolved_name,
            version=target_version,
            firmware_build_id=selected_build_id,
            firmware_source="Release",
            include_partials="0",
            gitlab_ref="master",
            is_firmware=True,
        )
        print(
            "[Forge Client] Firmware Build POST returned status:"
            f" {build_resp.status_code}"
        )

        # Step 3: Poll GCS bucket for compiled Firmware DCK artifact (20 attempts x 3s)
        target_prefix = f"forge/{self.user_email}/{target_version}/"
        print(
            "[GCS Polling] Waiting for Forge Firmware DCK output for"
            f" '{resolved_name}' ({target_version})..."
        )

        for attempt in range(1, 21):
            time.sleep(3)
            bin_bytes, downloaded_filename = self.fetch_bin_from_gcs(
                config_name=resolved_name,
                version=target_version,
                is_firmware=True,
                min_updated_time=request_start_time,
            )
            if bin_bytes:
                print(
                    "[GCS Polling] Firmware DCK ready on attempt"
                    f" #{attempt}: {downloaded_filename}"
                )
                return bin_bytes, downloaded_filename

        raise RuntimeError(
            "Forge Firmware Error: Firmware compilation timed out waiting for"
            f" GCS artifact for '{config_name}'."
        )

    def generate_tokens_flow(
        self, csv_file_path: Path, target_version: str, config_obj=None
    ) -> dict:
        """Executes full profile and firmware compilation flow to register PocketBase tokens.

        Args:
            csv_file_path (Path): Path to configuration CSV file.
            target_version (str): Target firmware version string.
            config_obj (optional): Loaded configuration domain object. Defaults to None.

        Returns:
            dict: Results map containing token names, cached states, and token values.
        """
        from services.pocketbase_client import PocketBaseClient

        config_name = csv_file_path.stem.upper()
        # Strip leading 'v' to match PocketBase naming (e.g. 'v5.4.11' -> '5.4.11')
        clean_version = target_version.lstrip("v")

        profile_token_name = f"{clean_version} {config_name} PROFILE"
        firmware_token_name = f"{clean_version} {config_name} FIRMWARE"

        pb_client = PocketBaseClient()

        # 1. Search PocketBase for existing active tokens
        cached_profile_token = pb_client.check_active_token(
            profile_token_name
        )
        cached_firmware_token = pb_client.check_active_token(
            firmware_token_name
        )

        results = {
            "profile_token_name": profile_token_name,
            "profile_token": cached_profile_token,
            "profile_cached": bool(cached_profile_token),
            "firmware_token_name": firmware_token_name,
            "firmware_token": cached_firmware_token,
            "firmware_cached": bool(cached_firmware_token),
        }

        # 2. Compile & Upload Profile Token if missing
        if not cached_profile_token:
            print(
                f"[Tokens Flow] Compiling Profile BIN for '{profile_token_name}'..."
            )
            try:
                bin_bytes, downloaded_fn = self.upload_csv_and_generate_bin(
                    csv_file_path, target_version, config_obj=config_obj
                )

                temp_dir = Path("/tmp/tokens")
                temp_dir.mkdir(parents=True, exist_ok=True)
                temp_path = temp_dir / downloaded_fn
                with open(temp_path, "wb") as f:
                    f.write(bin_bytes)

                new_profile_token = pb_client.create_token_record(
                    profile_token_name, temp_path
                )
                temp_path.unlink(missing_ok=True)

                results["profile_token"] = new_profile_token
            except Exception as e:
                print(f"[Tokens Flow Error - Profile] {e}")
                results["profile_token"] = f"Compilation Error: {e}"

        # 3. Compile & Upload Firmware Token if missing
        if not cached_firmware_token:
            print(
                "[Tokens Flow] Compiling Firmware DCK for"
                f" '{firmware_token_name}'..."
            )
            try:
                dck_bytes, downloaded_dck_fn = (
                    self.upload_csv_and_generate_firmware(
                        csv_file_path, target_version, config_obj=config_obj
                    )
                )

                temp_dir = Path("/tmp/tokens")
                temp_dir.mkdir(parents=True, exist_ok=True)
                temp_path = temp_dir / downloaded_dck_fn
                with open(temp_path, "wb") as f:
                    f.write(dck_bytes)

                new_fw_token = pb_client.create_token_record(
                    firmware_token_name, temp_path
                )
                temp_path.unlink(missing_ok=True)

                results["firmware_token"] = new_fw_token
            except Exception as e:
                print(f"[Tokens Flow Error - Firmware] {e}")
                results["firmware_token"] = f"Compilation Error: {e}"

        return results