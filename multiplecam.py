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

Requirements:
    pip install PyQt6 python-vlc
"""
import sys
import os
import time
from PyQt6 import QtWidgets, QtCore


# Add DLL directory for libvlc
base_path = os.path.dirname(os.path.abspath(__file__))
os.add_dll_directory(base_path)
import vlc
# ---------- Cameras ----------
CAM_LIST = [
    {"url": "rtsp://admin:UNV123456%@192.168.22.18:554/ch01", "area": "KHU VỰC BUỒNG GIAM - 2 CAMERA", "name": "A11"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.15:554/ch01", "area": "KHU VỰC BUỒNG GIAM - 2 CAMERA", "name": "A12"},
    {"url": "rtsp://admin:123456a$@192.168.22.73:554/ch01", "area": "KHU VỰC HÀNG RÀO PHÍA BẮC - 6 CAMERA", "name": "B11"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.611:554/ch01", "area": "KHU VỰC HÀNG RÀO PHÍA BẮC - 6 CAMERA", "name": "B12"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.611:554/ch01", "area": "KHU VỰC HÀNG RÀO PHÍA BẮC - 6 CAMERA", "name": "B13"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.611:554/ch01", "area": "KHU VỰC HÀNG RÀO PHÍA BẮC - 6 CAMERA", "name": "B14"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.611:554/ch01", "area": "KHU VỰC HÀNG RÀO PHÍA BẮC - 6 CAMERA", "name": "B15"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.611:554/ch01", "area": "KHU VỰC HÀNG RÀO PHÍA BẮC - 6 CAMERA", "name": "B16"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.46:554/ch01", "area": "KHU VỰC KSAN - 2 CAMERA", "name": "C11"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.100:554/ch01", "area": "KHU VỰC KSAN - 2 CAMERA", "name": "C12"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.261:554/ch01", "area": "KHU VỰC CỔNG TRẠI - 3 CAMERA", "name": "D11"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.261:554/ch01", "area": "KHU VỰC CỔNG TRẠI - 3 CAMERA", "name": "D12"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.61:554/ch01", "area": "KHU VỰC CỔNG TRẠI - 3 CAMERA", "name": "D13"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.42:554/ch01", "area": "KHU VỰC ĐIỂM DANH LAO ĐỘNG RA VÀO DOANH TRẠI - 3 CAMERA", "name": "E11"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.27:554/ch01", "area": "KHU VỰC ĐIỂM DANH LAO ĐỘNG RA VÀO DOANH TRẠI - 3 CAMERA", "name": "E12"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.28:554/ch01", "area": "KHU VỰC ĐIỂM DANH LAO ĐỘNG RA VÀO DOANH TRẠI - 3 CAMERA", "name": "E13"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.24:554/ch01", "area": "KHU VỰC THĂM GẶP - 2 CAMERA", "name": "F11"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.86:554/ch01", "area": "KHU VỰC THĂM GẶP - 2 CAMERA", "name": "F12"},
]

# VLC options
VLC_OPTS = ":no-video-title-show :no-sub-autodetect-file :no-osd :network-caching=300"

# ---------- Helpers ----------
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
        self.setWindowFlags(QtCore.Qt.WindowType.Window)

        self.cams = cams
        self.vlc_instance = vlc_instance
        self.frames = []  # list of (frame, label, cam) or (frame, None, None) for black tile
        self.players = []  # vlc players (index-aligned to frames)
        self.last_play_attempts = [0.0] * max(4, num_cams)  # Track last play attempt per cam

        central = QtWidgets.QWidget()
        central.setContentsMargins(0, 0, 0, 0)
        central.setStyleSheet("background: black;")
        self.setCentralWidget(central)

        # Create frames and overlay labels
        for cam in self.cams:
            f = QtWidgets.QFrame(central)
            f.setStyleSheet("background: black; border: 0px;")
            # lbl = QtWidgets.QLabel(f)
            # lbl.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            # lbl.setStyleSheet("background: transparent; color: #FFA500; padding: 4px; font-size: 14px;")
            # lbl.setText(f"{cam.get('name','')} - {cam.get('area','')}")
            # lbl.adjustSize()
            # lbl.move(8, 8)
            lbl = QtWidgets.QLabel(central)
            lbl.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            # lbl.setStyleSheet("background: transparent; color: #FFA500; padding: 4px; font-size: 14px;")
            lbl.setStyleSheet("background-color: rgba(0, 0, 0, 100); color: #FFA500; padding: 2px 6px; font-size: 14px; border-radius: 4px;")
            lbl.setText(f"{cam.get('name','')} - {cam.get('area','')}")
            lbl.adjustSize()
            lbl.move(8, 8)
            lbl.raise_()
            self.frames.append((f, lbl, cam))

        # Add black tiles for 2 or 3 cams
        if num_cams == 2:
            for _ in range(2):  # Add 2 black tiles
                f = QtWidgets.QFrame(central)
                f.setStyleSheet("background: black; border: 0px;")
                self.frames.append((f, None, None))
        elif num_cams == 3:
            f = QtWidgets.QFrame(central)  # Add 1 black tile
            f.setStyleSheet("background: black; border: 0px;")
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
            # 2x2 grid: top-left, top-right, bottom-left, bottom-right
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
                # lbl.move(frame.x() + 8, frame.y() + 8)
                # lbl.raise_()
                lbl.adjustSize()
                lbl.move(frame.x() + 8, frame.y() + frame.height() - lbl.height() - 8)
                lbl.raise_()

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
                        lbl.setText(f"{cam.get('name','')} - {cam.get('area','')} (Đang kết nối...)")
                        lbl.adjustSize()
                        lbl.raise_()
            else:
                if lbl:
                    lbl.setText(f"{cam.get('name','')} - {cam.get('area','')}")
                    lbl.adjustSize()
                    lbl.raise_()

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