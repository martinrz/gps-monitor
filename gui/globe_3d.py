import math
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QDialog, QGridLayout
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from gps.data_models import SYSTEM_COLORS, SatelliteInfo

def _hex_to_rgba(hex_color: str, alpha: float = 1.0):
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    return [r, g, b, alpha]

try:
    import vispy
    vispy.use('PyQt6')
    from vispy import scene
    from vispy.scene import visuals
    VISPY_AVAILABLE = True
except Exception:
    VISPY_AVAILABLE = False

EARTH_RADIUS = 1.0
COAST_R = 1.0015
_DEFAULT_LAT = 51.5074
_DEFAULT_LON = -0.1278

# Approximate orbital inclinations used to tilt the ring visual for each system
_SYSTEM_INCLINATIONS = {
    'GPS':      55.0,
    'GLONASS':  64.8,
    'GALILEO':  56.0,
    'BEIDOU':   55.5,
    'QZSS':     43.0,
    'IRIDIUM':  86.4,
    'STARLINK': 53.0,
    'ONEWEB':   87.5,
    'STATIONS': 51.6,
    'NAVIC':    29.0,
}


def _make_ring_verts(radius: float, inclination_deg: float, n: int = 360) -> np.ndarray:
    """Circle of n points at the given radius, tilted by inclination_deg around the X-axis."""
    t = np.linspace(0, 2 * np.pi, n, endpoint=True)
    x = radius * np.cos(t)
    y = radius * np.sin(t)
    inc = math.radians(inclination_deg)
    ci, si = math.cos(inc), math.sin(inc)
    # Rotate (x, y, 0) around X: y' = y*cos - 0*sin, z' = y*sin + 0*cos
    return np.column_stack([x, y * ci, y * si]).astype(np.float32)


def _vis_radius(alt_km) -> float:
    if alt_km is None or alt_km < 2_000:
        return 1.12
    if alt_km < 30_000:
        return 1.80
    return 2.25


def _obs_pos(lat_deg: float, lon_deg: float) -> np.ndarray:
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    r = EARTH_RADIUS * 1.006
    return np.array([[r * math.cos(lat) * math.cos(lon),
                      r * math.cos(lat) * math.sin(lon),
                      r * math.sin(lat)]], dtype=np.float32)


def _angular_dist(lat1, lon1, lat2, lon2) -> float:
    """Great-circle angular distance in degrees (fast haversine)."""
    la1, lo1, la2, lo2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = la2 - la1
    dlon = lo2 - lo1
    a = math.sin(dlat/2)**2 + math.cos(la1)*math.cos(la2)*math.sin(dlon/2)**2
    return math.degrees(2 * math.asin(min(1.0, math.sqrt(a))))


def _build_coastlines():
    try:
        import cartopy.io.shapereader as shpreader
        from shapely.geometry import LineString
    except ImportError:
        return None

    shpfile = shpreader.natural_earth(resolution='110m', category='physical', name='coastline')
    reader = shpreader.Reader(shpfile)
    chunks = []
    nan_row = np.full((1, 3), np.nan, dtype=np.float32)
    for record in reader.records():
        geom = record.geometry
        segments = [geom] if isinstance(geom, LineString) else list(geom.geoms)
        for seg in segments:
            coords = np.asarray(seg.coords, dtype=np.float64)
            lons = np.radians(coords[:, 0])
            lats = np.radians(coords[:, 1])
            x = COAST_R * np.cos(lats) * np.cos(lons)
            y = COAST_R * np.cos(lats) * np.sin(lons)
            z = COAST_R * np.sin(lats)
            chunks.append(np.column_stack([x, y, z]).astype(np.float32))
            chunks.append(nan_row)
    return np.vstack(chunks) if chunks else None


