from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request

from core.translators.csv_loader import CSVConfigLoader
from services.forge_client import ForgeClient
from services.osdp_flasher import OsdpFlasher
from services.slack_client import SlackNotificationManager

testing_bp = Blueprint("testing", __name__, url_prefix="/testing")
loader = CSVConfigLoader()
slack_manager = SlackNotificationManager()

# In-memory store: { "v5.4.11": { "session_123": { "id": ..., "created_at": ..., "configs": { ... } } } }
VERSION_SESSIONS = {}

TEAM_MEMBERS = [
    "Unassigned",
    "J. Hepburn",
    "Kris",
    "Nate",
    "Jacob",
    "Dinesh",
    "Rich Crowder",
]

SUPPORTED_FIRMWARE_VERSIONS = [f"v5.4.{i}" for i in range(11, 5, -1)]


def generate_structured_sections(config_obj) -> list[dict]:
    """Generates structured test card sections with clean key-value dictionaries.

    Args:
        config_obj: The loaded configuration object.

    Returns:
        list[dict]: A list of section dictionaries containing criteria and status.
    """
    sections = []

    # 1. Verify AV and Output Formats
    idle_led = getattr(config_obj.audio_visual, "idle_led_color", "Red")
    cred_led = getattr(config_obj.audio_visual, "credential_led_color", "Green")
    beeper = "On" if getattr(config_obj.audio_visual, "beeper_enabled", True) else "Off"
    keypad_fmt = getattr(config_obj.audio_visual, "keypad_format", "8-bit")
    tamper = "On" if getattr(config_obj.audio_visual, "tamper_monitoring", True) else "Off"

    sections.append(
        {
            "section_id": "av_outputs",
            "title": "Verify AV and Output Formats.",
            "status": "UNTESTED",
            "criteria": [
                {"label": "Idle LED", "value": idle_led},
                {"label": "Credential Report LED", "value": cred_led},
                {"label": "Beeper", "value": beeper},
                {"label": "Keypad Format", "value": keypad_fmt},
                {"label": "Tampering Monitoring", "value": tamper},
                {
                    "label": "Config ID",
                    "value": f"{config_obj.config_id_dec} ({config_obj.config_id_hex})",
                },
            ],
        }
    )

    # 2. Present HF Credential
    leaf_si = getattr(config_obj.high_frequency, "leaf_si_app", "None")
    leaf_cc = getattr(config_obj.high_frequency, "leaf_cc_app", "Leaf Cc")
    custom_hf = getattr(config_obj.high_frequency, "custom_hf_app", "None")

    sections.append(
        {
            "section_id": "hf_credentials",
            "title": "Present the HF credential.",
            "status": "UNTESTED",
            "criteria": [
                {"label": "Leaf Si Application (Kv1)", "value": leaf_si},
                {"label": "Leaf Cc Application (Kc1)", "value": leaf_cc},
                {"label": "Other Custom HF Application", "value": custom_hf},
            ],
        }
    )

    # 3. Verify Card Serial Number (CSN) Credentials
    mfc_csn = getattr(config_obj.csn, "mfc_csn", "Off")
    ev_csn = getattr(config_obj.csn, "ev1_ev2_csn", "Off")
    iclass_csn = getattr(config_obj.csn, "iclass_csn", "Off")
    iso15693 = getattr(config_obj.csn, "iso15693_csn", "Off")
    iso14443a = getattr(config_obj.csn, "iso14443a_csn", "Off")

    sections.append(
        {
            "section_id": "csn_credentials",
            "title": "Verify Card Serial Number (CSN) credentials.",
            "status": "UNTESTED",
            "criteria": [
                {"label": "MFC CSN", "value": mfc_csn},
                {"label": "EV1/EV2 CSN", "value": ev_csn},
                {"label": "iClass CSN", "value": iclass_csn},
                {"label": "ISO 15693 CSN", "value": iso15693},
                {"label": "ISO 14443A", "value": iso14443a},
            ],
        }
    )

    # 4. Verify Low Frequency (LF) Credentials
    fsk = "On" if getattr(config_obj.low_frequency, "fsk_prox", True) else "Off"
    ask = "On" if getattr(config_obj.low_frequency, "ask_prox", True) else "Off"
    prox_filter_en = getattr(config_obj.low_frequency, "prox_filter_enabled", "Off")
    prox_filter_desc = getattr(config_obj.low_frequency, "prox_filter_description", "")
    prox_filter_val = f"{prox_filter_en}" + (f" — {prox_filter_desc}" if prox_filter_desc else "")

    sections.append(
        {
            "section_id": "lf_credentials",
            "title": "Verify Low Frequency (LF) credentials.",
            "status": "UNTESTED",
            "criteria": [
                {"label": "FSK Prox", "value": fsk},
                {"label": "ASK Prox", "value": ask},
                {"label": "Prox Filter", "value": prox_filter_val},
            ],
        }
    )

    # 5. Verify Mobile Capabilities
    mifare2go = getattr(config_obj.mobile, "mifare2go_enabled", "Disabled")
    ble_adv = getattr(config_obj.mobile, "ble_advertising", "Unique (Differs)")
    ble_func = getattr(config_obj.mobile, "ble_functionality", "Admin Only")

    sections.append(
        {
            "section_id": "mobile_credentials",
            "title": "Verify Mobile & Pass credentials.",
            "status": "UNTESTED",
            "criteria": [
                {"label": "BLE Advertising", "value": ble_adv},
                {"label": "BLE Functionality", "value": ble_func},
                {"label": "MiFare2Go Wallet", "value": mifare2go},
            ],
        }
    )

    return sections


