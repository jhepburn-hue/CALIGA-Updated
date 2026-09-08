from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class ConfigStatus(str, Enum):
    ACTIVE = "Active"
    POC = "POC"
    ARCHIVED = "Archived"


class HardwareProfile(BaseModel):
    wiegand_2ws: bool = False
    wiegand_3ws: bool = False
    wiegand_6ws: bool = False
    wiegand_7ws: bool = False
    f2f_7fm: bool = False
    mclp_7fm: bool = False


class AudioVisualSettings(BaseModel):
    idle_led_color: str = "Off"
    credential_led_color: str = "Green"
    beeper_enabled: bool = True
    keypad_format: str = "8-bit"
    tamper_monitoring: bool = True


class HighFrequencySettings(BaseModel):
    leaf_si_app: str = "None"
    leaf_cc_app: str = "None"
    custom_hf_app: str = "None"
    notes: str = ""


class CardSerialNumberSettings(BaseModel):
    mfc_csn: str = "Off"
    ev1_ev2_csn: str = "Off"
    iclass_csn: str = "Off"
    iso15693_csn: str = "Off"
    iso14443a_csn: str = "Off"


class LowFrequencySettings(BaseModel):
    fsk_prox: bool = True
    ask_prox: bool = True
    prox_filter_enabled: bool = False
    prox_filter_description: str = ""


class MobileCapabilities(BaseModel):
    ble_advertising: str = "Unique (Differs)"
    ble_functionality: str = "Admin Only"
    nfc_enabled: str = "Enabled"
    mobile_keyset: str = "Custom"
    legacy_credentials: str = "Off"
    transport_mode: str = "Off"
    ecp_desfire_enabled: str = "Disabled"
    ecp_tci: str = ""
    apple_meridian_bit_count: str = "40"
    mifare2go_enabled: str = "Disabled"
    mifare2go_dfname: str = ""
    mobile_notes: str = ""


class ReaderConfiguration(BaseModel):
    config_name: str
    filename: str
    config_id_dec: int = Field(..., ge=0, le=65535)
    config_id_hex: str
    status: ConfigStatus = ConfigStatus.POC
    keyset_id: Optional[str] = Field("None")
    assigned_part_numbers: List[str] = Field(default_factory=list)

    hardware: HardwareProfile = Field(default_factory=HardwareProfile)
    audio_visual: AudioVisualSettings = Field(default_factory=AudioVisualSettings)
    high_frequency: HighFrequencySettings = Field(default_factory=HighFrequencySettings)
    csn: CardSerialNumberSettings = Field(default_factory=CardSerialNumberSettings)
    low_frequency: LowFrequencySettings = Field(default_factory=LowFrequencySettings)
    mobile: MobileCapabilities = Field(default_factory=MobileCapabilities)

    @field_validator("config_id_hex", mode="before")
    @classmethod
    def format_hex_id(cls, v: str | int) -> str:
        if isinstance(v, int):
            return f"0x{v:04X}"
        if isinstance(v, str) and not v.startswith("0x"):
            try:
                return f"0x{int(v):04X}"
            except ValueError:
                return v
        return v