def _build_graticule(spacing_deg=30):
    t = np.linspace(-np.pi, np.pi, 256)
    chunks = []
    nan_row = np.full((1, 3), np.nan, dtype=np.float32)
    r = EARTH_RADIUS * 1.0005

    for lat_deg in range(-90 + spacing_deg, 90, spacing_deg):
        lat = np.radians(lat_deg)
        cl = np.cos(lat) * r
        sl = np.sin(lat) * r
        verts = np.column_stack([cl * np.cos(t), cl * np.sin(t),
                                 np.full(len(t), sl)]).astype(np.float32)
        chunks += [verts, nan_row]

    t2 = np.linspace(-np.pi / 2, np.pi / 2, 128)
    for lon_deg in range(-180, 180, spacing_deg):
        lon = np.radians(lon_deg)
        verts = np.column_stack([r * np.cos(t2) * np.cos(lon),
                                 r * np.cos(t2) * np.sin(lon),
                                 r * np.sin(t2)]).astype(np.float32)
        chunks += [verts, nan_row]

    return np.vstack(chunks) if chunks else None


def _make_earth_texture():
    """Generate a 2048×1024 RGBA earth texture using cartopy. Cached after first call."""
    try:
        import cartopy.feature as cfeature
        import cartopy.crs as ccrs
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg

        W, H = 2048, 1024
        fig = Figure(figsize=(W / 100, H / 100), dpi=100)
        FigureCanvasAgg(fig)
        ax = fig.add_axes([0, 0, 1, 1], projection=ccrs.PlateCarree())
        ax.set_global()
        ax.set_axis_off()
        fig.patch.set_facecolor('#0d2040')
        ax.add_feature(cfeature.OCEAN,     color='#0d2040', zorder=0)
        ax.add_feature(cfeature.LAND,      color='#1e4a1e', zorder=1)
        ax.add_feature(cfeature.LAKES,     color='#0d2040', zorder=2)
        ax.add_feature(cfeature.BORDERS,   color='#445544', linewidth=0.5, zorder=3)
        ax.add_feature(cfeature.COASTLINE, color='#44aa44', linewidth=0.8, zorder=4)
        fig.canvas.draw()
        buf = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8).copy()
        return buf.reshape(H, W, 4)
    except Exception:
        return None


