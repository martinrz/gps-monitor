# time_module/ntp_client.py

`NTPClient(QObject)` — queries multiple NTP servers in parallel and emits a weighted time estimate. Runs on a dedicated `QThread`.

## Signals

| Signal | Payload |
|--------|---------|
| `time_updated` | `TimeEstimate` |
| `status_changed` | `str` |

## Servers Queried

`pool.ntp.org`, `time.google.com`, `time.cloudflare.com`, `time.windows.com`, `ntp.ubuntu.com`, `time1/2/3.google.com` — 8 servers in total.

## Algorithm

1. All 8 servers queried concurrently via `ThreadPoolExecutor` (timeout 5 s).
2. Responses with `delay ≥ 10 s` or errors are discarded.
3. **Outlier rejection**: if ≥ 3 results, discard those where `|offset − median| > 2σ`.
4. **Weighted average**: weights = `1/delay²`; final offset = `Σ(weight × offset) / Σ(weight)`.
5. **Uncertainty**: weighted standard deviation of offsets, floored at 1 μs.
6. Emits `TimeEstimate` with `utc_time = time.time() + weighted_offset`.

## Update Interval

Queries every `QUERY_INTERVAL = 30` seconds. Sleep is broken into 0.1 s increments so `stop()` is responsive.

## GPS-NTP Offset

If `set_gps_time(gps_unix)` has been called, the offset `(projected_GPS_time − ntp_time) × 1000` is included in the estimate as `gps_offset_ms`. Currently `set_gps_time()` is not called by any live code path; the field is always `None`.
