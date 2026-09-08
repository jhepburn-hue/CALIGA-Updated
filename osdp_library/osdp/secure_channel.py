from enum import IntEnum
import secrets
from typing import Optional
from .constants import SCBK_D_KEY, SecurityBlockType, CommandTags, ResponseTags
from .exceptions import (
    SecureChannelModeError,
    MacVerificationError,
    IncompleteSetupError,
    SecureChannelEstablishmentError,
)
from .message import OsdpMessage, OsdpMessageDirection
from .utils import AES_BLOCK_SIZE, decrypt, encrypt, ones_complement, pad_data


class ScbkMode(IntEnum):
    CUSTOM = 0
    """
    Use preset/custom base key.
    """

    DEFAULT = 1
    """
    Use deprecated key default method.
    """


class SecureChannelState(IntEnum):
    INACTIVE = 0
    """
    Secure channel is not active - no encryption/MAC processing.
    """

    # The below states and values are borrowed from security block constants used in the sc
    # handshake

    SCS_11 = 1
    """
    Challenge command is pending.
    """

    SCS_12 = 2
    """
    Ccrypt response is pending.
    """

    SCS_13 = 3
    """
    Scrypt command is pending.
    """

    SCS_14 = 4
    """
    Rmac_i command is pending. The SC is considered active in this state, but no messages
    have been transferred.
    """

    ACTIVE = 5
    """
    Secure channel is fully active - all required keys are set and ready for encryption/MAC.
    """

    def next(self) -> "SecureChannelState":
        """
        Gets the next sc state.

        :return Next SC state value:
        """
        if self.value < SecureChannelState.ACTIVE:
            return SecureChannelState(self.value + 1)
        else:
            return self

    def is_inactive(self) -> bool:
        """
        Helper function to check if sc state is completely inactive.

        :return T/F whether state is inactive:
        """
        return self.value == SecureChannelState.INACTIVE

    def is_pending(self) -> bool:
        """
        Helper function to check if there is a pending sc handshake, which means
        the state is in between INACTIVE and SCS_14. If SCS_14 is acheived then
        the secure channel state is considered active, as both sides have what they
        need and have verified validity.

        :return T/F whether there is a pending handshake:
        """
        return (self.value > SecureChannelState.INACTIVE) and (
                self.value < SecureChannelState.SCS_14
        )

    def is_active(self) -> bool:
        """
        Helper function to check if the sc state is active, which is whenever the state
        enum is SCS_14 or greater.

        :return T/F whether SC is active:
        """
        return self.value >= SecureChannelState.SCS_14

    @classmethod
    def first(cls) -> "SecureChannelState":
        """
        Gets the initial sc state.

        :return Initial sc state value:
        """
        return SecureChannelState.INACTIVE


