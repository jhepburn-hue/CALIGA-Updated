import io
import json
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request, send_file

from core.translators.csv_loader import CSVConfigLoader
from core.translators.yaml_generator import build_sam_yaml
from services.forge_client import ForgeClient
from services.osdp_flasher import OsdpFlasher
from services.relay_client import RelayClient

tools_bp = Blueprint("tools", __name__, url_prefix="/tools")
loader = CSVConfigLoader()
forge_client = ForgeClient()

MAPPINGS_FILE = Path(__file__).parent.parent / "group_mappings.json"


@tools_bp.route("/")
def tools_index():
    """Renders the main tools index page with available utility routing options.

    Returns:
        str: Rendered HTML template response.
    """
    tools = [
        {
            "id": "translate",
            "name": "INI Translator",
            "description": "Convert INI files into readable formats.",
            "route": "/tools/translate",
        },
        {
            "id": "yaml",
            "name": "SAM YAML Generator",
            "description": (
                "Generate SAM configuration YAML files for cryptographic key"
                " chips."
            ),
            "route": "/tools/yaml",
        },
        {
            "id": "batch-tokens",
            "name": "Batch Token Generator",
            "description": (
                "Bulk query, compile, and register PocketBase tokens."
            ),
            "route": "/tools/tokens",
        },
        {
            "id": "batch-wallets",
            "name": "Batch Wallet Generator",
            "description": (
                "Batch request and issue Wallet Pass URLs and QR codes."
            ),
            "route": "/tools/wallets",
        },
    ]
    return render_template("tools-index.html", tools=tools)


@tools_bp.route("/translate")
def translate_tool():
    """Renders the INI translation tool view.

    Returns:
        str: Rendered HTML template response.
    """
    all_configs = loader.list_all_configurations()
    return render_template("ini-translator.html", configs=all_configs)


@tools_bp.route("/yaml", methods=["GET", "POST"])
def yaml_tool():
    """Renders or processes SAM configuration YAML file generation requests.

    Returns:
        Response: YAML file download or rendered HTML view template.
    """
    if request.method == "POST":
        yaml_content, download_filename = build_sam_yaml(request.form)
        return send_file(
            io.BytesIO(yaml_content.encode("utf-8")),
            mimetype="text/yaml",
            as_attachment=True,
            download_name=download_filename,
        )

    return render_template("yaml-generator.html")


@tools_bp.route("/tokens")
def tokens_tool():
    """Renders the batch token generator interface.

    Returns:
        str: Rendered HTML template response.
    """
    all_configs = loader.list_all_configurations()
    return render_template("batch-tokens.html", configs=all_configs)


@tools_bp.route("/api/generate-batch-tokens", methods=["POST"])
def generate_batch_tokens():
    """API endpoint to query, compile, and register PocketBase tokens in batch.

    Returns:
        Response: JSON response with itemized token processing results.
    """
    payload = request.get_json() or {}
    selected_filenames = payload.get("configs", [])
    target_version = payload.get("target_version", "v5.4.11")

    if not selected_filenames:
        return jsonify(
            {
                "success": False,
                "error": "Please select at least one configuration.",
            }
        ), 400

    results = []
    configs_dir = Path(__file__).parent.parent / "configs"

    for filename in selected_filenames:
        csv_path = configs_dir / filename
        if not csv_path.exists():
            continue

        try:
            config_obj = loader.load_by_filename(filename)
            token_data = forge_client.generate_tokens_flow(
                csv_file_path=csv_path,
                target_version=target_version,
                config_obj=config_obj,
            )
            results.append(
                {
                    "config_name": csv_path.stem.upper(),
                    "success": True,
                    "profile_token_name": token_data.get("profile_token_name"),
                    "profile_token": token_data.get("profile_token"),
                    "profile_cached": token_data.get("profile_cached"),
                    "firmware_token_name": token_data.get(
                        "firmware_token_name"
                    ),
                    "firmware_token": token_data.get("firmware_token"),
                    "firmware_cached": token_data.get("firmware_cached"),
                }
            )
        except Exception as e:
            results.append(
                {
                    "config_name": csv_path.stem.upper(),
                    "success": False,
                    "error": str(e),
                }
            )

    return jsonify({"success": True, "results": results})


