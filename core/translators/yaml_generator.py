"""
SAM YAML Generator Core Engine
Handles hex-formatted integers, dynamic SKU auto-incrementing, and 
structural YAML serialization matching Caliga specifications.
"""

import yaml

# Global OEM SKU ID mapping (increments in-memory during application runtime)
OEM_ID_MAP = {
    "BUTTERFLY_MX": 1,
    "BOA": 2,
    "REDHAT": 3,
    "UGA": 4,
    "CWO1": 5,
    "LEAF_SI": 6,
    "WELLS_FARGO": 7,
    "FIL": 8,
    "QUADREAL": 8,
    "SOLOINSIGHT": 10,
    "CARDINAL_HEALTH": 11,
    "BRIVO": 27,
    "TEST": 18,
    "TIAA": 61,
    "PDK": 62
}

SAM_TYPE_MAP = {
    "sam_av2": {"label": "SAM_AV2", "id": 2},
    "sam_av3": {"label": "SAM_AV3", "id": 3}
}

PART_MAP = {
    "elatec": {"label": "PARTNER_ELATEC", "id": 1},
    "rfideas": {"label": "PARTNER_RFIDEAS", "id": 2},
    "brivo": {"label": "PARTNER_BRIVO", "id": 3},
    "test": {"label": "PARTNER_TEST", "id": 4}
}

PART_KM_MAP = {
    "test": {"label": "partnerKm0", "id": 0},
    "elatec": {"label": "partnerKm1", "id": 1},
    "rfideas": {"label": "partnerKm2", "id": 2},
    "brivo": {"label": "partnerKm3", "id": 3},
    "pdq": {"label": "partnerKm4", "id": 4}
}

KEY_TYPE_MAP = {
    "aes_128": ("SAM_AES_128_KEY", 0x20),
    "mifare": ("SAM_MIFARE_KEY", 0x10)
}

KEY_USE_MAP = {
    "picc": ("SAM_PICC_KEY", 1),
    "offline_crypto": ("SAM_OFFLINE_CRYPTO_KEY", 1)
}

ECP_TERMINAL_MAP = {
    "tra_express": ("ECP_WL_TERMINAL_INFO", 0xC3),
    "tra_enabled": ("ECP_WL_TERMINAL_INFO_USER_AUTH", 0x83)
}

ECP_SUBTYPE_MAP = {
    "university": ("ECP_TERMINAL_SUBTYPE_UNIVERSITY", 0),
    "corporate": ("ECP_TERMINAL_SUBTYPE_CORPORATE", 2),
    "hospitality": ("ECP_TERMINAL_SUBTYPE_HOSPITALITY", 3),
    "residential": ("ECP_TERMINAL_SUBTYPE_RESIDENTIAL", 4)
}

ECP_APP_MAP = {
    "credential_app": ("ECP_OPTIONS_1", 1),
    "secure_app": ("ECP_OPTIONS_2", 2)
}


class HexInt(int):
    """Custom integer wrapper for PyYAML 0x-hex scalar formatting."""
    pass


def hex_int_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:int', f'0x{data:02X}')


yaml.add_representer(HexInt, hex_int_representer)


