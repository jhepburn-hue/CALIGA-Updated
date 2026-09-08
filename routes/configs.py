import csv
import getpass
import io
import json
import os
import re
from pathlib import Path
import threading
import time
from flask import Response
from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from core.translators.csv_loader import CSVConfigLoader
from core.translators.revision_manager import RevisionManager
from services.forge_client import ForgeClient
from services.osdp_flasher import OsdpFlasher
from services.pocketbase_client import PocketBaseClient
from services.relay_client import RelayClient
from services.slack_client import SlackNotificationManager
from osdp_library.utils.port_inspector import PortInspector

configs_bp = Blueprint("configs", __name__, url_prefix="/configs")
testing_bp = Blueprint("testing", __name__)
loader = CSVConfigLoader()
revision_manager = RevisionManager()
slack_manager = SlackNotificationManager()

CONFIGS_DIR = Path(__file__).parent.parent / "configs"
MAPPINGS_FILE = Path(__file__).parent.parent / "group_mappings.json"

DROPDOWN_OPTIONS = {
    "yes_no": ["No", "Yes"],
    "on_off": ["Off", "On"],
    "enabled_disabled": ["Enabled", "Disabled"],
    "led_colors": [
        "Off",
        "Red",
        "Green",
        "Amber",
        "Blue",
        "Cyan",
        "Magenta",
        "White",
    ],
    "keypad_formats": [
        "8-bit",
        "4-bit",
        "buffered 26-bit",
        "Magstripe - 4 digit",
        "Magstripe - 5 digit",
    ],
    "casi_formats": ["CASI-4001", "CASI-4002"],
    "supervision_states": ["2-State", "4-State", "Unsupervised"],
    "leaf_si_apps": ["None", "Leaf Si"],
    "other_hf_apps": ["None", "Custom EV1", "Custom MFC"],
    "ble_advertising": [
        "WaveLynx (ETHS)",
        "AMAG (AMAG)",
        "Brivo (BRVO)",
        "Fidelity (FDTY)",
        "Long Range (ETLR)",
        "Unique (Differs)",
    ],
    "ble_functionality": ["Admin + Credentials", "Admin Only", "Disabled"],
    "mobile_keysets": ["WaveLynx Transport", "AMAG Transport", "Custom"],
    "meridian_bit_counts": [
        "Standard Ethos",
        "32 bit",
        "32 bit, reverse byte (RP40)",
        "56 bit, reverse byte (Seos)",
        "56 bit for ISO15693/iCLASS",
        "40",
        "57",
        "128",
    ],
    "csn_formats": [
        "Off",
        "On",
        "Standard",
        "CSN_4001",
        "CSN_4002",
        "CSN_5002",
        "CSN_6400",
        "CSN_26_BIT",
        "CSN_32_BIT_LSB_XOR",
        "CSN_32_BIT_MSB_XOR",
        "CSN_40_BIT_MSB_LRC",
        "CSN_34_BIT_MSB_PARITY",
        "CSN_32_BIT_LSB",
        "CSN_32_BIT_MSB",
        "CSN_32_BIT_PLUS",
        "CSN_56_BIT",
        "CSN_40_BIT_PCSC",
        "CSN_75_BIT_PCSC",
        "CSN_5002_CL2",
        "CSN_37_BIT",
        "CSN_56_BIT_MSB",
    ],
}


def get_active_user() -> str:
    """Retrieves the active username from the environment or system user settings.

    Returns:
        str: The capitalized username or a fallback message if it cannot be determined.
    """
    env_user = os.getenv("CALIGA_USER_NAME")
    if env_user:
        return env_user
    try:
        user = getpass.getuser()
        if user:
            return user.capitalize() if len(user) <= 3 else user
    except Exception:
        pass
    return "Could Not Determine User"


@configs_bp.route("/")
def list_configs():
    """Renders the view listing all existing configurations.

    Returns:
        str: Rendered HTML page with the list of configurations.
    """
    all_configs = loader.list_all_configurations()
    return render_template("configs-list.html", configs=all_configs)


