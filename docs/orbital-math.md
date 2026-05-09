# utils/orbital_math.py

WGS-84 geodetic constants and coordinate transform functions. Pure maths — no side effects.

## Constants

| Name | Value | Description |
|------|-------|-------------|
| `MU` | 3.986004418 × 10¹⁴ m³/s² | Earth gravitational parameter |
| `EARTH_RADIUS` | 6,378,137.0 m | WGS-84 semi-major axis |
| `EARTH_F` | 1/298.257223563 | WGS-84 flattening |
| `EARTH_B` | `EARTH_RADIUS × (1 − F)` | Semi-minor axis |
| `OMEGA_E` | 7.2921150 × 10⁻⁵ rad/s | Earth rotation rate |

## Functions

### `keplerian_to_ecef(sma, ecc, inc, raan, ap, ma, gps_time_s) → ndarray(3)`

Converts Keplerian orbital elements to ECEF position in metres.

1. Compute mean motion `n = √(MU/a³)`.
2. Propagate mean anomaly: `M = M₀ + n·t`.
3. Solve Kepler's equation `M = E − e·sin(E)` via Newton-Raphson (50 iterations max, convergence at < 10⁻¹² rad).
4. Compute true anomaly ν from eccentric anomaly E.
5. Rotate to ECEF using inclination, RAAN (adjusted for Earth rotation: `RAAN − Ω_E·t`), and argument of perigee.

### `latlon_to_ecef(lat_deg, lon_deg, alt_m=0) → ndarray(3)`

WGS-84 geodetic → ECEF. Uses the prime vertical radius of curvature N.

### `ecef_to_latlon(xyz) → (lat_deg, lon_deg, alt_m)`

ECEF → WGS-84 geodetic via Bowring iterative method (10 iterations, convergence at < 10⁻¹² rad). Handles polar singularity.

### `ecef_to_azel(sat_ecef, obs_ecef, obs_lat, obs_lon) → (az_deg, el_deg)`

Compute azimuth and elevation from observer to satellite using the East-North-Up (ENU) rotation matrix.  
Returns azimuth in [0°, 360°) and elevation in [−90°, 90°].