@testing_bp.route("/")
@testing_bp.route("/portal")
def portal():
    """Renders the main testing portal overview page.

    Returns:
        str: Rendered HTML template response.
    """
    version_summaries = []
    for ver in SUPPORTED_FIRMWARE_VERSIONS:
        sessions = VERSION_SESSIONS.get(ver, {})
        total_sessions = len(sessions)
        passed_sessions = sum(1 for s in sessions.values() if s["status"] == "PASS")
        failed_sessions = sum(1 for s in sessions.values() if s["status"] == "FAIL")

        version_summaries.append(
            {
                "version": ver,
                "total_cases": total_sessions,
                "passed_cases": passed_sessions,
                "failed_cases": failed_sessions,
            }
        )

    return render_template("testing-portal.html", firmware_versions=version_summaries)


@testing_bp.route("/version/<version>")
def view_version_workspace(version: str):
    """Renders the test workspace for a specific firmware version.

    Args:
        version (str): Target firmware version string.

    Returns:
        str: Rendered HTML template response.
    """
    configs = loader.list_all_configurations()
    sessions = list(VERSION_SESSIONS.get(version, {}).values())

    return render_template(
        "version-workspace.html",
        version=version,
        configs=configs,
        team_members=TEAM_MEMBERS,
        sessions=sessions,
    )


@testing_bp.route("/version/<version>/session/<session_id>")
def view_session_page(version: str, session_id: str):
    """Renders details for a specific test session.

    Args:
        version (str): Target firmware version string.
        session_id (str): Unique test session identifier.

    Returns:
        Response: Rendered template response or 404 page error.
    """
    if version not in VERSION_SESSIONS or session_id not in VERSION_SESSIONS[version]:
        return "Test Session not found", 404

    session = VERSION_SESSIONS[version][session_id]

    # Calculate detailed status counters for the session
    passed_count = sum(1 for c in session["configs"].values() if c["status"] == "PASS")
    failed_count = sum(1 for c in session["configs"].values() if c["status"] == "FAIL")
    pending_count = sum(
        1 for c in session["configs"].values() if c["status"] in ["UNTESTED", "IN_PROGRESS"]
    )

    session_stats = {
        "passed": passed_count,
        "failed": failed_count,
        "pending": pending_count,
        "total": len(session["configs"]),
    }

    return render_template(
        "session-view.html",
        session=session,
        session_stats=session_stats,
        team_members=TEAM_MEMBERS,
    )


@testing_bp.route("/version/<version>/session/<session_id>/run/<filename>")
def run_test_case_page(version: str, session_id: str, filename: str):
    """Renders the execution page for a single configuration test case.

    Args:
        version (str): Target firmware version string.
        session_id (str): Unique test session identifier.
        filename (str): The configuration CSV file name.

    Returns:
        Response: Rendered template response or 404 error page.
    """
    if version not in VERSION_SESSIONS or session_id not in VERSION_SESSIONS[version]:
        return "Test Session not found", 404

    session = VERSION_SESSIONS[version][session_id]
    test_case = session["configs"].get(filename)
    if not test_case:
        return "Configuration test case not in this session", 404

    return render_template(
        "test-run.html",
        test_case=test_case,
        session_id=session_id,
        team_members=TEAM_MEMBERS,
    )


