"""Verified system commands: power, state, time, and remote config queries."""

from __future__ import annotations

from controller.protocol.constants import (
    CMD_POWER_OFF,
    CMD_POWER_ON,
    CMD_REMOTE_QUERY,
    CMD_STATE_QUERY,
    CMD_TIME_QUERY,
)
from controller.protocol.encoder.tunnel import append_inner_checksum


def build_state_query(include_inner_checksum: bool = False) -> bytes:
    """Build the 0x81 0x8A 0x8B state query payload."""
    return append_inner_checksum(CMD_STATE_QUERY) if include_inner_checksum else CMD_STATE_QUERY


def build_power_command(turn_on: bool, include_inner_checksum: bool = False) -> bytes:
    """Build the 0x71 0x23/0x24 0x0F power command payload."""
    cmd = CMD_POWER_ON if turn_on else CMD_POWER_OFF
    return append_inner_checksum(cmd) if include_inner_checksum else cmd


def build_time_query(include_inner_checksum: bool = False) -> bytes:
    """Build the 0x11 0x1A 0x1B 0x0F RTC time query payload."""
    return append_inner_checksum(CMD_TIME_QUERY) if include_inner_checksum else CMD_TIME_QUERY


def build_remote_config_query() -> bytes:
    """Build the 0x2B 0x2C 0x2D remote config query payload."""
    return CMD_REMOTE_QUERY
