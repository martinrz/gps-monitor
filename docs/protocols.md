# gps/protocols/

Three parsers translate hardware byte streams into `GPSData` objects. All are stateful — call `feed()` or `feed_bytes()` repeatedly as data arrives.

---

## nmea.py — `NMEAParser`

Parses ASCII NMEA 0183 sentences via `pynmea2`.

### `feed(line: str) -> GPSData | None`

Returns `GPSData` after any fix sentence (GGA, RMC, GNS, GSA, ZDA). Returns `None` after a GSV sentence (buffered until the full multi-message group arrives, then flushes).

### Sentence Handling

| Sentence | Action |
|----------|--------|
| GGA / RMC / GNS | Extracts lat/lon/alt/speed/heading/fix quality |
| GSA | Updates DOP values; marks `used_in_fix` for listed PRNs |
| GSV | Buffered by `(talker, total_msgs)` key; flushed when the last message of a group arrives |
| ZDA | Extracts UTC date |

### Talker → System Mapping

`GP → GPS`, `GL → GLONASS`, `GA → GALILEO`, `GB → BEIDOU`, `GN → GPS` (multi-constellation combined).

---

## ubx.py — `UBXParser`

Parses u-blox UBX binary protocol via `pyubx2`.

### `feed_bytes(raw: bytes) -> GPSData | None`

Parses a single message from the raw bytes. Returns `GPSData` on `NAV-PVT`; updates the internal satellite list on `NAV-SAT`; returns `None` for all other messages.

### Message Handling

| Message | Action |
|---------|--------|
| `NAV-PVT` | Lat/lon/alt (×10⁻⁷ / ×10⁻³), speed (×10⁻³ m/s), heading (×10⁻⁵°), time |
| `NAV-SAT` | Satellite list: gnssId, svId, C/N₀, elevation, azimuth, `flags & 0x08` = used |

### GNSS ID Map

`0=GPS, 1=SBAS, 2=GALILEO, 3=BEIDOU, 5=QZSS, 6=GLONASS`

---

## sirf.py — `SiRFParser`

State-machine binary parser for SiRF III (binary) protocol.

### Frame Format

`A0 A2 | len_hi len_lo | payload[len] | cs_hi cs_lo | B0 B3`

15-bit additive checksum over the payload.

### `feed_bytes(data: bytes) -> list[GPSData]`

Returns a list (possibly empty) of `GPSData` objects completed during this call.

### Message Handling

| Message ID | Action |
|------------|--------|
| `0x29` (41) — Geodetic Nav | Lat (×10⁻⁷°), lon (×10⁻⁷°), alt (×10⁻² m), speed (×10⁻² m/s), heading (×10⁻² °), fix validity from `nav_valid & 0x01` |
| `0x04` — Measured Tracker | Up to 12 channels: svid, azimuth (×360/1024°), elevation, C/N₀ (average of 8 bytes), state bit 0 = used |
