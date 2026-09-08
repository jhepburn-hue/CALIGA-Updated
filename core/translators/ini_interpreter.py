"""
INI Interpreter Module
Parses raw INI configuration text and maps the key-value settings into 
structured, card-based test criteria identical to the Testing Portal layout.
"""

import configparser


def interpret_ini_to_cards(raw_ini_text: str, config_name: str = "CONFIG") -> list:
    """
    Parses raw INI text and extracts structured verification check cards.
    """
    parser = configparser.ConfigParser(allow_no_value=True, strict=False)
    
    try:
        parser.read_string(raw_ini_text)
    except Exception:
        parser.read_string(f"[GLOBAL]\n{raw_ini_text}")

    # Helper function to extract key value safely across sections
    def get_ini_val(keys, default="Off"):
        if isinstance(keys, str):
            keys = [keys]
        for section in parser.sections():
            for k, v in parser.items(section):
                if k.lower().strip() in [key.lower() for key in keys]:
                    clean_v = v.strip()
                    if clean_v == "1":
                        return "On"
                    elif clean_v == "0":
                        return "Off"
                    return clean_v
        return default

    cards = [
        {
            "card_id": "av_outputs",
            "title": "Verify AV and Output Formats.",
            "criteria": [
                {"label": "Idle LED", "value": get_ini_val(["idle_led", "idle_led_color"], "Red")},
                {"label": "Credential Report LED", "value": get_ini_val(["cred_led", "credential_led_color"], "Green")},
                {"label": "Beeper", "value": get_ini_val(["beeper", "beeper_enabled"], "On")},
                {"label": "Keypad Format", "value": get_ini_val(["keypad_fmt", "keypad_format"], "8-bit")},
                {"label": "Tampering Monitoring", "value": get_ini_val(["tamper", "tamper_monitoring"], "On")},
                {"label": "Config ID", "value": get_ini_val(["config_id", "cfg_id"], "0 (0x0000)")}
            ]
        },
        {
            "card_id": "hf_credentials",
            "title": "Present the HF credential.",
            "criteria": [
                {"label": "Leaf Si Application (Kv1)", "value": get_ini_val(["leaf_si", "leaf_si_app"], "None")},
                {"label": "Leaf Cc Application (Kc1)", "value": get_ini_val(["leaf_cc", "leaf_cc_app"], "Leaf Cc")},
                {"label": "Other Custom HF Application", "value": get_ini_val(["custom_hf", "other_hf_app"], "None")}
            ]
        },
        {
            "card_id": "csn_credentials",
            "title": "Verify Card Serial Number (CSN) credentials.",
            "criteria": [
                {"label": "MFC CSN", "value": get_ini_val(["mfc_csn"], "Off")},
                {"label": "EV1/EV2 CSN", "value": get_ini_val(["ev1_ev2_csn", "ev_csn"], "Off")},
                {"label": "iClass CSN", "value": get_ini_val(["iclass_csn"], "Off")},
                {"label": "ISO 15693 CSN", "value": get_ini_val(["iso15693_csn"], "Off")},
                {"label": "ISO 14443A", "value": get_ini_val(["iso14443a_csn"], "Off")}
            ]
        },
        {
            "card_id": "lf_credentials",
            "title": "Verify Low Frequency (LF) credentials.",
            "criteria": [
                {"label": "FSK Prox", "value": get_ini_val(["fsk_prox", "fsk"], "On")},
                {"label": "ASK Prox", "value": get_ini_val(["ask_prox", "ask"], "On")},
                {"label": "Prox Filter", "value": get_ini_val(["prox_filter"], "Off")}
            ]
        },
        {
            "card_id": "mobile_credentials",
            "title": "Verify Mobile & Pass credentials.",
            "criteria": [
                {"label": "BLE Advertising", "value": get_ini_val(["ble_advertising", "ble_adv"], "Unique (Differs)")},
                {"label": "BLE Functionality", "value": get_ini_val(["ble_functionality", "ble_func"], "Admin Only")},
                {"label": "MiFare2Go Wallet", "value": get_ini_val(["mifare2go", "mifare2go_enabled"], "Disabled")}
            ]
        }
    ]

    return cards