"""Recorded live packet fixtures captured from AK001-ZJ21413 (10.0.0.207 & IOTWFC00)."""

# Live UDP 48899 discovery reply from 10.0.0.207
FIXTURE_UDP_DISCOVERY = (
    "10.0.0.207,B4E842A7FC00,AK001-ZJ21413,6ed63336bc9a4c49b38792dbbd68fdbb"
)

# Live BLE 0x5A01 service data advertisement from IOTWFC00
FIXTURE_BLE_5A01_HEX = "5207b4e842a7fc00006b1e090102"

# Live Wi-Fi TCP 5577 state query TX (seq=0) and EA 81 RX (38 bytes wired)
FIXTURE_TCP_STATE_QUERY_TX = bytes.fromhex("b0b1b2b3000102000003818a8b62")
FIXTURE_TCP_STATE_QUERY_RX = bytes.fromhex(
    "b0b1b2b300010200001bea8101006b0923251d32f03ad414ff000c0032ffffffff01000003aa"
)

# Live Wi-Fi TCP 5577 state response after E1 22 Green (60, 100, 100)
FIXTURE_TCP_STATE_GREEN_RX = bytes.fromhex(
    "b0b1b2b30001020e001bea8101006b0923240132f03c6464ff000c0032ffffffff010000037d"
)

# Live Wi-Fi TCP 5577 RTC time query RX (2026-11-18 12:17:21 Wed)
FIXTURE_TCP_TIME_RX = bytes.fromhex(
    "b0b1b2b300010201000c0f11141a0b120c11150300a016"
)

# Live Wi-Fi TCP 5577 Remote config query RX
FIXTURE_TCP_REMOTE_RX = bytes.fromhex(
    "b0b1b2b300010206000e2b03000100003c0000000000006bb3"
)

# Live BLE FF02 notification JSON response for E1 22 Blue 80%
FIXTURE_BLE_NOTIFY_BLUE80 = (
    bytes.fromhex("04028000004d4e0a")
    + b'{"code":0,"payload":"EA8101006B0923240164F0786450FF000C0032FFFFFFFF01000003"}'
)
