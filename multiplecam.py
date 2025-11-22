#!/usr/bin/env python3
"""
Dynamic camera layout per group by area
- Cameras with the same 'area' are grouped into one window.
- Layout adapts to number of cameras:
  - 1: Full screen
  - 2: Uses 4-cam 2x2 grid (2 cams, 2 black tiles)
  - 3: Uses 4-cam 2x2 grid (3 cams, 1 black tile)
  - 4: 2x2 grid, each cam 1/4 screen
  - 5-6: 3x3 grid (first 2x2 top-left, others 1x1)
- No pixel gaps using compute_boundaries
- Ctrl+F toggles fullscreen
- Displays connection status on overlay with orange text and transparent background
- Displays current time at top center of window

Requirements:
    pip install PyQt6 python-vlc
"""
import sys
import os
import time
import json
from PyQt6 import QtWidgets, QtCore
from datetime import datetime

# Add DLL directory for libvlc
base_path = os.path.dirname(os.path.abspath(__file__))
os.add_dll_directory(base_path)
import vlc

# ---------- Configuration ----------
CAMERA_JSON_FILE = os.path.join(base_path, "camera.json")
VLC_OPTS = (
    ":network-caching=0 :live-caching=0 :file-caching=0 :disc-caching=0 :drop-late-frames :skip-frames"
)

# ---------- Fallback camera list (used if JSON file is not found) ----------
DEFAULT_CAM_LIST = [
    {"url": "rtsp://192.168.22.3:8564/bbox/f4ebc728df05346e7d2f785b", "area": "KHU VỰC BUỒNG GIAM", "name": "A11", "camera_id": "f4ebc728df05346e7d2f785b"},
    {"url": "rtsp://192.168.22.3:8564/bbox/0b92b8b2602c011d1831c6c2", "area": "KHU VỰC BUỒNG GIAM", "name": "A12", "camera_id": "0b92b8b2602c011d1831c6c2"},
    {"url": "rtsp://192.168.22.3:8564/bbox/f35b705e8c57ae59e369ebc9", "area": "KHU VỰC BUỒNG GIAM", "name": "A13", "camera_id": "f35b705e8c57ae59e369ebc9"},
    {"url": "rtsp://192.168.22.3:8564/bbox/43ba9900ff2fc7d9d3207254", "area": "KHU VỰC BUỒNG GIAM", "name": "A14", "camera_id": "43ba9900ff2fc7d9d3207254"},
    {"url": "rtsp://192.168.22.3:8564/bbox/c064aa5670a62419ecc714e0", "area": "KHU VỰC HÀNG RÀO", "name": "B11", "camera_id": "c064aa5670a62419ecc714e0"}, 
    {"url": "rtsp://192.168.22.3:8564/bbox/8acfe827853aff5217d7ef21", "area": "KHU VỰC HÀNG RÀO", "name": "B12", "camera_id": "8acfe827853aff5217d7ef21"},    
    {"url": "rtsp://192.168.22.3:8564/bbox/5a90dccf0259cc883dd91c7a", "area": "KHU VỰC KSAN", "name": "C21", "camera_id": "5a90dccf0259cc883dd91c7a"},
    {"url": "rtsp://192.168.22.3:8564/bbox/f1c9d16d7f35450ac3171d20", "area": "KHU VỰC KSAN", "name": "C22", "camera_id": "f1c9d16d7f35450ac3171d20"},
    {"url": "rtsp://192.168.22.3:8564/bbox/83567cd28bc5c1e1749a19fa", "area": "KHU VỰC KSAN", "name": "C23", "camera_id": "83567cd28bc5c1e1749a19fa"},
    {"url": "rtsp://192.168.22.3:8564/bbox/c0e3be4e63002c75ba05748a", "area": "KHU VỰC CỔNG TRẠI", "name": "D11", "camera_id": "c0e3be4e63002c75ba05748a"},
    {"url": "rtsp://192.168.22.3:8564/bbox/75b573a2a80f7d1f54f711b8", "area": "KHU VỰC CỔNG TRẠI", "name": "D12", "camera_id": "75b573a2a80f7d1f54f711b8"},
    {"url": "rtsp://192.168.22.3:8564/bbox/bc666a1cd3460379f3d05a2a", "area": "KHU VỰC CỔNG TRẠI", "name": "D13", "camera_id": "bc666a1cd3460379f3d05a2a"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.160:554/ch01", "area": "KHU VỰC CỔNG TRẠI", "name": "D14", "camera_id": "b8f3d30bf1c346e37d3cba37"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.150:554/ch01", "area": "KHU VỰC LAO ĐỘNG", "name": "E11", "camera_id": "e6a6a63057a146f86c6d0f94"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.162:554/ch01", "area": "KHU VỰC LAO ĐỘNG", "name": "E12", "camera_id": "084babdcdda0e2f987d9d505"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.163:554/ch01", "area": "KHU VỰC LAO ĐỘNG", "name": "E13", "camera_id": "7975566a25bafcc34f6109d3"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.158:554/ch01", "area": "KHU VỰC KIỂM SOÁT RA VÀO", "name": "F11", "camera_id": "643b0662422d1d0dffa3fca2"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.165:554/ch01", "area": "KHU VỰC KIỂM SOÁT RA VÀO", "name": "F12", "camera_id": "e902674982fc99aa343cdd94"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.156:554/ch01", "area": "KHU VỰC KIỂM SOÁT RA VÀO", "name": "F13", "camera_id": "95dfde4807d4d6a9eec49920"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.164:554/ch01", "area": "KHU VỰC KIỂM SOÁT RA VÀO", "name": "F14", "camera_id": "2468649b6215c4cdd2aef509"},  
]