@testing_bp.route("/api/create-session", methods=["POST"])
def create_session():
    """API endpoint to create a new testing session.

    Returns:
        Response: JSON payload indicating success and the new session ID.
    """
    payload = request.get_json() or {}
    version = payload.get("version", "v5.4.11")
    selected_filenames = payload.get("configs", [])
    session_title = payload.get("title", "").strip() or f"{version} Test Session"

    if not selected_filenames:
        return jsonify({"success": False, "error": "Please select at least one configuration."}), 400

    if version not in VERSION_SESSIONS:
        VERSION_SESSIONS[version] = {}

    session_id = f"sess_{int(datetime.now().timestamp())}"
    config_cases = {}

    for filename in selected_filenames:
        config_obj = loader.load_by_filename(filename)
        if config_obj:
            sections = generate_structured_sections(config_obj)
            config_cases[filename] = {
                "filename": filename,
                "config_name": config_obj.config_name,
                "version": version,
                "assigned_to": "Unassigned",
                "status": "UNTESTED",
                "sections": sections,
                "notes": "",
            }

    session_data = {
        "session_id": session_id,
        "title": session_title,
        "version": version,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "status": "IN_PROGRESS",
        "configs": config_cases,
    }

    VERSION_SESSIONS[version][session_id] = session_data

    return jsonify({"success": True, "session_id": session_id})


@testing_bp.route("/api/update-section", methods=["POST"])
def update_section():
    """API endpoint to update the test status of a specific verification section.

    Returns:
        Response: JSON payload indicating success and the updated test case state.
    """
    payload = request.get_json() or {}
    version = payload.get("version")
    session_id = payload.get("session_id")
    filename = payload.get("filename")
    section_id = payload.get("section_id")
    new_status = payload.get("status")

    if version not in VERSION_SESSIONS or session_id not in VERSION_SESSIONS[version]:
        return jsonify({"success": False, "error": "Session not found."}), 404

    session = VERSION_SESSIONS[version][session_id]
    test_case = session["configs"].get(filename)
    if not test_case:
        return jsonify({"success": False, "error": "Test case not found."}), 404

    for sec in test_case["sections"]:
        if sec["section_id"] == section_id:
            sec["status"] = new_status
            break

    # Recalculate config test status
    statuses = [s["status"] for s in test_case["sections"]]
    if "FAIL" in statuses:
        test_case["status"] = "FAIL"
    elif all(s == "PASS" for s in statuses):
        test_case["status"] = "PASS"
    elif "PASS" in statuses:
        test_case["status"] = "IN_PROGRESS"

    # Recalculate session status
    cfg_statuses = [c["status"] for c in session["configs"].values()]
    if "FAIL" in cfg_statuses:
        session["status"] = "FAIL"
    elif all(s == "PASS" for s in cfg_statuses):
        session["status"] = "PASS"
    else:
        session["status"] = "IN_PROGRESS"

    return jsonify({"success": True, "test_case": test_case})


@testing_bp.route("/api/update-assignee", methods=["POST"])
def update_assignee():
    """API endpoint to reassign a configuration test case to a tester.

    Returns:
        Response: JSON payload indicating success.
    """
    payload = request.get_json() or {}
    version = payload.get("version")
    session_id = payload.get("session_id")
    filename = payload.get("filename")
    assigned_to = payload.get("assigned_to", "Unassigned")

    if version in VERSION_SESSIONS and session_id in VERSION_SESSIONS[version]:
        session = VERSION_SESSIONS[version][session_id]
        if filename in session["configs"]:
            session["configs"][filename]["assigned_to"] = assigned_to
            return jsonify({"success": True})

    return jsonify({"success": False, "error": "Not found"}), 404


@testing_bp.route("/api/submit-run", methods=["POST"])
def submit_run():
    """API endpoint to submit completed test run results and alert Slack on failures.

    Returns:
        Response: JSON response with status, Slack notification state, and redirect URL.
    """
    payload = request.get_json() or {}
    version = payload.get("version")
    session_id = payload.get("session_id")
    filename = payload.get("filename")
    assignee = payload.get("assigned_to", "Unassigned")
    note = payload.get("note", "").strip()

    if not assignee or assignee == "Unassigned":
        return jsonify(
            {
                "success": False,
                "error": "A Tester must be selected/assigned before submitting test results.",
            }
        ), 400

    if version not in VERSION_SESSIONS or session_id not in VERSION_SESSIONS[version]:
        return jsonify({"success": False, "error": "Session not found."}), 404

    session = VERSION_SESSIONS[version][session_id]
    test_case = session["configs"].get(filename)
    if not test_case:
        return jsonify({"success": False, "error": "Test case not found."}), 404

    test_case["assigned_to"] = assignee
    test_case["notes"] = note

    failed_sections = [s for s in test_case["sections"] if s["status"] == "FAIL"]

    if failed_sections and not note:
        return jsonify(
            {
                "success": False,
                "error": "A failure note/comment is required when one or more tests fail.",
            }
        ), 400

    slack_sent = False
    if failed_sections:
        failed_tests_data = []
        for sec in failed_sections:
            items_str = ", ".join([f"{item['label']} = {item['value']}" for item in sec["criteria"]])
            failed_tests_data.append({"title": sec["title"], "details": items_str})

        slack_sent = slack_manager.send_test_failure_notification(
            config_name=test_case["config_name"],
            version=version,
            tester_name=assignee,
            failed_tests=failed_tests_data,
            comments=note,
        )

    return jsonify(
        {
            "success": True,
            "slack_sent": slack_sent,
            "redirect_url": f"/testing/version/{version}/session/{session_id}",
        }
    )