class Globe3DWidget(QWidget):
    observer_moved     = pyqtSignal(float, float)  # lat, lon
    satellite_selected = pyqtSignal(object)        # SatelliteInfo
    satellite_hovered  = pyqtSignal(object)        # SatelliteInfo or None

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._obs_lat = _DEFAULT_LAT
        self._obs_lon = _DEFAULT_LON
        self._dragging_obs = False
        self._terrain_enabled = False
        self._terrain_texture = None   # cached numpy array
        self._terrain_mesh   = None    # VisPy mesh visual
        self._current_satellites: list = []
        self._current_positions: list  = []
        self._last_hovered = None
        self._rings_enabled = False
        self._orbits_only   = False
        self._pixel_mode    = False
        self._orbit_rings: list = []
        self._ring_systems: frozenset = frozenset()

        if not VISPY_AVAILABLE:
            lbl = QLabel("VisPy not available.\nInstall with: pip install vispy")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #aaaaaa; font-size: 14px;")
            layout.addWidget(lbl)
            self._vispy_ok = False
            return

        self._vispy_ok = True
        self._canvas = scene.SceneCanvas(keys='interactive', bgcolor='#060610', show=False)
        self._view = self._canvas.central_widget.add_view()
        self._view.camera = scene.TurntableCamera(
            elevation=20, azimuth=30, distance=4.5, fov=40
        )

        # Ocean sphere
        self._earth = visuals.Sphere(
            radius=EARTH_RADIUS, method='latitude', rows=64, cols=128,
            color=(0.04, 0.12, 0.32, 0.18),
            parent=self._view.scene
        )
        self._earth.set_gl_state('translucent', depth_test=True, cull_face=False)

        # Graticule
        grat = _build_graticule(30)
        if grat is not None:
            visuals.Line(grat, color=(0.2, 0.35, 0.65, 0.2),
                         width=0.5, connect='strip', parent=self._view.scene)

        # Equator
        t = np.linspace(0, 2 * np.pi, 512)
        r = EARTH_RADIUS * 1.0005
        eq = np.column_stack([np.cos(t) * r, np.sin(t) * r,
                               np.zeros(512)]).astype(np.float32)
        visuals.Line(eq, color=(0.3, 0.55, 1.0, 0.5),
                     width=1.0, connect='strip', parent=self._view.scene)

        # Coastlines
        coast = _build_coastlines()
        if coast is not None:
            cv = visuals.Line(coast, color=(0.45, 0.72, 0.45, 0.9),
                              width=1.0, connect='strip', parent=self._view.scene)
            cv.set_gl_state(depth_test=True)

        # Satellite markers
        self._sat_visual = visuals.Markers(parent=self._view.scene)
        self._sat_visual.set_gl_state('translucent', depth_test=False)

        # Observer marker (yellow star)
        self._obs_marker = visuals.Markers(parent=self._view.scene)
        self._obs_marker.set_gl_state('translucent', depth_test=False)
        self._update_obs_marker()

        # Mouse events
        self._canvas.events.mouse_press.connect(self._on_mouse_press)
        self._canvas.events.mouse_move.connect(self._on_mouse_move)
        self._canvas.events.mouse_release.connect(self._on_mouse_release)
        self._canvas.events.mouse_double_click.connect(self._on_double_click)

        layout.addWidget(self._canvas.native)

    # ------------------------------------------------------------------
    # Observer marker
    # ------------------------------------------------------------------

    def _update_obs_marker(self):
        pos = _obs_pos(self._obs_lat, self._obs_lon)
        self._obs_marker.set_data(pos,
                                   face_color=[[1.0, 0.9, 0.1, 1.0]],
                                   edge_color=[[1.0, 1.0, 1.0, 0.9]],
                                   size=14, edge_width=1.5,
                                   symbol='star')
        if self._vispy_ok:
            self._canvas.update()

    def set_observer(self, lat: float, lon: float):
        self._obs_lat = lat
        self._obs_lon = lon
        self._update_obs_marker()

    # ------------------------------------------------------------------
    # Screen ↔ sphere helpers
    # ------------------------------------------------------------------

    def _screen_to_sphere(self, x: float, y: float):
        """Return (lat_deg, lon_deg) for screen pixel (x, y), or None if ray misses."""
        W, H = self._canvas.physical_size
        if W == 0 or H == 0:
            return None
        cam = self._view.camera
        az  = math.radians(cam.azimuth)
        el  = math.radians(cam.elevation)
        d   = float(cam.distance)
        fov = math.radians(float(cam.fov))

        eye = np.array([d * math.cos(el) * math.sin(az),
                        d * math.cos(el) * math.cos(az),
                        d * math.sin(el)])
        fwd = -eye / np.linalg.norm(eye)
        world_up = np.array([0.0, 0.0, 1.0])
        right = np.cross(fwd, world_up)
        if np.linalg.norm(right) < 1e-8:
            right = np.array([1.0, 0.0, 0.0])
        else:
            right /= np.linalg.norm(right)
        up = np.cross(right, fwd)
        up /= np.linalg.norm(up)

        ht     = math.tan(fov / 2)
        aspect = W / H
        nx     = (2 * x / W - 1) * ht * aspect
        ny     = -(2 * y / H - 1) * ht

        ray_d = fwd + nx * right + ny * up
        ray_d /= np.linalg.norm(ray_d)

        b    = 2 * float(np.dot(eye, ray_d))
        c    = float(np.dot(eye, eye)) - EARTH_RADIUS ** 2
        disc = b * b - 4 * c
        if disc < 0:
            return None
        t = (-b - math.sqrt(disc)) / 2
        if t < 0:
            return None
        hit = eye + t * ray_d
        lat = math.degrees(math.asin(max(-1.0, min(1.0, float(hit[2]) / EARTH_RADIUS))))
        lon = math.degrees(math.atan2(float(hit[1]), float(hit[0])))
        return lat, lon

    def _obs_screen_pos(self):
        """Return pixel (x, y) of the observer marker, or None."""
        try:
            pos3 = _obs_pos(self._obs_lat, self._obs_lon)[0]
            tr = self._obs_marker.transforms.get_transform('visual', 'canvas')
            sc = tr.map(list(pos3) + [1.0])
            if abs(sc[3]) < 1e-8:
                return None
            return sc[0] / sc[3], sc[1] / sc[3]
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Mouse event handlers
    # ------------------------------------------------------------------

    def _on_mouse_press(self, event):
        # Right-click (button=2) near observer → start drag
        if event.button == 2:
            sp = self._obs_screen_pos()
            if sp is not None:
                dx, dy = event.pos[0] - sp[0], event.pos[1] - sp[1]
                if math.sqrt(dx*dx + dy*dy) < 24:
                    self._dragging_obs = True
                    event.handled = True

    def _on_mouse_move(self, event):
        if self._dragging_obs and event.buttons:
            result = self._screen_to_sphere(event.pos[0], event.pos[1])
            if result is not None:
                self._obs_lat, self._obs_lon = result
                self._update_obs_marker()
            event.handled = True
            return
        self._detect_hover(event.pos[0], event.pos[1])

    def _detect_hover(self, x: float, y: float):
        if not self._current_satellites or not self._vispy_ok:
            if self._last_hovered is not None:
                self._last_hovered = None
                self.satellite_hovered.emit(None)
            return
        try:
            tr   = self._sat_visual.transforms.get_transform('visual', 'canvas')
            pos  = np.array(self._current_positions, dtype=np.float32)  # (N, 3)
            pos4 = np.column_stack([pos, np.ones(len(pos), dtype=np.float32)])
            sc   = tr.map(pos4)                                          # (N, 4)
            # Satellites behind the camera have w ≤ 0; exclude them
            front = sc[:, 3] > 0
            if not np.any(front):
                hovered = None
            else:
                sx    = sc[front, 0] / sc[front, 3]
                sy    = sc[front, 1] / sc[front, 3]
                dists = np.sqrt((sx - x) ** 2 + (sy - y) ** 2)
                near  = int(np.argmin(dists))
                idx   = int(np.where(front)[0][near])
                hovered = self._current_satellites[idx] if dists[near] < 12 else None
        except Exception:
            hovered = None
        if hovered is not self._last_hovered:
            self._last_hovered = hovered
            self.satellite_hovered.emit(hovered)

    def _on_mouse_release(self, event):
        if self._dragging_obs:
            self._dragging_obs = False
            self.observer_moved.emit(self._obs_lat, self._obs_lon)
            event.handled = True

    def _on_double_click(self, event):
        result = self._screen_to_sphere(event.pos[0], event.pos[1])
        if result is None or not self._current_satellites:
            return
        click_lat, click_lon = result
        best, best_dist = None, 999.0
        for sat in self._current_satellites:
            if sat.sat_lat is None:
                continue
            d = _angular_dist(click_lat, click_lon, sat.sat_lat, sat.sat_lon)
            if d < best_dist:
                best_dist, best = d, sat
        if best and best_dist < 3.5:
            self.satellite_selected.emit(best)

    # ------------------------------------------------------------------
    # Satellite update
    # ------------------------------------------------------------------

    def update_satellites(self, satellites: list):
        if not self._vispy_ok:
            return
        if not satellites:
            self._sat_visual.set_data(
                np.zeros((1, 3), dtype=np.float32),
                face_color=[[0, 0, 0, 0]], edge_color=[[0, 0, 0, 0]], size=0.001
            )
            self._current_satellites = []
            self._current_positions  = []
            self._canvas.update()
            self._update_orbit_rings([])
            return

        positions = []
        colors    = []

        for sat in satellites:
            r = _vis_radius(sat.altitude_km)
            if sat.sat_lat is not None and sat.sat_lon is not None:
                lat = math.radians(sat.sat_lat)
                lon = math.radians(sat.sat_lon)
                x = r * math.cos(lat) * math.cos(lon)
                y = r * math.cos(lat) * math.sin(lon)
                z = r * math.sin(lat)
            else:
                az = math.radians(sat.azimuth)
                el = math.radians(sat.elevation)
                x  = r * math.cos(el) * math.sin(az)
                y  = r * math.cos(el) * math.cos(az)
                z  = r * math.sin(el)
            positions.append([x, y, z])

            hex_c = SYSTEM_COLORS.get(sat.system, '#888888')
            if sat.elevation > 0 and sat.snr >= 25:
                colors.append(_hex_to_rgba(hex_c, 1.0))
            elif sat.elevation > 0:
                colors.append(_hex_to_rgba(hex_c, 0.65))
            else:
                colors.append(_hex_to_rgba(hex_c, 0.22))

        self._current_satellites = list(satellites)
        self._current_positions  = list(positions)

        pos = np.array(positions, dtype=np.float32)
        col = np.array(colors,    dtype=np.float32)
        if self._pixel_mode:
            col[:, 3] = 1.0
            self._sat_visual.set_data(pos, face_color=col, edge_color=col,
                                      size=2, edge_width=0, symbol='square')
        else:
            self._sat_visual.set_data(pos, face_color=col, edge_color=col,
                                      size=9, edge_width=0.5)
        self._canvas.update()
        self._update_orbit_rings(satellites)

    def apply_prepared(self, positions: np.ndarray, colors: np.ndarray, satellites: list):
        """Fast path: apply pre-computed arrays from DisplayWorker (no per-sat loop)."""
        if not self._vispy_ok:
            return
        self._current_satellites = list(satellites)
        self._current_positions  = positions          # keep as ndarray for hover projection
        if len(satellites) == 0:
            self._sat_visual.set_data(
                np.zeros((1, 3), dtype=np.float32),
                face_color=[[0, 0, 0, 0]], edge_color=[[0, 0, 0, 0]], size=0.001
            )
        elif self._pixel_mode:
            bright = colors.copy()
            bright[:, 3] = 1.0          # force full alpha on every dot
            self._sat_visual.set_data(positions, face_color=bright, edge_color=bright,
                                      size=2, edge_width=0, symbol='square')
        else:
            self._sat_visual.set_data(positions, face_color=colors, edge_color=colors,
                                      size=9, edge_width=0.5)
        self._canvas.update()
        self._update_orbit_rings(satellites)

    # ------------------------------------------------------------------
    # Orbital rings
    # ------------------------------------------------------------------

    def toggle_orbit_rings(self):
        if not self._vispy_ok:
            return
        self._rings_enabled = not self._rings_enabled
        if self._rings_enabled:
            self._ring_systems = frozenset()   # force rebuild
            self._rebuild_orbit_rings(self._current_satellites)
        else:
            for ring in self._orbit_rings:
                ring.parent = None
            self._orbit_rings.clear()
            self._ring_systems = frozenset()
            self._canvas.update()

    def toggle_orbits_only(self):
        """Show orbital rings and hide satellite dots, or restore dots."""
        if not self._vispy_ok:
            return
        self._orbits_only = not self._orbits_only
        if self._orbits_only:
            self._sat_visual.visible = False
            if not self._rings_enabled:
                self._rings_enabled = True
                self._ring_systems = frozenset()
                self._rebuild_orbit_rings(self._current_satellites)
        else:
            self._sat_visual.visible = True
            if not self._rings_enabled:
                for ring in self._orbit_rings:
                    ring.parent = None
                self._orbit_rings.clear()
                self._ring_systems = frozenset()
        self._canvas.update()

    def toggle_pixel_mode(self):
        """Switch satellite markers between normal dots and bright 2-px squares."""
        if not self._vispy_ok:
            return
        self._pixel_mode = not self._pixel_mode
        # Re-render with current data so the change is immediate
        if self._current_positions is not None and len(self._current_satellites):
            pos = (self._current_positions if isinstance(self._current_positions, np.ndarray)
                   else np.array(self._current_positions, dtype=np.float32))
            # Rebuild colors from current satellite list
            colors = []
            for sat in self._current_satellites:
                hex_c = SYSTEM_COLORS.get(sat.system, '#888888')
                if sat.elevation > 0 and sat.snr >= 25:
                    colors.append(_hex_to_rgba(hex_c, 1.0))
                elif sat.elevation > 0:
                    colors.append(_hex_to_rgba(hex_c, 0.65))
                else:
                    colors.append(_hex_to_rgba(hex_c, 0.22))
            col = np.array(colors, dtype=np.float32)
            if self._pixel_mode:
                col[:, 3] = 1.0
                self._sat_visual.set_data(pos, face_color=col, edge_color=col,
                                          size=2, edge_width=0, symbol='square')
            else:
                self._sat_visual.set_data(pos, face_color=col, edge_color=col,
                                          size=9, edge_width=0.5)
            self._canvas.update()

    def _update_orbit_rings(self, satellites: list):
        if not self._rings_enabled:
            return
        new_systems = frozenset(s.system for s in satellites)
        if new_systems == self._ring_systems:
            return
        self._ring_systems = new_systems
        self._rebuild_orbit_rings(satellites)

    def _rebuild_orbit_rings(self, satellites: list):
        for ring in self._orbit_rings:
            ring.parent = None
        self._orbit_rings.clear()
        seen: set = set()
        for sat in satellites:
            if sat.system in seen:
                continue
            seen.add(sat.system)
            radius = _vis_radius(sat.altitude_km)
            incl = _SYSTEM_INCLINATIONS.get(sat.system, 56.0)
            rgba = _hex_to_rgba(SYSTEM_COLORS.get(sat.system, '#888888'), 0.45)
            verts = _make_ring_verts(radius, incl)
            ring = visuals.Line(verts, color=rgba, width=1.5, connect='strip',
                                parent=self._view.scene)
            ring.set_gl_state(depth_test=False)
            self._orbit_rings.append(ring)
        self._canvas.update()

    # ------------------------------------------------------------------
    # Terrain toggle
    # ------------------------------------------------------------------

    def toggle_terrain(self):
        if not self._vispy_ok:
            return
        self._terrain_enabled = not self._terrain_enabled
        if self._terrain_enabled:
            self._enable_terrain()
        else:
            self._disable_terrain()

    def _enable_terrain(self):
        if self._terrain_texture is None:
            self._terrain_texture = _make_earth_texture()
        if self._terrain_texture is None:
            self._terrain_enabled = False
            return

        try:
            from vispy.geometry import create_sphere
            from vispy.visuals.filters import TextureFilter

            mesh_data = create_sphere(cols=128, rows=64, method='latitude',
                                      radius=EARTH_RADIUS * 0.9995)

            # Compute UV texture coordinates from vertex spherical positions.
            # v=0 is south pole in OpenGL convention; image row-0 is north, so flip Y.
            verts = mesh_data.get_vertices()
            r = np.sqrt(np.sum(verts ** 2, axis=1))
            lat = np.arcsin(np.clip(verts[:, 2] / r, -1.0, 1.0))
            lon = np.arctan2(verts[:, 1], verts[:, 0])
            u = ((lon + math.pi) / (2 * math.pi)).astype(np.float32)
            v = ((lat + math.pi / 2) / math.pi).astype(np.float32)
            texcoords = np.column_stack([u, v])

            self._terrain_mesh = visuals.Mesh(
                meshdata=mesh_data,
                shading=None,
                parent=self._view.scene
            )
            tex_filter = TextureFilter(
                texture=self._terrain_texture[::-1],  # flip Y: row-0 → south pole
                texcoords=texcoords,
            )
            self._terrain_mesh.attach(tex_filter)
            self._terrain_mesh.set_gl_state(depth_test=True, cull_face=False)
            self._earth.visible = False
            # Re-parent marker visuals to end of scene children so they render
            # after the terrain mesh and are never painted over by it.
            self._sat_visual.parent = None
            self._sat_visual.parent = self._view.scene
            self._obs_marker.parent = None
            self._obs_marker.parent = self._view.scene
        except Exception:
            self._terrain_mesh = None
            self._terrain_enabled = False
            self._earth.visible = True
        self._canvas.update()

    def _disable_terrain(self):
        if self._terrain_mesh is not None:
            self._terrain_mesh.parent = None
            self._terrain_mesh = None
        self._earth.visible = True
        self._canvas.update()