# ---------- Helpers ----------
def load_cameras_from_json(json_file: str = None) -> list:
    """
    Load camera list from JSON file
    
    Args:
        json_file: Path to JSON file. If None, uses default CAMERA_JSON_FILE
    
    Returns:
        List of camera dictionaries. Returns DEFAULT_CAM_LIST if file not found or invalid.
    """
    if json_file is None:
        json_file = CAMERA_JSON_FILE
    
    try:
        if not os.path.exists(json_file):
            print(f"[WARN] Camera JSON file not found: {json_file}")
            print("[INFO] Using default camera list")
            return DEFAULT_CAM_LIST.copy()
        
        with open(json_file, 'r', encoding='utf-8') as f:
            cameras = json.load(f)
        
        # Validate structure
        if not isinstance(cameras, list):
            print(f"[ERROR] Invalid JSON structure: expected list, got {type(cameras)}")
            print("[INFO] Using default camera list")
            return DEFAULT_CAM_LIST.copy()
        
        # Validate each camera has required fields
        valid_cameras = []
        for idx, cam in enumerate(cameras):
            if not isinstance(cam, dict):
                print(f"[WARN] Skipping invalid camera at index {idx}: not a dictionary")
                continue
            if 'url' not in cam or 'area' not in cam:
                print(f"[WARN] Skipping invalid camera at index {idx}: missing 'url' or 'area'")
                continue
            valid_cameras.append(cam)
        
        if not valid_cameras:
            print("[ERROR] No valid cameras found in JSON file")
            print("[INFO] Using default camera list")
            return DEFAULT_CAM_LIST.copy()
        
        print(f"[INFO] Loaded {len(valid_cameras)} cameras from {json_file}")
        return valid_cameras
    
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse JSON file: {e}")
        print("[INFO] Using default camera list")
        return DEFAULT_CAM_LIST.copy()
    except Exception as e:
        print(f"[ERROR] Failed to load camera JSON file: {e}")
        print("[INFO] Using default camera list")
        return DEFAULT_CAM_LIST.copy()


def compute_boundaries(total_pixels: int, segments: int):
    """Return integer boundaries ensuring sum equals total_pixels."""
    return [int(round(i * total_pixels / segments)) for i in range(segments + 1)]