def get_group_id_from_mapping(
    lk_number: str, environment: str = "staging"
) -> int | None:
    """Looks up the group ID for a specific reader keyset ID.

    Args:
        lk_number (str): The keyset ID (e.g. 'Lk10010').
        environment (str, optional): Target environment plane ('staging' or
          'prod'). Defaults to "staging".

    Returns:
        int | None: The mapped group ID integer if found, otherwise None.
    """
    if not MAPPINGS_FILE.exists():
        return None
    with open(MAPPINGS_FILE, "r") as f:
        mappings = json.load(f)

    env_key = (
        "prod" if environment.lower() in ("prod", "production") else "staging"
    )
    env_map = mappings.get(env_key, {})

    for key, gid in env_map.items():
        if key.lower() == lk_number.lower():
            return gid
    return None


@tools_bp.route("/wallets")
def wallets_tool():
    """Renders the batch wallet generator interface.

    Returns:
        str: Rendered HTML template response.
    """
    all_configs = loader.list_all_configurations()

    # Filter out configurations where keyset_id is missing, empty, or "None"
    valid_configs = [
        cfg
        for cfg in all_configs
        if cfg.keyset_id
        and str(cfg.keyset_id).strip().lower() not in ("none", "")
    ]

    return render_template("batch-wallets.html", configs=valid_configs)


@tools_bp.route("/api/generate-batch-wallets", methods=["POST"])
def generate_batch_wallets():
    """API endpoint to batch generate wallet passes using Relay Client.

    Returns:
        Response: JSON response containing generated pass URLs or errors.
    """
    payload = request.get_json() or {}
    selected_filenames = payload.get("configs", [])
    env_type = payload.get("environment", "staging").lower()
    is_staging = env_type == "staging"

    if not selected_filenames:
        return jsonify(
            {
                "success": False,
                "error": "Please select at least one configuration.",
            }
        ), 400

    results = []
    configs_dir = Path(__file__).parent.parent / "configs"
    relay = RelayClient(is_staging=is_staging)

    for filename in selected_filenames:
        csv_path = configs_dir / filename
        if not csv_path.exists():
            continue

        try:
            config_obj = loader.load_by_filename(filename)
            if not config_obj:
                continue

            lk_number = str(config_obj.keyset_id).strip()
            group_id = get_group_id_from_mapping(lk_number, env_type)

            if not group_id:
                results.append(
                    {
                        "config_name": csv_path.stem.upper(),
                        "keyset_id": lk_number,
                        "success": False,
                        "error": (
                            f"Reader ID '{lk_number}' is not mapped to a"
                            f" group_id in {env_type.upper()}."
                        ),
                    }
                )
                continue

            pass_result = relay.create_corporate_weblink(
                group_id=int(group_id),
                cardholder_data={
                    "first_name": config_obj.config_name,
                    "last_name": f"({lk_number})",
                },
            )

            if pass_result.get("success"):
                results.append(
                    {
                        "config_name": csv_path.stem.upper(),
                        "keyset_id": lk_number,
                        "group_id": group_id,
                        "success": True,
                        "wallet_url": pass_result.get("provisioning_link"),
                    }
                )
            else:
                results.append(
                    {
                        "config_name": csv_path.stem.upper(),
                        "keyset_id": lk_number,
                        "group_id": group_id,
                        "success": False,
                        "error": pass_result.get("error"),
                    }
                )

        except Exception as e:
            results.append(
                {
                    "config_name": csv_path.stem.upper(),
                    "keyset_id": "Unknown",
                    "success": False,
                    "error": str(e),
                }
            )

    return jsonify({"success": True, "results": results})


@tools_bp.route("/api/ports", methods=["GET"])
def get_serial_ports():
    """Endpoint returning available macOS and Windows COM ports.

    Returns:
        Response: JSON payload containing list of available serial device dicts.
    """
    ports = OsdpFlasher.get_available_ports()
    return jsonify({"ports": ports})