@configs_bp.route("/view/<filename>", methods=["GET", "POST"])
def view_config(filename: str):
    """Renders or updates a specific configuration by file name.

    Args:
        filename (str): The CSV file name of the configuration to view/edit.

    Returns:
        Response: Rendered template or redirect response.
    """
    config = loader.load_by_filename(filename)
    if not config:
        return "Configuration not found", 404

    active_user = get_active_user()

    if request.method == "POST":
        if config.status.value != "POC":
            flash("Locked: Only POC configurations can be modified.", "error")
            return redirect(url_for("configs.view_config", filename=filename))

        # Field Mapping for form comparison and CSV row updating
        field_mapping = {
            "wiegand_2ws": ("-2WS", "Yes" if config.hardware.wiegand_2ws else "No"),
            "wiegand_3ws": ("-3WS", "Yes" if config.hardware.wiegand_3ws else "No"),
            "wiegand_6ws": ("-6WS", "Yes" if config.hardware.wiegand_6ws else "No"),
            "wiegand_7ws": ("-7WS", "Yes" if config.hardware.wiegand_7ws else "No"),
            "f2f_7fm": ("F2F", "Yes" if config.hardware.f2f_7fm else "No"),
            "mclp_7fm": ("MCLP", "Yes" if config.hardware.mclp_7fm else "No"),
            "keyset_id": ("Keyset ID", str(config.keyset_id)),
            "idle_led_color": ("Idle LED", config.audio_visual.idle_led_color),
            "credential_led_color": (
                "Credential Report LED",
                config.audio_visual.credential_led_color,
            ),
            "beeper_enabled": (
                "Beeper",
                "On" if config.audio_visual.beeper_enabled else "Off",
            ),
            "keypad_format": ("Keypad Format", config.audio_visual.keypad_format),
            "tamper_monitoring": (
                "Tamper Monitoring",
                "On" if config.audio_visual.tamper_monitoring else "Off",
            ),
            "leaf_si_app": (
                "Leaf Si Application",
                config.high_frequency.leaf_si_app,
            ),
            "leaf_cc_app": (
                "Leaf Cc Application",
                config.high_frequency.leaf_cc_app,
            ),
            "custom_hf_app": (
                "Other Custom HF Application",
                config.high_frequency.custom_hf_app,
            ),
            "mfc_csn": ("MFC CSN", config.csn.mfc_csn),
            "ev1_ev2_csn": ("EV1/EV2 CSN", config.csn.ev1_ev2_csn),
            "iclass_csn": ("iClass CSN", config.csn.iclass_csn),
            "iso15693_csn": ("ISO15693 CSN", config.csn.iso15693_csn),
            "iso14443a_csn": ("ISO14443A CSN", config.csn.iso14443a_csn),
            "fsk_prox": (
                "FSK Prox",
                "On" if config.low_frequency.fsk_prox else "Off",
            ),
            "ask_prox": (
                "ASK Prox",
                "On" if config.low_frequency.ask_prox else "Off",
            ),
            "prox_filter_enabled": (
                "Prox Filter",
                "On" if config.low_frequency.prox_filter_enabled else "Off",
            ),
            "ble_advertising": (
                "BLE Advertising Config",
                config.mobile.ble_advertising,
            ),
            "ble_functionality": (
                "BLE Functionality",
                config.mobile.ble_functionality,
            ),
            "nfc_enabled": ("NFC Functionality", config.mobile.nfc_enabled),
            "mobile_keyset": ("Mobile Keyset", config.mobile.mobile_keyset),
            "legacy_credentials": (
                "Legacy Credentials",
                config.mobile.legacy_credentials,
            ),
            "transport_mode": ("Transport Mode", config.mobile.transport_mode),
            "ecp_desfire_enabled": (
                "ECP DESFire",
                config.mobile.ecp_desfire_enabled,
            ),
            "ecp_tci": ("ECP TCI", config.mobile.ecp_tci),
            "apple_meridian_bit_count": (
                "Apple Meridian Bit Count",
                config.mobile.apple_meridian_bit_count,
            ),
            "mifare2go_enabled": ("MiFare2Go", config.mobile.mifare2go_enabled),
            "mifare2go_dfname": ("MiFare2Go DFNAME", config.mobile.mifare2go_dfname),
        }

        changes = []
        updates_dict = {}

        # Compare form input against loaded config
        for form_key, (csv_label, current_val) in field_mapping.items():
            if form_key in request.form:
                new_val = request.form.get(form_key, "").strip()
                if new_val and new_val.lower() != current_val.lower():
                    changes.append(f"• {csv_label}: {current_val} → {new_val}")
                    updates_dict[csv_label.lower()] = new_val

        # Update CSV file on disk
        file_path = CONFIGS_DIR / filename
        if updates_dict and file_path.is_file():
            try:
                rows = []
                with open(file_path, mode="r", encoding="utf-8", errors="ignore") as f:
                    reader = csv.reader(f)
                    for row in reader:
                        new_row = list(row)
                        if new_row:
                            first_cell = new_row[0].strip().lower()
                            for label_lower, val_to_set in updates_dict.items():
                                if label_lower in first_cell:
                                    if len(new_row) >= 3:
                                        new_row[2] = val_to_set
                                    elif len(new_row) == 2:
                                        new_row[1] = val_to_set
                                    break
                        rows.append(new_row)

                with open(file_path, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerows(rows)
            except Exception as e:
                print(f"Error updating CSV file: {e}")

        # Log to Revision History and notify Slack
        if changes:
            summary_text = "\n".join(changes)
            revision_manager.add_revision(
                filename, summary=summary_text, updated_by=active_user
            )
            slack_manager.send_batch_update_notification(
                config_name=config.config_name,
                changes=changes,
                updated_by=active_user,
            )
            flash(
                "Profile changes saved, revision logged, and Slack alert sent!",
                "success",
            )
        else:
            flash("No settings were changed.", "info")

        return redirect(url_for("configs.view_config", filename=filename))

    revisions = revision_manager.get_history(filename)
    return render_template(
        "view-config.html",
        config=config,
        dropdowns=DROPDOWN_OPTIONS,
        revisions=revisions,
    )


@configs_bp.route("/api/status", methods=["POST"])
def update_status():
    """API endpoint to update the status of a configuration file.

    Returns:
        Response: JSON payload indicating operation success and updated fields.
    """
    payload = request.get_json() or {}
    filename = payload.get("filename")
    new_status = payload.get("status")

    if not filename or not new_status or new_status not in ["Active", "POC", "Archived"]:
        return jsonify({"success": False, "error": "Invalid payload"}), 400

    file_path = CONFIGS_DIR / filename
    if not file_path.is_file():
        return jsonify({"success": False, "error": "File not found"}), 404

    try:
        rows = []
        status_updated = False
        old_status = "Active"

        with open(file_path, mode="r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            for row in reader:
                new_row = list(row)
                for idx, cell in enumerate(new_row):
                    if cell.strip().lower() == "status":
                        if idx + 1 < len(new_row):
                            old_status = new_row[idx + 1].strip()
                            new_row[idx + 1] = new_status
                        else:
                            new_row.append(new_status)
                        status_updated = True
                        break
                rows.append(new_row)

        if not status_updated:
            rows.append(["Status", new_status])

        with open(file_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(rows)

        # Get active user dynamically
        active_user = get_active_user()

        # Log Revision History
        revision_manager.add_revision(
            filename,
            summary=f"Status changed from {old_status} to {new_status}.",
            updated_by=active_user,
        )

        # Send Slack Alert
        slack_manager.send_status_change_notification(
            config_name=Path(filename).stem,
            old_status=old_status,
            new_status=new_status,
            updated_by=active_user,
        )

        return jsonify(
            {
                "success": True,
                "filename": filename,
                "old_status": old_status,
                "new_status": new_status,
                "updated_by": active_user,
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@configs_bp.route("/api/batch-save", methods=["POST"])
def batch_save():
    """API endpoint to receive batched field edits flushed via UI timers.

    Updates disk CSV, adds 1 revision entry, and sends 1 Slack summary alert.

    Returns:
        Response: JSON payload indicating the status and saved modification count.
    """
    payload = request.get_json(silent=True) or {}
    filename = payload.get("filename")
    incoming_changes = payload.get("changes", {})

    if not filename or not incoming_changes:
        return jsonify({"success": True, "message": "No changes to save"}), 200

    config = loader.load_by_filename(filename)
    if not config or config.status.value != "POC":
        return jsonify(
            {"success": False, "error": "Configuration is locked or invalid"}
        ), 400

    active_user = get_active_user()

    # Map form keys to friendly display labels
    labels_map = {
        "wiegand_2ws": "-2WS",
        "wiegand_3ws": "-3WS",
        "wiegand_6ws": "-6WS",
        "wiegand_7ws": "-7WS",
        "f2f_7fm": "F2F",
        "mclp_7fm": "MCLP",
        "keyset_id": "Keyset ID",
        "idle_led_color": "Idle LED",
        "credential_led_color": "Credential Report LED",
        "beeper_enabled": "Beeper",
        "keypad_format": "Keypad Format",
        "tamper_monitoring": "Tamper Monitoring",
        "leaf_si_app": "Leaf Si Application",
        "leaf_cc_app": "Leaf Cc Application",
        "custom_hf_app": "Other Custom HF Application",
        "mfc_csn": "MFC CSN",
        "ev1_ev2_csn": "EV1/EV2 CSN",
        "iclass_csn": "iClass CSN",
        "iso15693_csn": "ISO15693 CSN",
        "iso14443a_csn": "ISO14443A CSN",
        "fsk_prox": "FSK Prox",
        "ask_prox": "ASK Prox",
        "prox_filter_enabled": "Prox Filter",
        "ble_advertising": "BLE Advertising Config",
        "ble_functionality": "BLE Functionality",
        "nfc_enabled": "NFC Functionality",
        "mobile_keyset": "Mobile Keyset",
        "legacy_credentials": "Legacy Credentials",
        "transport_mode": "Transport Mode",
        "ecp_desfire_enabled": "ECP DESFire",
        "ecp_tci": "ECP TCI",
        "apple_meridian_bit_count": "Apple Meridian Bit Count",
        "mifare2go_enabled": "MiFare2Go",
        "mifare2go_dfname": "MiFare2Go DFNAME",
    }

    diff_summary = []
    updates_dict = {}

    for key, new_val in incoming_changes.items():
        csv_label = labels_map.get(key, key)
        diff_summary.append(f"• {csv_label}: set to {new_val}")
        updates_dict[csv_label.lower()] = new_val

    # Update CSV File on disk
    file_path = CONFIGS_DIR / filename
    if updates_dict and file_path.is_file():
        try:
            rows = []
            with open(file_path, mode="r", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                for row in reader:
                    new_row = list(row)
                    if new_row:
                        first_cell = new_row[0].strip().lower()
                        for label_lower, val_to_set in updates_dict.items():
                            if label_lower in first_cell:
                                if len(new_row) >= 3:
                                    new_row[2] = val_to_set
                                elif len(new_row) == 2:
                                    new_row[1] = val_to_set
                                break
                    rows.append(new_row)

            with open(file_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(rows)
        except Exception as e:
            print(f"Error updating CSV file: {e}")

    # Log 1 Revision Entry & Send 1 Slack Alert
    if diff_summary:
        summary_text = "\n".join(diff_summary)
        revision_manager.add_revision(
            filename, summary=summary_text, updated_by=active_user
        )
        slack_manager.send_batch_update_notification(
            config_name=config.config_name,
            changes=diff_summary,
            updated_by=active_user,
        )

    return jsonify({"success": True, "saved_count": len(diff_summary)})


def get_next_available_ids() -> tuple[int, str]:
    """Scans existing configurations to calculate the next incremental decimal and hex IDs.

    Returns:
        tuple[int, str]: The next decimal ID integer and formatted hexadecimal ID string.
    """
    all_configs = loader.list_all_configurations()
    max_dec_id = 0
    for cfg in all_configs:
        if cfg.config_id_dec > max_dec_id:
            max_dec_id = cfg.config_id_dec

    next_dec = max_dec_id + 1
    next_hex = f"0x{next_dec:04X}"
    return next_dec, next_hex


@configs_bp.route("/new", methods=["GET", "POST"])
def create_config():
    """Handles the creation of a new configuration profile.

    Returns:
        Response: Rendered HTML template or redirect response.
    """
    active_user = get_active_user()

    if request.method == "POST":
        config_name = request.form.get("config_name", "").strip().upper()
        dec_id_raw = request.form.get("config_id_dec", "").strip()

        if not config_name:
            flash("Configuration Name is required.", "error")
            return redirect(url_for("configs.create_config"))

        try:
            dec_id = int(dec_id_raw)
            hex_id = f"0x{dec_id:04X}"
        except (ValueError, TypeError):
            next_dec, _ = get_next_available_ids()
            dec_id = next_dec
            hex_id = f"0x{dec_id:04X}"

        filename = f"{config_name}.csv"
        file_path = CONFIGS_DIR / filename

        if file_path.exists():
            flash(f"Configuration '{filename}' already exists!", "error")
            return redirect(url_for("configs.create_config"))

        # Write CSV matching the exact column layout expected by CSVConfigLoader
        csv_rows = [
            ["End User Configuration Form", "", "", "", "", "", ""],
            ["Card Details", "Config Name", config_name, "", "Card Type", "", ""],
            ["", "Config ID", dec_id, "", "Bitstream", "", ""],
            ["STEP 1: Hardware", "", "", "", "", "", ""],
            ["Facility Code", "", "", "", "", "", ""],
            ["Wiegand/OSDP", "ET10", "ET20", "ET25", "", "Starting Badge", ""],
            ["-2WS", request.form.get("wiegand_2ws", "No"), "", "", "", "Notes", ""],
            ["-3WS", request.form.get("wiegand_3ws", "No"), "", "", "", "", ""],
            ["-6WS", request.form.get("wiegand_6ws", "No"), "", "", "", "", ""],
            ["-7WS", request.form.get("wiegand_7ws", "No"), "", "", "", "", ""],
            ["F2F", "ET10", "ET20", "ET25", "", "Part Numbers", ""],
            ["-7FM", request.form.get("f2f_7fm", "No"), "", "", "", "", ""],
            ["MCLP", "ET10", "ET20", "ET25", "", "", ""],
            [
                "-7FM",
                request.form.get("mclp_7fm", "No"),
                "",
                "",
                "",
                "Notes/Other Products",
                "",
            ],
            ["STEP 2: Custom Keyset", "", "", "", "", "", ""],
            ["Custom Keyset (LEAF Cc)", "", "Enabled", "", "", "", ""],
            [
                "Keyset ID (LkXXXXX)",
                "",
                request.form.get("keyset_id", "None"),
                "",
                "",
                "",
                "",
            ],
            ["LEAF Customer Code (Decimal)", "", "", "", "", "", ""],
            ["STEP 3: AV + Output Formats", "", "", "", "", "", ""],
            ["Wiegand/OSDP", "", "", "", "", "", ""],
            [
                "Idle LED",
                "",
                request.form.get("idle_led_color", "Red"),
                "",
                "",
                "",
                "",
            ],
            [
                "Credential Report LED",
                "",
                request.form.get("credential_led_color", "Green"),
                "",
                "",
                "",
                "",
            ],
            ["Beeper", "", request.form.get("beeper_enabled", "On"), "", "", "", ""],
            [
                "Keypad Format",
                "",
                request.form.get("keypad_format", "8-bit"),
                "",
                "",
                "",
                "",
            ],
            [
                "Tamper Monitoring",
                "",
                request.form.get("tamper_monitoring", "On"),
                "",
                "",
                "",
                "",
            ],
            ["STEP 4: High Frequency (HF)", "", "", "", "", "", ""],
            [
                "Leaf Si Application (Kv1)",
                "",
                request.form.get("leaf_si_app", "None"),
                "",
                "",
                "",
                "",
            ],
            [
                "Leaf Cc Application (Kc1)",
                "",
                request.form.get("leaf_cc_app", "Leaf Cc"),
                "",
                "",
                "",
                "",
            ],
            [
                "Other Custom HF Application",
                "",
                request.form.get("custom_hf_app", "None"),
                "",
                "",
                "",
                "",
            ],
            ["Custom Application Notes", "", "", "", "", "", ""],
            ["STEP 5: Card Serial Number (CSN)", "", "", "", "", "", ""],
            ["MFC CSN", "", request.form.get("mfc_csn", "Off"), "", "", "", ""],
            ["EV1/EV2 CSN", "", request.form.get("ev1_ev2_csn", "Off"), "", "", "", ""],
            ["iClass CSN", "", request.form.get("iclass_csn", "Off"), "", "", "", ""],
            ["ISO15693 CSN", "", request.form.get("iso15693_csn", "Off"), "", "", "", ""],
            [
                "ISO14443A CSN",
                "",
                request.form.get("iso14443a_csn", "Off"),
                "",
                "",
                "",
                "",
            ],
            ["STEP 6: Low Frequency (LF)", "", "", "", "", "", ""],
            ["FSK Prox", "", request.form.get("fsk_prox", "On"), "", "", "", ""],
            ["ASK Prox", "", request.form.get("ask_prox", "On"), "", "", "", ""],
            [
                "Prox Filter",
                "",
                request.form.get("prox_filter_enabled", "Off"),
                "",
                "",
                "",
                "",
            ],
            ["Prox Filter Description", "", "", "", "", "", ""],
            ["STEP 7: Mobile", "", "", "", "", "", ""],
            [
                "BLE Advertising Config",
                "",
                request.form.get("ble_advertising", "Unique (Differs)"),
                "",
                "",
                "",
                "",
            ],
            [
                "BLE Functionality",
                "",
                request.form.get("ble_functionality", "Admin Only"),
                "",
                "",
                "",
                "",
            ],
            [
                "NFC Functionality",
                "",
                request.form.get("nfc_enabled", "Enabled"),
                "",
                "",
                "",
                "",
            ],
            [
                "Mobile Keyset",
                "",
                request.form.get("mobile_keyset", "Custom"),
                "",
                "",
                "",
                "",
            ],
            [
                "Legacy Credentials (Sym Blue, Brivo)",
                "",
                request.form.get("legacy_credentials", "Off"),
                "",
                "",
                "",
                "",
            ],
            [
                "Transport Mode",
                "",
                request.form.get("transport_mode", "Off"),
                "",
                "",
                "",
                "",
            ],
            [
                "ECP DESFire",
                "",
                request.form.get("ecp_desfire_enabled", "Disabled"),
                "",
                "",
                "",
                "",
            ],
            ["ECP TCI", "", request.form.get("ecp_tci", ""), "", "", "", ""],
            [
                "Apple Meridian Bit Count",
                "",
                request.form.get("apple_meridian_bit_count", "40"),
                "",
                "",
                "",
                "",
            ],
            [
                "MiFare2Go",
                "",
                request.form.get("mifare2go_enabled", "Disabled"),
                "",
                "",
                "",
                "",
            ],
            [
                "MiFare2Go DFNAME",
                "",
                request.form.get("mifare2go_dfname", ""),
                "",
                "",
                "",
                "",
            ],
            ["Mobile Notes", "", "", "", "", "", ""],
            ["STEP 8: Part Numbers", "", "", "", "", "", ""],
            ["Assigned Part Numbers", "", f"ETxx-xWS-{config_name}", "", "", "", ""],
            ["Status", "POC"],
        ]

        try:
            with open(file_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(csv_rows)

            # 1. Log Initial Revision
            revision_manager.add_revision(
                filename,
                summary="Configuration created in POC status.",
                updated_by=active_user,
            )

            # 2. Send New Config Slack Alert
            slack_manager.send_new_config_notification(
                config_name=config_name,
                dec_id=dec_id,
                hex_id=hex_id,
                updated_by=active_user,
            )

            flash(
                f"Configuration '{config_name}' (ID: {dec_id}) created successfully!",
                "success",
            )
            return redirect(url_for("configs.list_configs"))

        except Exception as e:
            flash(f"Error creating configuration file: {e}", "error")
            return redirect(url_for("configs.create_config"))

    next_dec, next_hex = get_next_available_ids()
    return render_template(
        "new-config.html",
        dropdowns=DROPDOWN_OPTIONS,
        next_dec=next_dec,
        next_hex=next_hex,
    )


@configs_bp.route("/view/<filename>/generate/ini", methods=["POST"])
def generate_ini(filename: str):
    """Triggers INI file compilation via ForgeClient and returns the content.

    Args:
        filename (str): The configuration CSV file name.

    Returns:
        Response: JSON payload containing INI string or error message.
    """
    try:
        csv_path = CONFIGS_DIR / filename
        target_version = request.form.get("target_version", "v5.4.11")
        config_obj = loader.load_by_filename(filename)

        forge_client = ForgeClient()
        ini_content = forge_client.upload_csv_and_generate_ini(
            csv_path, target_version, config_obj=config_obj
        )

        return jsonify(
            {
                "success": True,
                "filename": f"{csv_path.stem}.ini",
                "content": ini_content,
            }
        )

    except Exception as e:
        print(f"[Generate INI Error] {e}")
        return jsonify({"success": False, "error": str(e)}), 400


@configs_bp.route("/view/<filename>/generate/bin", methods=["POST"])
def generate_profile_bin(filename: str):
    """Triggers Profile BIN compilation via ForgeClient and returns the file download.

    Args:
        filename (str): The configuration CSV file name.

    Returns:
        Response: File download response containing the compiled binary asset.
    """
    try:
        csv_path = CONFIGS_DIR / filename
        target_version = request.form.get("target_version", "v5.4.11")
        config_obj = loader.load_by_filename(filename)

        forge_client = ForgeClient()
        bin_bytes, download_filename = forge_client.upload_csv_and_generate_bin(
            csv_path, target_version, config_obj=config_obj
        )

        return send_file(
            io.BytesIO(bin_bytes),
            mimetype="application/octet-stream",
            as_attachment=True,
            download_name=download_filename,
        )

    except Exception as e:
        print(f"[Generate Profile BIN Error] {e}")
        return jsonify({"success": False, "error": str(e)}), 400


@configs_bp.route("/view/<filename>/generate/firmware", methods=["POST"])
def generate_firmware_dck(filename: str):
    """Triggers Firmware DCK compilation via ForgeClient and returns the file download.

    Args:
        filename (str): The configuration CSV file name.

    Returns:
        Response: File download response containing the compiled firmware DCK file.
    """
    try:
        csv_path = CONFIGS_DIR / filename
        target_version = request.form.get("target_version", "v5.4.11")
        config_obj = loader.load_by_filename(filename)

        forge_client = ForgeClient()
        dck_bytes, download_filename = (
            forge_client.upload_csv_and_generate_firmware(
                csv_path, target_version, config_obj=config_obj
            )
        )

        return send_file(
            io.BytesIO(dck_bytes),
            mimetype="application/octet-stream",
            as_attachment=True,
            download_name=download_filename,
        )

    except Exception as e:
        print(f"[Generate Firmware DCK Error] {e}")
        return jsonify({"success": False, "error": str(e)}), 400


@configs_bp.route("/view/<filename>/generate/tokens", methods=["POST"])
def generate_tokens(filename: str):
    """Generates active PocketBase token records for profile and firmware assets.

    Args:
        filename (str): The configuration CSV file name.

    Returns:
        Response: JSON response containing token generation results.
    """
    try:
        csv_path = CONFIGS_DIR / filename
        target_version = request.form.get("target_version", "v5.4.11")
        config_obj = loader.load_by_filename(filename)

        forge_client = ForgeClient()
        token_results = forge_client.generate_tokens_flow(
            csv_path, target_version, config_obj=config_obj
        )

        return jsonify({"success": True, "data": token_results})

    except Exception as e:
        print(f"[Generate Tokens Error] {e}")
        return jsonify({"success": False, "error": str(e)}), 400


def get_group_id_from_mapping(
    lk_number: str, environment: str = "staging"
) -> int | None:
    """Looks up the relay group ID for a given reader key from group mappings.

    Args:
        lk_number (str): The reader keyset ID (e.g., 'Lk10010').
        environment (str, optional): Target environment ('staging' or 'prod'). Defaults to "staging".

    Returns:
        int | None: The mapped group ID integer if found, otherwise None.
    """
    if not MAPPINGS_FILE.exists():
        return None

    with open(MAPPINGS_FILE, "r") as f:
        mappings = json.load(f)

    env_key = "prod" if environment.lower() in ("prod", "production") else "staging"
    env_map = mappings.get(env_key, {})

    # Check exact match or title case
    for key, gid in env_map.items():
        if key.lower() == lk_number.lower():
            return gid

    return None


@configs_bp.route("/view/<filename>/generate/wallet-pass", methods=["POST"])
def generate_wallet_pass(filename: str):
    """Generates a Relay wallet web link pass for the configuration.

    Args:
        filename (str): The configuration CSV file name.

    Returns:
        Response: JSON payload with wallet provisioning URL or error message.
    """
    try:
        config_obj = loader.load_by_filename(filename)
        if not config_obj:
            return jsonify({"success": False, "error": "Configuration not found"}), 404

        env_type = request.form.get("environment", "staging").lower()
        lk_number = str(config_obj.keyset_id).strip()  # e.g. 'Lk10010'

        # Look up group_id in mapping file based on environmental plane
        group_id = get_group_id_from_mapping(lk_number, env_type)

        if not group_id:
            return jsonify(
                {
                    "success": False,
                    "error": (
                        f"Reader ID '{lk_number}' is not mapped to a group_id in"
                        f" {env_type.upper()}."
                    ),
                }
            ), 400

        relay = RelayClient(is_staging=(env_type == "staging"))
        result = relay.create_corporate_weblink(
            group_id=int(group_id),
            cardholder_data={
                "first_name": config_obj.config_name,
                "last_name": f"({lk_number})",
            },
        )

        if result.get("success"):
            return jsonify(
                {
                    "success": True,
                    "environment": env_type,
                    "keyset_id": lk_number,
                    "wallet_url": result.get("provisioning_link"),
                }
            )
        else:
            return jsonify({"success": False, "error": result.get("error")}), 400

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@configs_bp.route('/scan_ports', methods=['GET'])
def scan_ports():
    """Scans system for connected serial ports and returns them as a list of strings."""
    try:
        inspector = PortInspector()
        ports = inspector.find_and_get_ports()
        return jsonify({'success': True, 'ports': ports})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'ports': []}), 500


@testing_bp.route("/testing/flash-profile", methods=["POST"])
def flash_profile_route():
    """Flashes a profile BIN file over OSDP serial connection.

    Returns:
        Response: JSON result of the flashing transaction.
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
        result = flasher.flash_profile(
            bin_bytes=bin_bytes, filename=filename, port=port
        )
        return jsonify(result)

    except Exception as e:
        return jsonify(
            {"success": False, "error": f"Profile Flash Error: {str(e)}"}
        ), 500


@testing_bp.route("/testing/flash-firmware", methods=["POST"])
def flash_firmware_route():
    """Flashes a firmware DCK file over OSDP serial connection.

    Returns:
        Response: JSON result of the flashing transaction.
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
            dck_bytes, downloaded_filename = (
                forge.upload_csv_and_generate_firmware(
                    csv_file_path=temp_csv, target_version=version
                )
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
        result = flasher.flash_firmware(
            dck_bytes=dck_bytes, filename=filename, port=port
        )
        return jsonify(result)

    except Exception as e:
        return jsonify(
            {"success": False, "error": f"Firmware Flash Error: {str(e)}"}
        ), 500

@configs_bp.route("/view/<filename>/flash-osdp", methods=["POST"])
def flash_osdp_stream(filename: str):
    """Server-Sent Events (SSE) streaming endpoint for compiling a binary artifact
    and flashing it directly to a physical reader over an OSDP serial port.

    Args:
        filename (str): Target configuration CSV filename.

    Returns:
        Response: SSE Event Stream Response displaying real-time progress.
    """
    port = request.form.get("port")
    build_type = request.form.get("build_type", "profile")
    target_version = request.form.get("target_version", "v5.4.11")

    is_firmware = (build_type == "firmware")
    config_name = filename.rsplit(".", 1)[0]
    csv_path = CONFIGS_DIR / filename

    def generate_events():
        def send_status(msg, percent, error=False):
            data = json.dumps({"status": msg, "percent": percent, "error": error})
            return f"data: {data}\n\n"

        if not port:
            yield send_status("Error: No OSDP serial port selected.", 0, error=True)
            return

        if not csv_path.exists():
            yield send_status(f"Error: CSV file '{filename}' not found.", 0, error=True)
            return

        yield send_status("Fetching compiled binary from Forge/GCS...", 10)
        
        try:
            forge = ForgeClient()
            config_obj = loader.load_by_filename(filename)

            if is_firmware:
                bin_bytes, downloaded_filename = forge.upload_csv_and_generate_firmware(
                    csv_file_path=csv_path, target_version=target_version, config_obj=config_obj
                )
            else:
                bin_bytes, downloaded_filename = forge.upload_csv_and_generate_bin(
                    csv_file_path=csv_path, target_version=target_version, config_obj=config_obj
                )
        except Exception as e:
            yield send_status(f"Forge Build Exception: {str(e)}", 0, error=True)
            return

        if not bin_bytes:
            yield send_status("Failed to retrieve compiled binary asset.", 0, error=True)
            return

        downloaded_filename = downloaded_filename or (
            f"{config_name}.dck" if is_firmware else f"{config_name}.bin"
        )
        yield send_status(f"Binary ready: {downloaded_filename}", 30)

        temp_dir = Path("/tmp/generated")
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_bin_path = temp_dir / downloaded_filename

        try:
            temp_bin_path.write_bytes(bin_bytes)
        except Exception as e:
            yield send_status(f"Failed to save temporary binary: {str(e)}", 0, error=True)
            return

        try:
            yield send_status(f"Connecting to OSDP reader on {port}...", 35)
            flasher = OsdpFlasher(port=port)
            flasher.connect()

            progress_events = []

            def _progress_callback(pct):
                # Scale OSDP transfer percentage to 35% -> 100% on progress bar
                scaled_pct = 35 + int((pct / 100.0) * 65)
                progress_events.append(scaled_pct)

            flash_success = False
            flash_error_msg = None
            ft_type_code = 1 if is_firmware else 2

            # Execute flashing in background thread so loop can yield SSE events
            def _flash_thread_worker():
                nonlocal flash_success, flash_error_msg
                try:
                    flash_success = flasher.flash_binary_file(
                        file_path=temp_bin_path,
                        progress_callback=_progress_callback,
                        ft_type=ft_type_code
                    )
                except Exception as ex:
                    flash_error_msg = str(ex)

            flash_thread = threading.Thread(target=_flash_thread_worker)
            flash_thread.start()

            # Stream progress percentage updates while thread runs
            while flash_thread.is_alive() or progress_events:
                while progress_events:
                    latest_pct = progress_events.pop(0)
                    yield send_status("Transferring binary data to reader...", latest_pct)
                time.sleep(0.2)

            flash_thread.join()

            if flash_success:
                yield send_status("Flashing Complete! Reader is rebooting with new configuration.", 100)
            else:
                err_text = flash_error_msg or "OSDP file transfer rejected by reader."
                yield send_status(f"Flashing failed: {err_text}", 0, error=True)

        except Exception as e:
            yield send_status(f"OSDP Flashing Exception: {str(e)}", 0, error=True)
        finally:
            temp_bin_path.unlink(missing_ok=True)

    return Response(generate_events(), mimetype="text/event-stream")