def set_player_window_for_platform(player: vlc.MediaPlayer, frame: QtWidgets.QFrame):
    try:
        winid = int(frame.winId())
        if sys.platform.startswith("linux"):
            player.set_xwindow(winid)
        elif sys.platform == "win32":
            player.set_hwnd(winid)
        elif sys.platform == "darwin":
            try:
                player.set_nsobject(winid)
            except Exception:
                player.set_nsobject(int(winid))
    except Exception as e:
        print("[WARN] set_player_window failed:", e)

# ---------- Custom layout window with dynamic tiling ----------
class CustomLayoutWindow(QtWidgets.QMainWindow):
    """
    Dynamic layout based on number of cameras:
    - 1: Full screen
    - 2: 2x2 grid (2 cams, 2 black tiles)
    - 3: 2x2 grid (3 cams, 1 black tile)
    - 4: 2x2 grid, each cam 1/4 screen
    - 5-6: 3x3 grid (first 2x2 top-left, others 1x1)
    """

    RECONNECT_INTERVAL = 5  # seconds

    def __init__(self, cams, vlc_instance: vlc.Instance, group_name: str, parent=None):
        super().__init__(parent)
        num_cams = len(cams)
        if num_cams > 6:
            print(f"[WARN] Group '{group_name}' has {num_cams} cams, limiting to 6")
            cams = cams[:6]
            num_cams = 6
        self.setWindowTitle(f"Camera Group: {group_name} ({num_cams} cams)")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(QtCore.Qt.WindowType.Window)
        self.cams = cams
        self.vlc_instance = vlc_instance
        self.frames = []  # list of (frame, label, cam) or (frame, None, None) for black tile
        self.players = []  # vlc players (index-aligned to frames)
        self.last_play_attempts = [0.0] * max(4, num_cams)  # Track last play attempt per cam

        central = QtWidgets.QWidget()
        central.setContentsMargins(0, 0, 0, 0)
        central.setStyleSheet("background: transparent;")
        self.setCentralWidget(central)
        
        # Group label
        self.group_label = QtWidgets.QLabel(central)
        self.group_label.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.group_label.setStyleSheet("""
            background: transparent;
            color: #FFA500;
            font-size: 16px;
            font-weight: bold;
            padding: 6px;
            text-shadow: 1px 1px 2px black;
        """)
        self.group_label.setText(f"{group_name}")
        self.group_label.adjustSize()
        self.group_label.raise_()

        # Time label
        self.time_label = QtWidgets.QLabel(central)
        self.time_label.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.time_label.setStyleSheet("""
            background: transparent;
            color: #FFA500;
            font-size: 16px;
            font-weight: bold;
            padding: 6px;
            text-shadow: 1px 1px 2px black;
        """)
        self.time_label.setText(datetime.now().strftime("%H:%M:%S %d/%m/%Y"))
        self.time_label.adjustSize()
        self.time_label.raise_()

        # Timer to update time
        self.time_timer = QtCore.QTimer(self)
        self.time_timer.setInterval(1000)  # Update every second
        self.time_timer.timeout.connect(self._update_time)
        self.time_timer.start()

        # Create frames and overlay labels
        for cam in self.cams:
            f = QtWidgets.QFrame(central)
            f.setStyleSheet("background: transparent; border: 0px;")
            lbl = QtWidgets.QLabel(central)
            lbl.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            lbl.setStyleSheet("""
                background: transparent;
                color: #FFA500;
                padding: 4px;
                font-size: 14px;
                text-shadow: 1px 1px 2px black;
            """)
            lbl.setText(f"{cam.get('name','')}")
            lbl.adjustSize()
            lbl.move(8, 8)
            lbl.raise_()
            self.frames.append((f, lbl, cam))
            if self.group_label:
                sw = self.width()
                self.group_label.move(sw - self.group_label.width() - 20, 10)
                self.group_label.raise_()

        # Add black tiles for 2 or 3 cams
        if num_cams == 2:
            for _ in range(2):  # Add 2 black tiles
                f = QtWidgets.QFrame(central)
                f.setStyleSheet("background: transparent; border: 0px;")
                self.frames.append((f, None, None))
        elif num_cams == 3:
            f = QtWidgets.QFrame(central)  # Add 1 black tile
            f.setStyleSheet("background: transparent; border: 0px;")
            self.frames.append((f, None, None))

        # Define tile map based on number of cameras
        self.tile_map = self._get_tile_map(num_cams)

        # Monitor connection status
        self.monitor_timer = QtCore.QTimer(self)
        self.monitor_timer.setInterval(2000)
        self.monitor_timer.timeout.connect(self._monitor_players)
        self.monitor_timer.start()

        # Show fullscreen and layout
        QtCore.QTimer.singleShot(50, self.showFullScreen)
        QtCore.QTimer.singleShot(80, self._layout_and_attach)

        self._fullscreen = True

    def _get_tile_map(self, num_cams: int):
        """Return tile boundaries: {cam_idx: (x_start, y_start, x_end, y_end)}."""
        if num_cams == 1:
            return {0: (0, 0, 1, 1)}  # Full screen
        elif num_cams in (2, 3, 4):
            return {
                0: (0, 0, 1, 1),  # Top-left
                1: (1, 0, 2, 1),  # Top-right
                2: (0, 1, 1, 2),  # Bottom-left
                3: (1, 1, 2, 2),  # Bottom-right
            }
        else:  # 5-6: 3x3 grid
            return {
                0: (0, 0, 2, 2),  # A: 2x2 top-left
                1: (2, 0, 3, 1),  # B: col 2, row 0
                2: (2, 1, 3, 2),  # C: col 2, row 1
                3: (2, 2, 3, 3),  # D: col 2, row 2
                4: (0, 2, 1, 3),  # E: col 0, row 2
                5: (1, 2, 2, 3),  # F: col 1, row 2
            }

    def _layout_and_attach(self):
        """Set frame geometry based on tile map and attach players."""
        screen = self.windowHandle().screen() if self.windowHandle() else QtWidgets.QApplication.primaryScreen()
        geom = screen.geometry()
        sw, sh = geom.width(), geom.height()

        # Determine segments from tile_map
        max_x_seg = max(t[2] for t in self.tile_map.values())
        max_y_seg = max(t[3] for t in self.tile_map.values())
        x_bounds = compute_boundaries(sw, max_x_seg)
        y_bounds = compute_boundaries(sh, max_y_seg)

        # Set geometry for each frame
        for idx, (frame, lbl, cam) in enumerate(self.frames):
            if idx not in self.tile_map:
                frame.setGeometry(0, 0, 0, 0)
                continue
            xs, ys, xe, ye = self.tile_map[idx]
            x = x_bounds[xs]
            y = y_bounds[ys]
            w = x_bounds[xe] - x
            h = y_bounds[ye] - y
            w = max(0, int(w))
            h = max(0, int(h))
            frame.setGeometry(int(x), int(y), w, h)

            if lbl:
                lbl.adjustSize()
                lbl.move(frame.x() + 8, frame.y() + frame.height() - lbl.height() - 8)
                lbl.raise_()

        # Position group label
        if self.group_label:
            sw = self.width()
            self.group_label.move(sw - self.group_label.width() - 20, 10)
            self.group_label.raise_()

        # Position time label at top center
        if self.time_label:
            self.time_label.adjustSize()
            self.time_label.move((sw - self.time_label.width()) // 2, 10)
            self.time_label.raise_()

        # Attach or reassign players
        if not self.players:
            for idx, (frame, lbl, cam) in enumerate(self.frames):
                if cam is None:  # Black tile
                    self.players.append(None)
                    continue
                try:
                    player = self.vlc_instance.media_player_new()
                    media = self.vlc_instance.media_new(cam["url"], VLC_OPTS)
                    player.set_media(media)
                    set_player_window_for_platform(player, frame)
                    player.play()
                    self.players.append(player)
                    if lbl:  # Raise label after attaching player
                        lbl.adjustSize()
                        lbl.raise_()
                except Exception as e:
                    print(f"[ERROR] attach player failed for {cam.get('name')}: {e}")
                    self.players.append(None)
        else:
            for i, (frame, lbl, _) in enumerate(self.frames):
                if i < len(self.players) and self.players[i]:
                    set_player_window_for_platform(self.players[i], frame)
                    if lbl:  # Raise label after reassigning player
                        lbl.adjustSize()
                        lbl.raise_()

    def _update_time(self):
        """Update the time label with current time."""
        self.time_label.setText(datetime.now().strftime("%H:%M:%S %d/%m/%Y"))
        self.time_label.adjustSize()
        sw = self.width()
        self.time_label.move((sw - self.time_label.width()) // 2, 10)
        self.time_label.raise_()

    def _monitor_players(self):
        """Check player status and update labels."""
        for idx, (frame, lbl, cam) in enumerate(self.frames):
            if cam is None:  # Black tile
                continue
            player = self.players[idx] if idx < len(self.players) else None
            if player and player.get_state() not in (vlc.State.Playing, vlc.State.Paused):
                now = time.time()
                if now - self.last_play_attempts[idx] > self.RECONNECT_INTERVAL:
                    self._start_playback(idx)
                    if lbl:
                        lbl.setText(f"{cam.get('name','')} (Đang kết nối...)")
                        lbl.adjustSize()
                        lbl.raise_()
                        if self.group_label:
                            sw = self.width()
                            self.group_label.move(sw - self.group_label.width() - 20, 10)
                            self.group_label.raise_()
            else:
                if lbl:
                    lbl.setText(f"{cam.get('name','')}")
                    lbl.adjustSize()
                    lbl.raise_()
                    if self.group_label:
                        sw = self.width()
                        self.group_label.move(sw - self.group_label.width() - 20, 10)
                        self.group_label.raise_()

    def _start_playback(self, idx):
        """Start or restart playback for a specific camera."""
        if idx >= len(self.frames) or self.frames[idx][2] is None:
            return
        frame, lbl, cam = self.frames[idx]
        url = cam.get("url", "")
        if not url:
            return
        now = time.time()
        if now - self.last_play_attempts[idx] < 1.0:
        # if now - self.last_play_attempts[idx] < 0.3:
            return
        self.last_play_attempts[idx] = now
        try:
            player = self.players[idx]
            if player:
                player.stop()
            media = self.vlc_instance.media_new(url, VLC_OPTS)
            player.set_media(media)
            set_player_window_for_platform(player, frame)
            player.play()
            if lbl:  # Raise label after starting playback
                lbl.adjustSize()
                lbl.raise_()
        except Exception as e:
            print(f"[ERROR] Playback failed for {cam.get('name','cam')}: {e}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QtCore.QTimer.singleShot(10, self._layout_and_attach)

    def showEvent(self, event):
        super().showEvent(event)
        QtCore.QTimer.singleShot(40, self._layout_and_attach)

    def keyPressEvent(self, event):
        if (event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier) and event.key() == QtCore.Qt.Key.Key_F:
            if self._fullscreen:
                self.showNormal()
                self._fullscreen = False
            else:
                self.showFullScreen()
                self._fullscreen = True
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        for p in self.players:
            try:
                if p:
                    p.stop()
            except Exception:
                pass
        event.accept()

# ---------- Main ----------
def main():
    app = QtWidgets.QApplication(sys.argv)
    vlc_args = ["--no-xlib"] if sys.platform.startswith("linux") else []
    vlc_instance = vlc.Instance(*vlc_args)

    # Load cameras from JSON file
    CAM_LIST = load_cameras_from_json()
    
    if not CAM_LIST:
        print("[ERROR] No cameras available. Exiting.")
        sys.exit(1)

    # Group cameras by area
    cam_groups = {}
    for cam in CAM_LIST:
        area = cam.get("area", "Unknown")
        if area not in cam_groups:
            cam_groups[area] = []
        cam_groups[area].append(cam)

    # Create a CustomLayoutWindow for each group
    windows = []
    for i, (group_name, cams) in enumerate(cam_groups.items()):
        custom = CustomLayoutWindow(cams, vlc_instance, group_name)
        custom.move(50 * i, 50 * i)  # Offset windows to avoid overlap
        custom.show()
        windows.append(custom)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()