def build_sam_yaml(form_data: dict) -> tuple[str, str]:
    """
    Builds the structural dictionary and serializes it to formatted YAML text.
    Returns a tuple of (yaml_string, dynamic_filename).
    """
    global OEM_ID_MAP

    sam_choice = form_data.get('sam_type_choice')
    sam_info = SAM_TYPE_MAP.get(sam_choice, {"label": "SAM_AV3", "id": 3})

    partner_choice = form_data.get('partner_choice')
    partner_info = PART_MAP.get(partner_choice, {"label": "PARTNER_RFIDEAS", "id": 2})

    partner_km_choice = form_data.get('partner_km_choice')
    partner_km_info = PART_KM_MAP.get(partner_km_choice, {"label": "partnerKm2", "id": 2})

    raw_oem_input = form_data.get('oem', '').strip()
    oem_clean = raw_oem_input.replace(' ', '_').upper()

    if oem_clean and oem_clean not in OEM_ID_MAP:
        next_id = max(OEM_ID_MAP.values()) + 1
        OEM_ID_MAP[oem_clean] = next_id

    sku_oem_id = OEM_ID_MAP.get(oem_clean, 62)

    leaf_cc_input = form_data.get('leaf_cc_choice', '').strip() or "NO_LK"
    tci_raw = str(form_data.get('tci_choice', '0x000000')).strip().lower().replace("0x", "").zfill(6)
    
    # Construct dynamic filename: <SKU>_<LK>_<TCI>.yaml
    dynamic_filename = f"{oem_clean or 'SKU'}_{leaf_cc_input}_{tci_raw.upper()}.yaml"

    tci_1 = HexInt(int(tci_raw[0:2], 16))
    tci_2 = HexInt(int(tci_raw[2:4], 16))
    tci_3 = HexInt(int(tci_raw[4:6], 16))

    specialty_keys_config = None
    if form_data.get('specialty_keys_choice') == "true":
        version_input = int(form_data.get('key_version', '0'))
        version_labels = {0: "key_version_a", 1: "key_version_b", 2: "key_version_c"}

        type_label, type_hex = KEY_TYPE_MAP.get(form_data.get('key_type_choice'), ("SAM_MIFARE_KEY", 0x10))
        use_label, use_id = KEY_USE_MAP.get(form_data.get('key_use_choice'), ("SAM_PICC_KEY", 1))

        specialty_keys_config = {
            "key2": {
                "key_slot": int(form_data.get('key_slot', 64)),
                "key_version": [{version_labels.get(version_input, "key_version_a"): version_input}],
                "sel_key_version": version_input,
                "key_type": [{type_label: HexInt(type_hex)}],
                "sel_key_type": HexInt(type_hex),
                "key_use": [{use_label: use_id}],
                "sel_key_use": use_id
            }
        }

    m2g_choice = form_data.get('mifare_2go_app_id_choice')
    m2g_msb, m2g_hsb, m2g_lsb = (0xF5, 0x1C, 0xDF) if m2g_choice == "leaf" else (0xF5, 0x32, 0xF0)

    term_label, term_hex = ECP_TERMINAL_MAP.get(form_data.get('ecp_terminal_choice'), ("ECP_WL_TERMINAL_INFO", 0xC3))
    sub_label, sub_id = ECP_SUBTYPE_MAP.get(form_data.get('ecp_terminal_subtype_choice'), ("ECP_TERMINAL_SUBTYPE_CORPORATE", 2))
    app_label, app_id = ECP_APP_MAP.get(form_data.get('ecp_app_choice'), ("ECP_OPTIONS_1", 1))
    bit_count_raw = form_data.get('ecp_bit_count_choice')

    yaml_structure = {
        "sam_type": [{"SAM_AV2": 2}, {"SAM_AV3": 3}],
        "sel_sam_type": sam_info["id"],
        "partner": [
            {"PARTNER_ELATEC": 1},
            {"PARTNER_RFIDEAS": 2},
            {"PARTNER_BRIVO": 3},
            {"PARTNER_TEST": 4}
        ],
        "sel_partner": partner_info["id"],
        "partner_km": [
            {"partnerKm0": 0}, {"partnerKm1": 1}, {"partnerKm2": 2}, {"partnerKm3": 3},
            {"partnerKm4": 4}, {"partnerKm5": 5}, {"partnerKm6": 6}, {"partnerKm7": 7},
            {"partnerKm8": 8}, {"partnerKm9": 9}, {"partnerKm10": 10}, {"partnerKm11": 11},
            {"partnerKm12": 12}, {"partnerKm13": 13}, {"partnerKm14": 14}, {"partnerKm15": 15}
        ],
        "sel_partner_km": partner_km_info["id"],
        "sku_oem": [{f"SKU_{k}": v} for k, v in OEM_ID_MAP.items()],
        "sel_sku_oem": sku_oem_id,
        "sel_Wl_lk": form_data.get('leaf_si_choice') == "true",
        "OEM_lk1_name": leaf_cc_input or None,
        "OEM_lk2_name": form_data.get('second_leaf_cc_choice') or None,
        "specialty_keys": specialty_keys_config,
        "tci_1": tci_1,
        "tci_2": tci_2,
        "tci_3": tci_3,
        "ecp_format": [
            {"ECP_FORMAT_1": 1},
            {"ECP_FORMAT_2": 2}
        ],
        "sel_ecp_format": 2,
        "ecp_terminal_info_mode": [
            {"ECP_WL_TERMINAL_INFO": HexInt(0xC3)},
            {"ECP_WL_TERMINAL_INFO_USER_AUTH": HexInt(0x83)}
        ],
        "sel_ecp_terminal_info_mode": HexInt(term_hex),
        "ecp_terminal_type": 2,
        "ecp_terminal_subtype": [
            {"ECP_TERMINAL_SUBTYPE_UNIVERSITY": 0},
            {"ECP_TERMINAL_SUBTYPE_CORPORATE": 2},
            {"ECP_TERMINAL_SUBTYPE_HOSPITALITY": 3},
            {"ECP_TERMINAL_SUBTYPE_RESIDENTIAL": 4}
        ],
        "sel_ecp_terminal_subtype": sub_id,
        "ecp_bit_count": int(bit_count_raw) if bit_count_raw else 40,
        "ecp_app_options": [
            {"ECP_OPTIONS_1": 1},
            {"ECP_OPTIONS_2": 2}
        ],
        "sel_ecp_app_options": app_id,
        "M2G_AID_MSB": HexInt(m2g_msb),
        "M2G_AID_HSB": HexInt(m2g_hsb),
        "M2G_AID_LSB": HexInt(m2g_lsb),
        "PF_func": [
            {"PF_FUNC_NO_FILTER": 0},
            {"PF_FUNC_EQ": 1},
            {"PF_FUNC_ME": 2},
            {"PF_FUNC_LE": 3},
            {"PF_FUNC_NE": 4}
        ],
        "sel_PF_func": 0,
        "PF_num_bits": 0,
        "filter_all": False,
        "PF_value": 0,
        "bit_stream": None,
        "filtered_field_tag": [
            {"UNUSED": 0},
            {"BS_BID_MAP": HexInt(0xB2)},
            {"BS_FAC_MAP": HexInt(0xB3)},
            {"BS_CITY_CODE_MAP": HexInt(0xB5)},
            {"BS_TECH_NUM_MAP": HexInt(0xB6)}
        ],
        "sel_filtered_field_tag": 0
    }

    yaml_string = yaml.dump(yaml_structure, default_flow_style=False, sort_keys=False)

    section_breaks = [
        "\npartner:", "\npartner_km:", "\nsku_oem:", "\nsel_Wl_lk:", "\nspecialty_keys:",
        "\ntci_1:", "\necp_format:", "\necp_terminal_info_mode:", "\necp_terminal_type:",
        "\necp_terminal_subtype:", "\necp_bit_count:", "\necp_app_options:", "\nM2G_AID_MSB:",
        "\nPF_func:", "\nPF_num_bits:", "\nfilter_all:", "\nPF_value:", "\nbit_stream:", "\nfiltered_field_tag:"
    ]

    for section in section_breaks:
        yaml_string = yaml_string.replace(f"{section}", f"\n{section}")

    return yaml_string, dynamic_filename