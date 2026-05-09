import numpy as np

MU = 3.986004418e14     # Earth gravitational parameter, m^3/s^2
EARTH_RADIUS = 6_378_137.0  # WGS-84 semi-major axis, m
EARTH_F = 1.0 / 298.257223563   # WGS-84 flattening
EARTH_B = EARTH_RADIUS * (1.0 - EARTH_F)
OMEGA_E = 7.2921150e-5  # Earth rotation rate, rad/s


def keplerian_to_ecef(semi_major_axis: float, eccentricity: float,
                      inclination_deg: float, raan_deg: float,
                      arg_perigee_deg: float, mean_anomaly_deg: float,
                      gps_time_s: float) -> np.ndarray:
    """Convert Keplerian orbital elements to ECEF position (metres)."""
    n = np.sqrt(MU / semi_major_axis ** 3)          # mean motion
    M = np.radians(mean_anomaly_deg) + n * gps_time_s

    # Solve Kepler's equation via Newton-Raphson
    E = M
    for _ in range(50):
        dE = (M - E + eccentricity * np.sin(E)) / (1.0 - eccentricity * np.cos(E))
        E += dE
        if abs(dE) < 1e-12:
            break

    # True anomaly
    sin_nu = np.sqrt(1 - eccentricity ** 2) * np.sin(E) / (1 - eccentricity * np.cos(E))
    cos_nu = (np.cos(E) - eccentricity) / (1 - eccentricity * np.cos(E))
    nu = np.arctan2(sin_nu, cos_nu)

    # Orbital radius
    r = semi_major_axis * (1 - eccentricity * np.cos(E))

    # Position in orbital plane
    i = np.radians(inclination_deg)
    omega = np.radians(arg_perigee_deg)
    RAAN = np.radians(raan_deg) - OMEGA_E * gps_time_s   # account for Earth rotation

    u = omega + nu
    x_orb = r * np.cos(u)
    y_orb = r * np.sin(u)

    # Rotate to ECEF
    x = (x_orb * (np.cos(RAAN) * np.cos(omega) - np.sin(RAAN) * np.sin(omega) * np.cos(i))
         - y_orb * (np.cos(RAAN) * np.sin(omega) + np.sin(RAAN) * np.cos(omega) * np.cos(i)))
    y = (x_orb * (np.sin(RAAN) * np.cos(omega) + np.cos(RAAN) * np.sin(omega) * np.cos(i))
         + y_orb * (np.cos(RAAN) * np.cos(omega) * np.cos(i) - np.sin(RAAN) * np.sin(omega)))
    z = x_orb * np.sin(omega) * np.sin(i) + y_orb * np.cos(omega) * np.sin(i)

    return np.array([x, y, z])


def latlon_to_ecef(lat_deg: float, lon_deg: float, alt_m: float = 0.0) -> np.ndarray:
    """WGS-84 geodetic to ECEF."""
    lat = np.radians(lat_deg)
    lon = np.radians(lon_deg)
    e2 = 1 - (EARTH_B / EARTH_RADIUS) ** 2
    N = EARTH_RADIUS / np.sqrt(1 - e2 * np.sin(lat) ** 2)
    x = (N + alt_m) * np.cos(lat) * np.cos(lon)
    y = (N + alt_m) * np.cos(lat) * np.sin(lon)
    z = (N * (1 - e2) + alt_m) * np.sin(lat)
    return np.array([x, y, z])


def ecef_to_latlon(xyz: np.ndarray):
    """ECEF to WGS-84 geodetic (Bowring iterative). Returns (lat_deg, lon_deg, alt_m)."""
    x, y, z = xyz
    lon = np.arctan2(y, x)
    p = np.sqrt(x ** 2 + y ** 2)
    e2 = 1 - (EARTH_B / EARTH_RADIUS) ** 2
    lat = np.arctan2(z, p * (1 - e2))
    for _ in range(10):
        N = EARTH_RADIUS / np.sqrt(1 - e2 * np.sin(lat) ** 2)
        lat_new = np.arctan2(z + e2 * N * np.sin(lat), p)
        if abs(lat_new - lat) < 1e-12:
            lat = lat_new
            break
        lat = lat_new
    N = EARTH_RADIUS / np.sqrt(1 - e2 * np.sin(lat) ** 2)
    alt = p / np.cos(lat) - N if abs(np.cos(lat)) > 1e-10 else abs(z) / np.sin(lat) - N * (1 - e2)
    return np.degrees(lat), np.degrees(lon), alt


def ecef_to_azel(sat_ecef: np.ndarray, obs_ecef: np.ndarray,
                 obs_lat_deg: float, obs_lon_deg: float):
    """Compute azimuth and elevation from observer to satellite. Returns (az_deg, el_deg)."""
    diff = sat_ecef - obs_ecef
    lat = np.radians(obs_lat_deg)
    lon = np.radians(obs_lon_deg)

    # ENU rotation matrix
    east = np.array([-np.sin(lon), np.cos(lon), 0.0])
    north = np.array([-np.sin(lat) * np.cos(lon), -np.sin(lat) * np.sin(lon), np.cos(lat)])
    up = np.array([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])

    e = np.dot(diff, east)
    n = np.dot(diff, north)
    u = np.dot(diff, up)

    az = np.degrees(np.arctan2(e, n)) % 360
    el = np.degrees(np.arctan2(u, np.sqrt(e ** 2 + n ** 2)))
    return az, el