class OsdpSecureChannelContext:
    """
    Handles context and secure channel messaging state.

    - Holds all cryptographic primitives used in SC.
    - Provides convenience functions for creating SC negotiation messages.
    - Provides SC negotiation state management.
    - Facilitates "wrapping" and "unwrapping" of SC messages once the SC is active.
    """

    scbk: bytes
    """
    Secure channel base key.
    """

    rnda: bytes
    """
    Random A used in SC negotiation.
    """

    rndb: bytes
    """
    Random B used in SC negotiation.
    """

    senc: bytes
    """
    Derived session encryption key.
    """

    smac1: bytes
    """
    Derived mac key 1.
    """

    smac2: bytes
    """
    Derived mac key 2.
    """

    cmac: bytes
    """
    Command MAC.
    """

    rmac: bytes
    """
    Response MAC.
    """

    mode: ScbkMode
    """
    Secure channel base key mode.
    """

    state: SecureChannelState
    """
    Secure channel state tracking.
    """

    TRUNCATED_MAC_LEN: int = 4
    """
    Number of bytes to truncate MAC to for the message field.
    """

    def __init__(
            self, secure_channel_base_key: Optional[bytes], mode: ScbkMode = ScbkMode.CUSTOM
    ):
        """
        Setup the secure channel context with the correct scbk matching the specified mode.
        A scbk will need to be provided for custom key mode, and a cuid provided for derived key mode.
        """
        self.reset()
        self.mode = mode

        if mode == ScbkMode.CUSTOM:
            if secure_channel_base_key:
                self.scbk = secure_channel_base_key
            else:
                raise SecureChannelModeError("must supply scbk for custom key mode")
        elif mode == ScbkMode.DEFAULT:
            self.scbk = SCBK_D_KEY
        else:
            raise SecureChannelModeError("unsupported secure channel mode")

    def reset(self):
        """
        Reset all secure channel primitives.
        """
        self.rnda = bytes(0)
        self.rndb = bytes(0)
        self.senc = bytes(0)
        self.smac1 = bytes(0)
        self.smac2 = bytes(0)
        self.cmac = bytes(0)
        self.rmac = bytes(0)
        self.state = SecureChannelState.INACTIVE

    def get_state(self) -> SecureChannelState:
        """
        Get the current secure channel state.

        :return: Current secure channel state
        """
        return self.state

    def gen_state(self) -> IntEnum:
        """
        Set the member state variable to SCS_11 (numeric value of 1)
        to indicate that state is pending.

        :return: Member state variable with the pending state of secure channel.
        """

        self.state = SecureChannelState.SCS_11
        return self.state

    def gen_rnda(self) -> bytes:
        """
        Generate a 8-byte random number for RNDA.

        :return: 8-byte random number as bytes
        """

        token_bytes: bytes = secrets.token_bytes(8)
        return token_bytes

    def receive_rnda(self, rnda: bytes):
        self.rnda = rnda

        # update the state to indicate a acu challenge is being reveived.
        self.state = SecureChannelState.SCS_11

    def gen_rndb(self) -> bytes:
        """
        Generate a 8-byte random number for RNDB.

        :return: 8-byte random number as bytes
        """
        self.rndb = secrets.token_bytes(8)
        return self.rndb

    def receive_rndb(self, rndb: bytes):
        self.rndb = rndb

    def derive_session_keys(self) -> None:
        """
        Derive session keys (S-ENC, S-MAC1, S-MAC2) using SCBK and RNDA. Store them in the context class variables.

        Taken directly from the OSDP specification:

        A set of three keys are derived and used for each secure communication session. The derivation
        operation uses the current SCBK and encrypts a data block generated for each key. The values are
        derived by encrypting these data blocks using the current SCBK.

        S-ENC = Encrypt the string
        (0x01,0x82,RND.A[0],RND.A[1],RND.A[2],RND.A[3],RND.A[4],RND.A[5],0,0,…) with SCBK.

        S-MAC1 = Encrypt the string
        (0x01,0x01,RND.A[0],RND.A[1],RND.A[2],RND.A[3],RND.A[4],RND.A[5],0,0,…) with SCBK.

        S-MAC2 = Encrypt the string
        (0x01,0x02,RND.A[0],RND.A[1],RND.A[2],RND.A[3],RND.A[4],RND.A[5],0,0,…) with SCBK.

        RND.A[8] is an 8-byte random number generated by the ACU and is transferred to the PD during the
        SCS_11 step.
        """
        # Ensure RNDA has been generated (take first 6 bytes as specified)
        if not self.rnda:
            raise ValueError("RNDA must be generated before deriving session keys")

        rnd_a_6_bytes = self.rnda[:6]

        # Create data blocks for key derivation (16 bytes each, padded with zeros)
        senc_data = bytearray([0x01, 0x82])  # Use specified prefix
        senc_data.extend(rnd_a_6_bytes)  # Add the random value
        senc_data.extend([0x00] * 8)  # Pad to 16 bytes

        smac1_data = bytearray([0x01, 0x01])  # Use specified prefix
        smac1_data.extend(rnd_a_6_bytes)  # Add the random value
        smac1_data.extend([0x00] * 8)  # Pad to 16 bytes

        smac2_data = bytearray([0x01, 0x02])  # Use specified prefix
        smac2_data.extend(rnd_a_6_bytes)  # Add the random value
        smac2_data.extend([0x00] * 8)  # Pad to 16 bytes

        # Derive session keys by encrypting data blocks with SCBK
        self.senc = encrypt(self.scbk, bytes(senc_data))
        self.smac1 = encrypt(self.scbk, bytes(smac1_data))
        self.smac2 = encrypt(self.scbk, bytes(smac2_data))

    def calc_client_cryptogram(self) -> bytes:
        """
        Calculate the client cryptogram using RNDA, RNDB, and session encryption key.

        :return: Client cryptogram as bytes
        """
        if not self.rnda or not self.rndb or not self.senc:
            raise ValueError(
                "RNDA, RNDB, and SENC must be populated to calc client cryptogram"
            )

        # update the state to indicate that at least a ccrypt response has been sent/received
        self.state = SecureChannelState.SCS_12

        return encrypt(self.senc, self.rnda + self.rndb)

    def calc_server_cryptogram(self) -> bytes:
        """
        Calculate the server cryptogram using RNDB, RNDA, and session encryption key.

        :return: Server cryptogram as bytes
        """
        if not self.rnda or not self.rndb or not self.senc:
            raise ValueError(
                "RNDA, RNDB, and SENC must be populated to calc server cryptogram"
            )

        # update the state to indicate that at least a scrypt response has been sent/received
        self.state = SecureChannelState.SCS_13

        return encrypt(self.senc, self.rndb + self.rnda)

    def calc_mac(self, message: bytes, mac_i: bytes) -> bytes:
        """
        Calculate the MAC (Message Authentication Code) for a given message.

        :param message: Message bytes to calculate MAC for
        :param mac_i: Initial MAC value
        :return: Calculated MAC as bytes
        """
        if not self.smac1 or not self.smac2:
            raise ValueError("Session keys must be derived before calculating MAC")

        padded_message: bytes = message
        if (len(message) % AES_BLOCK_SIZE) != 0:
            padded_message = pad_data(message)

        mac: bytes = mac_i
        num_blocks: int = len(padded_message) // AES_BLOCK_SIZE

        # Process all blocks except the last one with CBC using smac1
        if num_blocks > 1:
            mac = encrypt(
                self.smac1, padded_message[:-AES_BLOCK_SIZE], mode="CBC", iv=mac
            )

        # Final block is encrypted with smac2 using current MAC as IV
        final_block = padded_message[-AES_BLOCK_SIZE:]

        # The final mac blocks are the final 16 bytes of the mac, which is the actual message.
        # For OSDP commands which may carry a message that is greater than 16 bytes in size, this is provided as
        # a convenience cut-off so that only the data of interest if processed via the encryption.
        final_mac_blocks: bytes = mac[-AES_BLOCK_SIZE:]
        final_mac: bytes = encrypt(self.smac2, final_block, mode="CBC", iv=final_mac_blocks)

        return final_mac

    def calc_rmaci(self, server_cryptogram: bytes) -> bytes:
        """
        Calculate the response MAC initial value using the server cryptogram.

        :param server_cryptogram: Server cryptogram bytes
        :return: Calculated RMAC value as bytes
        """
        if not self.smac1 or not self.smac2:
            raise ValueError("smac1 and smac2 keys must be set to calculate rmac")

        ciphertext: bytes = encrypt(self.smac1, server_cryptogram)
        self.rmac = encrypt(self.smac2, ciphertext)

        # update the state to indicate that a rmac_i has been sent/received and channel is active
        self.state = SecureChannelState.ACTIVE

        return self.rmac

    def wrap_message(self, msg: OsdpMessage) -> OsdpMessage:
        """
        Wrap an OSDP message with secure channel encryption and MAC.

        :param msg: OSDP message to wrap
        :return: Wrapped OSDP message with security applied
        """
        # Handle secure channel handshake messages specially - this takes priority
        # over secure channel state since handshake messages need special handling
        # even when the channel is transitioning to ACTIVE state
        if self._is_secure_channel_handshake_message(msg):
            return self._wrap_handshake_message(msg)

        # Only bypass wrapping if secure channel is completely inactive AND no security block
        if self.state.is_inactive() and not msg.security_block:
            return msg

        # For non-handshake messages during secure channel establishment (PENDING state),
        # don't wrap with security if we don't have the required MAC keys yet
        if self.state.is_pending():
            if msg.direction == OsdpMessageDirection.COMMAND and not self.rmac:
                return msg
            elif msg.direction == OsdpMessageDirection.REPLY and not self.cmac:
                return msg

        # Standard secure channel message wrapping (allow PENDING/ACTIVE states for testing)
        if not msg.security_block:
            raise SecureChannelEstablishmentError(
                "security block required to be present in order to wrap handshake message"
            )

        msg.security_block.requires_mac = True

        icv: bytes
        maci: bytes

        if msg.direction == OsdpMessageDirection.COMMAND:
            msg.security_block.type = SecurityBlockType.SCS_15
            if msg.data:
                msg.security_block.type = SecurityBlockType.SCS_17

            if not self.rmac:
                raise ValueError("rmac required to wrap secure channel command")

            icv = ones_complement(self.rmac)
            maci = self.rmac
        else:
            msg.security_block.type = SecurityBlockType.SCS_16
            if msg.data:
                msg.security_block.type = SecurityBlockType.SCS_18

            if not self.cmac:
                raise ValueError("cmac required to wrap secure channel reply")

            icv = ones_complement(self.cmac)
            maci = self.cmac

        # encrypt the message data if it exists
        if msg.data:
            msg.data = bytearray(pad_data(msg.data))
            msg.data = encrypt(self.senc, msg.data, "CBC", icv[:AES_BLOCK_SIZE])

        full_mac = self.calc_mac(msg.get_mac_calc_bytes(), maci)
        msg.mac = bytearray(
            full_mac[: self.TRUNCATED_MAC_LEN]
        )  # Only first 4 bytes go in the message

        # store the full mac for the next cmd/reply
        if msg.direction == OsdpMessageDirection.COMMAND:
            self.cmac = full_mac
        else:
            self.rmac = full_mac

        return msg

    @classmethod
    def _is_secure_channel_handshake_message(cls, msg: OsdpMessage) -> bool:
        """
        Check if message is part of secure channel handshake.

        :param msg: Message to check
        :return: True if message is part of handshake
        """
        handshake_commands = {CommandTags.CHLNG, CommandTags.SCRYPT}
        handshake_responses = {ResponseTags.CCRYPT, ResponseTags.RMAC_I}

        return (
                msg.command_reply_code in handshake_commands
                or msg.command_reply_code in handshake_responses
        )

    def _wrap_handshake_message(self, msg: OsdpMessage) -> OsdpMessage:
        """
        Wrap secure channel handshake message with appropriate security block.

        :param msg: Handshake message to wrap
        :return: Wrapped message with correct SCS security block
        """
        if not msg.security_block:
            raise SecureChannelEstablishmentError(
                "security block required to be present in order to wrap handshake message"
            )

        # Determine security block type based on command/response and direction
        if msg.direction == OsdpMessageDirection.COMMAND:
            if msg.command_reply_code == CommandTags.CHLNG:
                msg.security_block.type = SecurityBlockType.SCS_11
            elif msg.command_reply_code == CommandTags.SCRYPT:
                msg.security_block.type = SecurityBlockType.SCS_13
        else:  # REPLY
            if msg.command_reply_code == ResponseTags.CCRYPT:
                msg.security_block.type = SecurityBlockType.SCS_12
            elif msg.command_reply_code == ResponseTags.RMAC_I:
                msg.security_block.type = SecurityBlockType.SCS_14

        # Set security block data based on SCBK mode
        if self.mode == ScbkMode.DEFAULT:
            # Default key mode: data = 0
            msg.security_block.data.value = bytearray([0])
            msg.security_block.data.num_bytes = 1
        else:  # ScbkMode.CUSTOM
            # Custom key mode: data = 1
            msg.security_block.data.value = bytearray([1])
            msg.security_block.data.num_bytes = 1

        # Update security block length to include the data byte
        msg.security_block.length = 2 + msg.security_block.data.num_bytes

        # Handshake messages don't require MAC during establishment
        msg.security_block.requires_mac = False

        return msg

    def unwrap_message(self, msg: OsdpMessage) -> OsdpMessage:
        """
        Unwrap a secure channel OSDP message by verifying MAC and decrypting data.

        :param msg: OSDP message to unwrap
        :return: Unwrapped OSDP message with decrypted data
        """
        # not a secure channel message
        if not msg.security_block:
            return msg

        # Handle secure channel handshake messages - no MAC verification needed
        if self._is_secure_channel_handshake_message(msg):
            return msg

        # For non-handshake messages, proceed with MAC verification and decryption

        # verify that MAC is present if security block type requires it
        if msg.security_block.requires_mac and not msg.mac:
            raise ValueError(
                f"MAC required for security block type {msg.security_block.type}"
            )

        # Do not attempt to unwrap encrypted message if sc state is not active
        if not self.state.is_active():
            raise IncompleteSetupError(
                "Cannot unwrap incoming encrypted message, SC not active"
            )

        icv: bytes
        maci: bytes

        if msg.direction == OsdpMessageDirection.COMMAND:
            if not self.rmac:
                raise ValueError("rmac required to unwrap secure channel command")

            icv = ones_complement(self.rmac)
            maci = self.rmac
        else:
            if not self.cmac:
                raise ValueError("cmac required to unwrap secure channel reply")

            icv = ones_complement(self.cmac)
            maci = self.cmac

        # verify the mac we calculate matches the one we received
        calc_mac = self.calc_mac(msg.get_mac_calc_bytes(), maci)
        if msg.mac != calc_mac[: OsdpMessage.MAC_LEN]:
            raise MacVerificationError(
                f"Mac in MSG: {msg.mac}, calculated: {calc_mac[:OsdpMessage.MAC_LEN]}"
            )

        if msg.security_block.type in [
            SecurityBlockType.SCS_17,
            SecurityBlockType.SCS_18,
        ]:
            msg.data = decrypt(self.senc, msg.data, icv[:AES_BLOCK_SIZE])

        # store the full calculated mac for the next cmd/reply
        if msg.direction == OsdpMessageDirection.COMMAND:
            self.cmac = calc_mac
        else:
            self.rmac = calc_mac

        return msg