@testing_bp.route("/testing/flash-profile", methods=["POST"])
def flash_profile_route():
    """Flashes a profile BIN file over OSDP connection.

    Returns:
        Response: JSON payload containing operation result.
    """
    data = request.json or request.form or {}
    port = data.get("port") or request.form.get("port")
    version = data.get("version") or request.form.get("version", "v5.4.11")
    config_name = data.get("config_name") or request.form.get("config_name")

    if not port:
        return jsonify({"success": False, "error": "No serial port selected."}), 400

    try:
        forge = ForgeClient()
        bin_bytes = None
        filename = f"{config_name}_profile.bin" if config_name else "profile.bin"

        # 1. Check if a CSV file was uploaded in the request
        if "file" in request.files:
            uploaded_file = request.files["file"]
            temp_csv = Path(f"/tmp/{uploaded_file.filename}")
            uploaded_file.save(temp_csv)

            # Compile CSV to Profile BIN via Forge pipeline
            bin_bytes, downloaded_filename = forge.upload_csv_and_generate_bin(
                csv_file_path=temp_csv, target_version=version
            )
            filename = downloaded_filename or filename
            temp_csv.unlink(missing_ok=True)

        # 2. Otherwise fetch the latest matching compiled binary from GCS
        elif config_name:
            bin_bytes, downloaded_filename = forge.fetch_bin_from_gcs(
                config_name=config_name, version=version, is_firmware=False
            )
            if downloaded_filename:
                filename = downloaded_filename

        if not bin_bytes:
            return jsonify(
                {
                    "success": False,
                    "error": (
                        "Failed to retrieve or compile Profile BIN for"
                        f" '{config_name or 'uploaded file'}'."
                    ),
                }
            ), 400

        # 3. Flash Profile BIN over OSDP (handles 9600 -> 115200 -> 9600 baud rate switching)
        flasher = OsdpFlasher()
        result = flasher.flash_profile(bin_bytes=bin_bytes, filename=filename, port=port)
        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": f"Profile Flash Error: {str(e)}"}), 500


@testing_bp.route("/testing/flash-firmware", methods=["POST"])
def flash_firmware_route():
    """Flashes a firmware DCK file over OSDP connection.

    Returns:
        Response: JSON payload containing operation result.
    """
    data = request.json or request.form or {}
    port = data.get("port") or request.form.get("port")
    version = data.get("version") or request.form.get("version", "v5.4.11")
    config_name = data.get("config_name") or request.form.get("config_name")

    if not port:
        return jsonify({"success": False, "error": "No serial port selected."}), 400

    try:
        forge = ForgeClient()
        dck_bytes = None
        filename = f"{config_name}_firmware.dck" if config_name else "firmware.dck"

        # 1. Check if a CSV file was uploaded in the request
        if "file" in request.files:
            uploaded_file = request.files["file"]
            temp_csv = Path(f"/tmp/{uploaded_file.filename}")
            uploaded_file.save(temp_csv)

            # Compile CSV to Firmware DCK via Forge pipeline
            dck_bytes, downloaded_filename = forge.upload_csv_and_generate_firmware(
                csv_file_path=temp_csv, target_version=version
            )
            filename = downloaded_filename or filename
            temp_csv.unlink(missing_ok=True)

        # 2. Otherwise fetch the latest matching compiled firmware DCK from GCS
        elif config_name:
            dck_bytes, downloaded_filename = forge.fetch_bin_from_gcs(
                config_name=config_name, version=version, is_firmware=True
            )
            if downloaded_filename:
                filename = downloaded_filename

        if not dck_bytes:
            return jsonify(
                {
                    "success": False,
                    "error": (
                        "Failed to retrieve or compile Firmware DCK for"
                        f" '{config_name or 'uploaded file'}'."
                    ),
                }
            ), 400

        # 3. Flash Firmware DCK over OSDP (handles 9600 -> 115200 -> 9600 baud rate switching)
        flasher = OsdpFlasher()
        result = flasher.flash_firmware(dck_bytes=dck_bytes, filename=filename, port=port)
        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": f"Firmware Flash Error: {str(e)}"}), 500