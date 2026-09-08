import csv
import re
from pathlib import Path
from typing import Dict, List, Optional
from core.models.config import (
    AudioVisualSettings,
    CardSerialNumberSettings,
    ConfigStatus,
    HardwareProfile,
    HighFrequencySettings,
    LowFrequencySettings,
    MobileCapabilities,
    ReaderConfiguration,
)


class CSVConfigLoader:
    def __init__(self, configs_dir: str | Path = "configs"):
        self.configs_dir = Path(configs_dir)

    def list_all_configurations(self) -> List[ReaderConfiguration]:
        configurations = []
        if not self.configs_dir.exists():
            return configurations

        for file_path in sorted(self.configs_dir.glob("*.csv")):
            config = self.load_by_filename(file_path.name)
            if config:
                configurations.append(config)

        return sorted(configurations, key=lambda c: c.config_id_dec)

    def _extract_ids(self, file_path: Path) -> tuple[int, str]:
        dec_id = 0
        hex_id = ""
        try:
            with open(file_path, mode="r", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                for row in reader:
                    for idx, cell in enumerate(row):
                        cell_str = cell.strip()
                        if "config id" in cell_str.lower():
                            numbers = re.findall(r"\b\d+\b", cell_str)
                            if numbers:
                                dec_id = int(numbers[0])
                            elif idx + 1 < len(row) and row[idx + 1].strip().isdigit():
                                dec_id = int(row[idx + 1].strip())
                            elif idx + 2 < len(row) and row[idx + 2].strip().isdigit():
                                dec_id = int(row[idx + 2].strip())

                        if "0x" in cell_str.lower():
                            hex_match = re.search(r"0x[0-9a-fA-F]+", cell_str)
                            if hex_match:
                                hex_id = hex_match.group(0).upper()
        except Exception:
            pass

        if not hex_id:
            hex_id = f"0x{dec_id:04X}"
        return dec_id, hex_id

    def load_by_filename(self, filename: str) -> Optional[ReaderConfiguration]:
        file_path = self.configs_dir / filename
        if not file_path.is_file():
            return None

        clean_name = re.sub(r"^[^\w]+", "", file_path.stem)
        dec_id, hex_id = self._extract_ids(file_path)

        fields: Dict[str, str] = {}
        part_numbers: List[str] = []

        try:
            with open(file_path, mode="r", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                for row in reader:
                    if not row:
                        continue

                    for i in range(len(row)):
                        cell_k = row[i].strip()
                        if not cell_k or cell_k.startswith("STEP") or "Form" in cell_k:
                            continue

                        norm_k = re.sub(r"\s+", " ", cell_k.lower().replace("\n", " "))

                        cell_v = ""
                        for j in range(i + 1, len(row)):
                            if row[j].strip():
                                cell_v = row[j].strip().replace("\n", " ")
                                break

                        if cell_v:
                            fields[norm_k] = cell_v

                        if "assigned" in norm_k and "part" in norm_k and cell_v:
                            part_numbers.append(cell_v)

        except Exception:
            pass

        def get_val(keys: List[str], default: str = "") -> str:
            for k in keys:
                for fk, fv in fields.items():
                    if k in fk:
                        return fv
            return default

        raw_status = fields.get("status", "Active")
        try:
            status = ConfigStatus(raw_status.capitalize())
        except ValueError:
            status = ConfigStatus.POC

        return ReaderConfiguration(
            config_name=clean_name,
            filename=filename,
            config_id_dec=dec_id,
            config_id_hex=hex_id,
            status=status,
            keyset_id=get_val(["keyset id", "keyset_id"], "None"),
            assigned_part_numbers=part_numbers or [get_val(["part number"], "None")],
            hardware=HardwareProfile(
                wiegand_2ws=get_val(["-2ws"], "No").lower() == "yes",
                wiegand_3ws=get_val(["-3ws"], "No").lower() == "yes",
                wiegand_6ws=get_val(["-6ws"], "No").lower() == "yes",
                wiegand_7ws=get_val(["-7ws"], "No").lower() == "yes",
                f2f_7fm=get_val(["f2f"], "No").lower() == "yes",
                mclp_7fm=get_val(["mclp"], "No").lower() == "yes",
            ),
            audio_visual=AudioVisualSettings(
                idle_led_color=get_val(["idle led"], "Off"),
                credential_led_color=get_val(["credential report led"], "Green"),
                beeper_enabled=get_val(["beeper"], "On").lower() != "off",
                keypad_format=get_val(["keypad format"], "8-bit"),
                tamper_monitoring=get_val(["tamper monitoring"], "On").lower() != "off",
            ),
            high_frequency=HighFrequencySettings(
                leaf_si_app=get_val(["leaf si application", "leaf si"], "None"),
                leaf_cc_app=get_val(["leaf cc application", "leaf cc"], "None"),
                custom_hf_app=get_val(["other custom hf application"], "None"),
                notes=get_val(["custom application notes"], ""),
            ),
            csn=CardSerialNumberSettings(
                mfc_csn=get_val(["mfc csn"], "Off"),
                ev1_ev2_csn=get_val(["ev1/ev2 csn"], "Off"),
                iclass_csn=get_val(["iclass csn"], "Off"),
                iso15693_csn=get_val(["iso15693 csn"], "Off"),
                iso14443a_csn=get_val(["iso14443a csn"], "Off"),
            ),
            low_frequency=LowFrequencySettings(
                fsk_prox=get_val(["fsk prox"], "On").lower() == "on",
                ask_prox=get_val(["ask prox"], "On").lower() == "on",
                prox_filter_enabled=get_val(["prox filter"], "Off").lower() == "on",
                prox_filter_description=get_val(["prox filter description"], ""),
            ),
            mobile=MobileCapabilities(
                ble_advertising=get_val(["ble advertising config", "ble advertising"], "Unique (Differs)"),
                ble_functionality=get_val(["ble functionality"], "Admin Only"),
                nfc_enabled=get_val(["nfc functionality"], "Enabled"),
                mobile_keyset=get_val(["mobile keyset"], "Custom"),
                legacy_credentials=get_val(["legacy credentials"], "Off"),
                transport_mode=get_val(["transport mode"], "Off"),
                ecp_desfire_enabled=get_val(["ecp desfire"], "Disabled"),
                ecp_tci=get_val(["ecp tci"], ""),
                apple_meridian_bit_count=get_val(["apple meridian bit count"], "40"),
                mifare2go_enabled=get_val(["mifare2go"], "Disabled"),
                mifare2go_dfname=get_val(["mifare2go dfname"], ""),
                mobile_notes=get_val(["mobile notes"], ""),
            ),
        )