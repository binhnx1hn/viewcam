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
- Real-time area counts panel on the right side showing prisoner, officer, and relative counts by area

Requirements:
    pip install PyQt6 python-vlc python-socketio
"""
import sys
import os
import time
import json
import csv
import weakref
import threading
from PyQt6 import QtWidgets, QtCore, QtGui, QtNetwork
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QPixmap
from datetime import datetime
from collections import defaultdict
from urllib.parse import urljoin

# Add DLL directory for libvlc
base_path = os.path.dirname(os.path.abspath(__file__))
os.add_dll_directory(base_path)
import vlc

# Import socket and department mapping
try:
    from hooks.use_socket import use_socket_statical
    from department_mapping import get_department_info
    SOCKET_AVAILABLE = True
except ImportError as e:
    print(f"[WARN] Socket modules not available: {e}")
    print("[INFO] Real-time area counts will be disabled")
    SOCKET_AVAILABLE = False

# ---------- Configuration ----------
CAMERA_JSON_FILE = os.path.join(base_path, "camera.json")
SUBJECTS_CSV_FILE = os.path.join(base_path, "movis_vms.subjects.csv")
VLC_OPTS = (
    ":network-caching=0 :live-caching=0 :file-caching=0 :disc-caching=0 :drop-late-frames :skip-frames"
)
PANEL_WIDTH = 350  # Width of the right-side panel for area counts
MAX_CAMS_PER_WINDOW = 16  # Maximum cameras per window
VIEW_MODES = [1, 2, 4, 9, 16]  # Available view modes: 1x1, 1x2, 2x2, 3x3, 4x4
DEFAULT_VIEW_MODE = 4  # Default view mode (2x2 grid)
AUTO_ROTATE_INTERVAL = 30000  # Auto-rotate interval in ms (30 seconds) for single-cam view

# ---------- Stream mode ----------
# "people_stream" = use AI-processed bbox stream (fall back to origin_url if people_stream is empty)
# "origin_url"    = always use direct camera RTSP
STREAM_MODE = "people_stream"


def normalize_area_name(area_name: str) -> str:
    """Return normalized area name for comparisons."""
    if not area_name:
        return ""
    return " ".join(area_name.split()).lower()


ALLOWED_RECOGNITION_AREAS = {
    normalize_area_name("KHU VỰC BUỒNG GIAM 01"),
    normalize_area_name("KHU VỰC BUỒNG GIAM 02"),
}
IMAGE_BASE_URL = "http://192.168.22.2:10000/movis_data"  # Base URL for face images
CSV_IMAGE_BASE_URL = "http://192.168.22.2:10000"  # Base URL for CSV images

# ---------- Fallback camera list (used if JSON file is not found) ----------
# Each entry carries both origin_url (direct RTSP) and people_stream (AI bbox stream).
# The 'url' field is resolved at runtime by resolve_cam_url() based on STREAM_MODE.
DEFAULT_CAM_LIST = [
    {"url": "rtsp://192.168.22.3:8564/bbox/f4ebc728df05346e7d2f785b", "origin_url": "rtsp://service:Bosch123%@192.168.22.171:554/stream1", "people_stream": "rtsp://192.168.22.3:8564/bbox/f4ebc728df05346e7d2f785b", "area": "KHU VỰC BUỒNG GIAM 01", "name": "A11", "camera_id": "f4ebc728df05346e7d2f785b"},
    {"url": "rtsp://192.168.22.3:8564/bbox/0b92b8b2602c011d1831c6c2", "origin_url": "rtsp://service:Bosch123%@192.168.22.172:554/stream1", "people_stream": "rtsp://192.168.22.3:8564/bbox/0b92b8b2602c011d1831c6c2", "area": "KHU VỰC BUỒNG GIAM 01", "name": "A12", "camera_id": "0b92b8b2602c011d1831c6c2"},
    {"url": "rtsp://service:Bosch123%@192.168.22.174:554/stream1", "origin_url": "rtsp://service:Bosch123%@192.168.22.174:554/stream1", "people_stream": "", "area": "KHU VỰC BUỒNG GIAM 02", "name": "A13", "camera_id": "f35b705e8c57ae59e369ebc9"},
    {"url": "rtsp://service:Bosch123%@192.168.22.173:554/stream1", "origin_url": "rtsp://service:Bosch123%@192.168.22.173:554/stream1", "people_stream": "", "area": "KHU VỰC BUỒNG GIAM 02", "name": "A14", "camera_id": "43ba9900ff2fc7d9d3207254"},
    {"url": "rtsp://192.168.22.3:8564/bbox/c064aa5670a62419ecc714e0", "origin_url": "rtsp://admin:UNV123456%@192.168.22.168:554/ch01", "people_stream": "rtsp://192.168.22.3:8564/bbox/c064aa5670a62419ecc714e0", "area": "KHU VỰC HÀNG RÀO", "name": "B11", "camera_id": "c064aa5670a62419ecc714e0"},
    {"url": "rtsp://192.168.22.3:8564/bbox/8acfe827853aff5217d7ef21", "origin_url": "rtsp://admin:UNV123456%@192.168.22.157:554/ch01", "people_stream": "rtsp://192.168.22.3:8564/bbox/8acfe827853aff5217d7ef21", "area": "KHU VỰC HÀNG RÀO", "name": "B12", "camera_id": "8acfe827853aff5217d7ef21"},
    {"url": "rtsp://192.168.22.3:8564/bbox/5a90dccf0259cc883dd91c7a", "origin_url": "rtsp://service:Bosch123%@192.168.22.176:554/stream1", "people_stream": "rtsp://192.168.22.3:8564/bbox/5a90dccf0259cc883dd91c7a", "area": "KHU VỰC KSAN", "name": "C21", "camera_id": "5a90dccf0259cc883dd91c7a"},
    {"url": "rtsp://192.168.22.3:8564/bbox/f1c9d16d7f35450ac3171d20", "origin_url": "rtsp://service:Bosch123%@192.168.22.175:554/stream1", "people_stream": "rtsp://192.168.22.3:8564/bbox/f1c9d16d7f35450ac3171d20", "area": "KHU VỰC KSAN", "name": "C22", "camera_id": "f1c9d16d7f35450ac3171d20"},
    {"url": "rtsp://192.168.22.3:8564/bbox/83567cd28bc5c1e1749a19fa", "origin_url": "rtsp://service:Bosch123%@192.168.22.177:554/stream1", "people_stream": "rtsp://192.168.22.3:8564/bbox/83567cd28bc5c1e1749a19fa", "area": "KHU VỰC KSAN", "name": "C23", "camera_id": "83567cd28bc5c1e1749a19fa"},
    {"url": "rtsp://192.168.22.3:8564/bbox/c0e3be4e63002c75ba05748a", "origin_url": "rtsp://admin:UNV123456%@192.168.22.149:554/ch01", "people_stream": "rtsp://192.168.22.3:8564/bbox/c0e3be4e63002c75ba05748a", "area": "KHU VỰC CỔNG TRẠI 02", "name": "D11", "camera_id": "c0e3be4e63002c75ba05748a"},
    {"url": "rtsp://192.168.22.3:8564/bbox/75b573a2a80f7d1f54f711b8", "origin_url": "rtsp://admin:UNV123456%@192.168.22.155:554/ch01", "people_stream": "rtsp://192.168.22.3:8564/bbox/75b573a2a80f7d1f54f711b8", "area": "KHU VỰC CỔNG TRẠI 02", "name": "D12", "camera_id": "75b573a2a80f7d1f54f711b8"},
    {"url": "rtsp://192.168.22.3:8564/bbox/e6a6a63057a146f86c6d0f94", "origin_url": "rtsp://admin:UNV123456%@192.168.22.150:554/ch01", "people_stream": "rtsp://192.168.22.3:8564/bbox/e6a6a63057a146f86c6d0f94", "area": "KHU VỰC LAO ĐỘNG", "name": "E11", "camera_id": "e6a6a63057a146f86c6d0f94"},
    {"url": "rtsp://192.168.22.3:8564/bbox/084babdcdda0e2f987d9d505", "origin_url": "rtsp://admin:UNV123456%@192.168.22.162:554/ch01", "people_stream": "rtsp://192.168.22.3:8564/bbox/084babdcdda0e2f987d9d505", "area": "KHU VỰC LAO ĐỘNG", "name": "E12", "camera_id": "084babdcdda0e2f987d9d505"},
    {"url": "rtsp://192.168.22.3:8564/bbox/7975566a25bafcc34f6109d3", "origin_url": "rtsp://admin:UNV123456%@192.168.22.163:554/ch01", "people_stream": "rtsp://192.168.22.3:8564/bbox/7975566a25bafcc34f6109d3", "area": "KHU VỰC LAO ĐỘNG", "name": "E13", "camera_id": "7975566a25bafcc34f6109d3"}
]


# ---------- Helpers ----------
def resolve_cam_url(cam: dict) -> None:
    """
    Resolve cam["url"] in-place based on the current STREAM_MODE.

    Rules:
    - If STREAM_MODE == "people_stream" and cam["people_stream"] is non-empty → use people_stream
    - Otherwise fall back to cam["origin_url"] if present, else keep existing cam["url"]

    Args:
        cam: Camera dictionary (mutated in-place)
    """
    people_stream = cam.get("people_stream", "")
    origin_url = cam.get("origin_url", "")

    if STREAM_MODE == "people_stream" and people_stream:
        cam["url"] = people_stream
    elif origin_url:
        cam["url"] = origin_url
    # else: leave cam["url"] unchanged (backward compat for entries without both fields)


def load_cameras_from_json(json_file: str = None) -> list:
    """
    Load camera list from JSON file and resolve each camera's active URL
    based on the current STREAM_MODE.

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
            cams = [dict(c) for c in DEFAULT_CAM_LIST]
            for cam in cams:
                resolve_cam_url(cam)
            return cams

        with open(json_file, 'r', encoding='utf-8') as f:
            cameras = json.load(f)

        # Validate structure
        if not isinstance(cameras, list):
            print(f"[ERROR] Invalid JSON structure: expected list, got {type(cameras)}")
            print("[INFO] Using default camera list")
            cams = [dict(c) for c in DEFAULT_CAM_LIST]
            for cam in cams:
                resolve_cam_url(cam)
            return cams

        # Validate each camera has required fields
        valid_cameras = []
        for idx, cam in enumerate(cameras):
            if not isinstance(cam, dict):
                print(f"[WARN] Skipping invalid camera at index {idx}: not a dictionary")
                continue
            if 'url' not in cam or 'area' not in cam:
                print(f"[WARN] Skipping invalid camera at index {idx}: missing 'url' or 'area'")
                continue
            # Resolve active URL based on current STREAM_MODE
            resolve_cam_url(cam)
            valid_cameras.append(cam)

        if not valid_cameras:
            print("[ERROR] No valid cameras found in JSON file")
            print("[INFO] Using default camera list")
            cams = [dict(c) for c in DEFAULT_CAM_LIST]
            for cam in cams:
                resolve_cam_url(cam)
            return cams

        print(f"[INFO] Loaded {len(valid_cameras)} cameras from {json_file}")
        return valid_cameras

    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse JSON file: {e}")
        print("[INFO] Using default camera list")
        cams = [dict(c) for c in DEFAULT_CAM_LIST]
        for cam in cams:
            resolve_cam_url(cam)
        return cams
    except Exception as e:
        print(f"[ERROR] Failed to load camera JSON file: {e}")
        print("[INFO] Using default camera list")
        cams = [dict(c) for c in DEFAULT_CAM_LIST]
        for cam in cams:
            resolve_cam_url(cam)
        return cams


def load_subject_images_from_csv(csv_file: str = None) -> dict:
    """
    Load subject images from CSV file.

    Returns:
        Dict mapping lowercase subject name to absolute image URL.
    """
    if csv_file is None:
        csv_file = SUBJECTS_CSV_FILE

    image_map = {}
    if not os.path.exists(csv_file):
        print(f"[WARN] Subjects CSV not found: {csv_file}")
        return image_map

    try:
        with open(csv_file, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                name = (row.get("name") or "").strip()
                image_path = (row.get("image") or row.get("images[0]") or "").strip()
                if not name or not image_path:
                    continue
                # Build absolute URL
                if image_path.startswith("/"):
                    full_url = f"{CSV_IMAGE_BASE_URL}{image_path}"
                else:
                    full_url = f"{CSV_IMAGE_BASE_URL}/{image_path}"
                image_map[name.lower()] = full_url
    except Exception as exc:
        print(f"[WARN] Failed to load subjects CSV: {exc}")

    print(f"[INFO] Loaded {len(image_map)} subject images from CSV")
    return image_map


SUBJECT_IMAGE_MAP = load_subject_images_from_csv()


def get_subject_image_url(subject_name: str) -> str | None:
    """Return CSV-derived image URL for a given subject name."""
    if not subject_name:
        return None
    key = subject_name.strip().lower()
    return SUBJECT_IMAGE_MAP.get(key)


def compute_boundaries(total_pixels: int, segments: int):
    """Return integer boundaries ensuring sum equals total_pixels."""
    return [int(round(i * total_pixels / segments)) for i in range(segments + 1)]


# ---------- Area Count Tracker ----------
class AreaCountTracker:
    """Theo dõi và quản lý số lượng theo area"""
    
    def __init__(self):
        # Dictionary để lưu trữ counts theo department_id
        # Format: {department_id: {'prisoner': int, 'officer': int, 'relative': int, 'list_person': list}}
        self.dept_counts = {}
        self.last_update_time = None
        
    def update_counts(self, department_id, data_count, list_person=None):
        """
        Cập nhật counts cho một department
        
        Args:
            department_id: ID của department
            data_count: Dictionary chứa counts {'prisoner': int, 'officer': int, 'relative': int}
            list_person: List of person dictionaries with face recognition data
        """
        # Lưu counts theo department_id
        if data_count:
            self.dept_counts[department_id] = {
                'prisoner': data_count.get('prisoner', 0),
                'officer': data_count.get('officer', 0),
                'relative': data_count.get('relative', 0),
                'list_person': list_person if list_person else []
            }
        
        self.last_update_time = time.strftime('%H:%M:%S')
    
    def get_area_counts(self):
        """
        Tổng hợp counts theo area từ tất cả departments
        
        Returns:
            Dictionary {area: {'prisoner': int, 'officer': int, 'relative': int, 'list_person': list}}
        """
        area_counts = defaultdict(lambda: {
            'prisoner': 0,
            'officer': 0,
            'relative': 0,
            'list_person': []
        })
        
        # Duyệt qua tất cả departments và tổng hợp theo area
        for department_id, counts in self.dept_counts.items():
            dept_info = get_department_info(department_id) if SOCKET_AVAILABLE else {}
            area = dept_info.get('area', '') if dept_info else ''
            
            # If there's no area from mapping, try treating `department_id` as the area name.
            # This happens when the socket payload is missing `department_id`,
            # and the frontend uses `window_area` as a fallback key to still show the panel.
            if not area:
                if normalize_area_name(department_id) in ALLOWED_RECOGNITION_AREAS:
                    area = department_id
                else:
                    area = f"UNKNOWN_AREA ({department_id[:8]}...)"
            
            # Cộng dồn counts vào area
            area_counts[area]['prisoner'] += counts['prisoner']
            area_counts[area]['officer'] += counts['officer']
            area_counts[area]['relative'] += counts['relative']
            
            # Aggregate list_person for display.
            if 'list_person' in counts:
                for person in counts['list_person']:
                    # Socket payload may have empty `subject_name` and `score=0`,
                    # and sometimes `face_url` itself can be empty too.
                    # We include the person if we have an identity (face_id/track_id),
                    # so the UI can show a placeholder when `face_url` is missing.
                    if person.get('face_id') or person.get('track_id'):
                        area_counts[area]['list_person'].append(person)
        
        return area_counts

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

# ---------- Camera selection dialog ----------
class CameraSelectDialog(QtWidgets.QDialog):
    """Dialog for selecting which cameras to display in a window."""

    def __init__(self, all_cameras: list, selected_cams: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chọn camera hiển thị")
        self.setMinimumSize(420, 520)
        self.all_cameras = all_cameras
        selected_urls = {c["url"] for c in selected_cams}

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)

        # Title
        title = QtWidgets.QLabel("Chọn camera cho cửa sổ này:")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFA500; padding: 6px;")
        layout.addWidget(title)

        # Select all / Deselect all buttons
        btn_row = QtWidgets.QHBoxLayout()
        select_all_btn = QtWidgets.QPushButton("☑ Chọn tất cả")
        select_all_btn.setStyleSheet(self._btn_style())
        select_all_btn.clicked.connect(self._select_all)
        deselect_all_btn = QtWidgets.QPushButton("☐ Bỏ chọn tất cả")
        deselect_all_btn.setStyleSheet(self._btn_style())
        deselect_all_btn.clicked.connect(self._deselect_all)
        btn_row.addWidget(select_all_btn)
        btn_row.addWidget(deselect_all_btn)
        layout.addLayout(btn_row)

        # Scroll area with checkboxes grouped by area
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: #1e1e1e; }
            QScrollBar:vertical {
                background: #2a2a2a; width: 10px; border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #FFA500; min-height: 30px; border-radius: 5px;
            }
        """)
        scroll_widget = QtWidgets.QWidget()
        scroll_widget.setStyleSheet("background: #1e1e1e;")
        scroll_layout = QtWidgets.QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(8)

        # Group cameras by area
        from collections import OrderedDict
        area_groups = OrderedDict()
        for cam in all_cameras:
            area = cam.get("area", "Không xác định")
            area_groups.setdefault(area, []).append(cam)

        self.checkboxes = []      # list of (QCheckBox, cam_dict)
        self._area_cbs = {}       # area_name -> list of QCheckBox (for area toggle)

        for area, cams in area_groups.items():
            group = QtWidgets.QGroupBox()
            group.setStyleSheet("""
                QGroupBox {
                    border: 2px solid #555; border-radius: 6px;
                    margin-top: 0px; padding: 10px 10px 10px 10px;
                    background: #252525;
                }
            """)
            group_layout = QtWidgets.QVBoxLayout(group)
            group_layout.setSpacing(4)

            # Area header with toggle button
            header_row = QtWidgets.QHBoxLayout()
            area_label = QtWidgets.QLabel(f"📍 {area}")
            area_label.setStyleSheet("""
                color: #FFA500; font-size: 14px; font-weight: bold;
                background: transparent; padding: 4px;
            """)
            header_row.addWidget(area_label)
            header_row.addStretch()

            toggle_btn = QtWidgets.QPushButton("Chọn khu vực")
            toggle_btn.setStyleSheet("""
                QPushButton {
                    background: #444; color: #FFA500; font-size: 12px;
                    padding: 4px 12px; border-radius: 3px; border: 1px solid #FFA500;
                }
                QPushButton:hover { background: #555; }
            """)
            toggle_btn.setFixedHeight(28)
            header_row.addWidget(toggle_btn)
            group_layout.addLayout(header_row)

            # Separator
            sep = QtWidgets.QFrame()
            sep.setFrameShape(QtWidgets.QFrame.Shape.HLine)
            sep.setStyleSheet("background: #555; max-height: 1px; border: none;")
            group_layout.addWidget(sep)

            area_cb_list = []
            for cam in cams:
                name = cam.get("name", cam.get("url", ""))
                cb = QtWidgets.QCheckBox(f"  {name}")
                cb.setChecked(cam["url"] in selected_urls)
                cb.setToolTip(cam["url"])
                cb.setStyleSheet("""
                    QCheckBox {
                        color: #e0e0e0; font-size: 14px;
                        padding: 5px 4px; spacing: 8px;
                        background: transparent;
                    }
                    QCheckBox:hover { color: #FFA500; }
                """)
                group_layout.addWidget(cb)
                self.checkboxes.append((cb, cam))
                area_cb_list.append(cb)

            self._area_cbs[area] = area_cb_list
            # Connect toggle button
            toggle_btn.clicked.connect(
                lambda checked, a=area: self._toggle_area(a)
            )

            scroll_layout.addWidget(group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # OK / Cancel buttons
        btn_layout = QtWidgets.QHBoxLayout()
        ok_btn = QtWidgets.QPushButton("✔ Áp dụng")
        ok_btn.setStyleSheet(self._btn_style())
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QtWidgets.QPushButton("✖ Hủy")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #555; color: white; font-weight: bold;
                font-size: 14px; padding: 8px 20px; border-radius: 4px; border: none;
            }
            QPushButton:hover { background: #777; }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    @staticmethod
    def _btn_style():
        return """
            QPushButton {
                background: #FFA500; color: #1e1e1e; font-weight: bold;
                font-size: 14px; padding: 8px 20px; border-radius: 4px; border: none;
            }
            QPushButton:hover { background: #FFB733; }
        """

    def _toggle_area(self, area_name: str):
        """Toggle all checkboxes in an area. If any unchecked -> check all; else uncheck all."""
        cbs = self._area_cbs.get(area_name, [])
        if not cbs:
            return
        any_unchecked = any(not cb.isChecked() for cb in cbs)
        for cb in cbs:
            cb.setChecked(any_unchecked)

    def _select_all(self):
        for cb, _ in self.checkboxes:
            cb.setChecked(True)

    def _deselect_all(self):
        for cb, _ in self.checkboxes:
            cb.setChecked(False)

    def get_selected_cameras(self) -> list:
        """Return list of selected camera dicts."""
        return [cam for cb, cam in self.checkboxes if cb.isChecked()]


# ---------- Custom layout window with dynamic tiling ----------
class CustomLayoutWindow(QtWidgets.QMainWindow):
    """
    Dynamic layout with switchable view modes:
    - 1 cam (1x1): Full screen single camera
    - 4 cams (2x2): 2x2 grid
    - 9 cams (3x3): 3x3 grid
    - 16 cams (4x4): 4x4 grid
    Right-click context menu to switch view modes and navigate pages.
    """

    RECONNECT_INTERVAL = 5  # seconds

    def __init__(self, all_cams, vlc_instance: vlc.Instance, group_name: str,
                 all_available_cameras: list = None, parent=None):
        super().__init__(parent)
        self.all_cams = all_cams  # Cameras assigned to this window
        self._all_available_cameras = all_available_cameras or all_cams  # Full camera list for selection dialog
        self.vlc_instance = vlc_instance
        self.group_name = group_name
        self.view_mode = DEFAULT_VIEW_MODE  # Current view mode (1, 4, 9, 16)
        self.current_page = 0  # Current page index (0-based)
        self._last_panel_snapshot = None
        self._rebuilding = False

        # Initialize area count tracker
        self.area_tracker = AreaCountTracker() if SOCKET_AVAILABLE else None
        self.socket_client = None
        self.panel_visible = False
        self._panel_user_hidden = False
        self.network_manager = QtNetwork.QNetworkAccessManager(self)
        self.image_cache = {}
        self.pending_image_labels = defaultdict(list)
        self.pending_requests = set()

        # Persistent pool: one frame+player per camera, created once
        self._cam_frames = []   # [(QFrame, QLabel, cam_dict)] for each cam in all_cams
        self._cam_players = []  # [vlc.MediaPlayer | None] for each cam in all_cams
        self._cam_play_ts = []  # last play attempt timestamp per cam

        # Active view: indices into _cam_frames for the current page + black filler frames
        self.frames = []        # [(QFrame, QLabel|None, cam_dict|None)] visible this page
        self.players = []       # [player|None] visible this page (refs into _cam_players)
        self.last_play_attempts = []
        self.tile_map = {}
        self._filler_frames = []  # reusable black filler frames

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(QtCore.Qt.WindowType.Window)
        self._update_window_title()

        central = QtWidgets.QWidget()
        central.setContentsMargins(0, 0, 0, 0)
        central.setStyleSheet("background: transparent;")
        self.setCentralWidget(central)

        # Create right panel for area counts
        self._create_area_panel(central)

        # Group label — shown at top-right corner by default
        self.group_label = QtWidgets.QLabel(central)
        self.group_label.setStyleSheet("""
            background: rgba(0, 0, 0, 120);
            color: #FFA500;
            font-size: 28px;
            font-weight: bold;
            padding: 10px 18px;
            border-radius: 8px;
            text-shadow: 1px 1px 2px black;
        """)
        self.group_label.setText(f"{group_name}")
        self.group_label.adjustSize()
        self.group_label.show()

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

        # Page indicator label
        self.page_label = QtWidgets.QLabel(central)
        self.page_label.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.page_label.setStyleSheet("""
            background: rgba(0, 0, 0, 120);
            color: #FFA500;
            font-size: 14px;
            font-weight: bold;
            padding: 4px 10px;
            border-radius: 8px;
        """)
        self.page_label.hide()
        self.page_label.raise_()

        # Timer to update time
        self.time_timer = QtCore.QTimer(self)
        self.time_timer.setInterval(1000)
        self.time_timer.timeout.connect(self._update_time)
        self.time_timer.start()

        # Auto-rotate timer: cycles through pages in single-cam (1×1) view
        self._auto_rotate_timer = QtCore.QTimer(self)
        self._auto_rotate_timer.setInterval(AUTO_ROTATE_INTERVAL)
        self._auto_rotate_timer.timeout.connect(self._auto_rotate_tick)

        # Create persistent pool of frames and players (created once, reused)
        self._init_persistent_pool(central)

        # Build initial view (sets visibility and tile_map without recreating players)
        self._rebuild_view()

        # Monitor connection status
        self.monitor_timer = QtCore.QTimer(self)
        self.monitor_timer.setInterval(2000)
        self.monitor_timer.timeout.connect(self._monitor_players)
        self.monitor_timer.start()

        # Initialize socket connection if available
        if SOCKET_AVAILABLE and self.area_tracker:
            self._init_socket()
        else:
            if hasattr(self, 'area_status_label'):
                self.area_status_label.setText("Socket không khả dụng")
                self.area_status_label.setStyleSheet("""
                    QLabel {
                        background-color: rgba(150, 150, 150, 150);
                        color: white;
                        font-size: 12px;
                        padding: 5px;
                        border: none;
                    }
                """)

        # Initial update to check if panel should be shown
        if self.area_tracker:
            QtCore.QTimer.singleShot(100, self._update_area_panel)
        else:
            self.panel_visible = False

        # Show fullscreen and layout
        QtCore.QTimer.singleShot(50, self.showFullScreen)
        QtCore.QTimer.singleShot(80, self._layout_and_attach)

        self._fullscreen = True

    def _update_window_title(self):
        """Update window title with current view mode and page info."""
        total = len(self.all_cams)
        total_pages = max(1, (total + self.view_mode - 1) // self.view_mode)
        grid = {1: '1x1', 4: '2x2', 9: '3x3', 16: '4x4'}.get(self.view_mode, f'{self.view_mode}')
        self.setWindowTitle(
            f"{self.group_name} — {grid} — Trang {self.current_page + 1}/{total_pages} ({total} cams)"
        )

    def _get_page_cams(self):
        """Return list of cameras for the current page based on view_mode."""
        start = self.current_page * self.view_mode
        end = start + self.view_mode
        return self.all_cams[start:end]

    def _total_pages(self):
        """Return total number of pages."""
        return max(1, (len(self.all_cams) + self.view_mode - 1) // self.view_mode)

    def _init_persistent_pool(self, central):
        """Create a persistent frame + player for every camera in all_cams.

        Players are started once and kept alive across view-mode / page changes.
        Only visibility and geometry change when the user switches views.
        """
        max_fillers = max(VIEW_MODES)  # pre-create enough filler frames
        for cam in self.all_cams:
            f = QtWidgets.QFrame(central)
            f.setStyleSheet("background: transparent; border: 0px;")
            f.hide()  # hidden until needed

            lbl = QtWidgets.QLabel(central)
            lbl.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            lbl.setStyleSheet("""
                background: transparent;
                color: #FFA500;
                padding: 4px;
                font-size: 14px;
                text-shadow: 1px 1px 2px black;
            """)
            lbl.setText(cam.get('name', ''))
            lbl.adjustSize()
            lbl.hide()

            self._cam_frames.append((f, lbl, cam))

            # Create and start player immediately
            try:
                player = self.vlc_instance.media_player_new()
                # Disable VLC mouse/key input so Qt receives events on the frame
                player.video_set_mouse_input(False)
                player.video_set_key_input(False)
                media = self.vlc_instance.media_new(cam["url"], VLC_OPTS)
                player.set_media(media)
                set_player_window_for_platform(player, f)
                player.play()
                self._cam_players.append(player)
            except Exception as e:
                print(f"[ERROR] init player failed for {cam.get('name')}: {e}")
                self._cam_players.append(None)

            # Install event filter on each frame to capture right-click
            f.installEventFilter(self)
            self._cam_play_ts.append(time.time())

        # Pre-create reusable filler (black) frames
        for _ in range(max_fillers):
            f = QtWidgets.QFrame(central)
            f.setStyleSheet("background: transparent; border: 0px;")
            f.hide()
            f.installEventFilter(self)  # Capture right-click on fillers too
            self._filler_frames.append(f)

    def _rebuild_view(self):
        """Switch visible frames for the current page/view_mode.

        No players are destroyed or recreated — only visibility toggles.
        """
        # 1. Hide ALL persistent cam frames and labels
        for (frame, lbl, _cam) in self._cam_frames:
            frame.hide()
            if lbl:
                lbl.hide()

        # Hide all fillers
        for ff in self._filler_frames:
            ff.hide()

        # 2. Determine which cameras are on the current page
        page_cams = self._get_page_cams()
        num_cams = len(page_cams)
        grid_slots = self.view_mode

        # 3. Build the active frames list for this page
        self.frames.clear()
        self.players.clear()
        self.last_play_attempts.clear()

        # Map page cameras to their pool indices
        cam_to_pool_idx = {id(cam): i for i, (_f, _l, cam) in enumerate(self._cam_frames)}

        for cam in page_cams:
            pool_idx = cam_to_pool_idx[id(cam)]
            frame, lbl, cam_ref = self._cam_frames[pool_idx]
            frame.show()
            if lbl:
                lbl.show()
                lbl.raise_()
            self.frames.append((frame, lbl, cam_ref))
            self.players.append(self._cam_players[pool_idx])
            self.last_play_attempts.append(self._cam_play_ts[pool_idx])

        # 4. Add filler frames to fill the grid
        fillers_needed = grid_slots - num_cams
        for i in range(fillers_needed):
            ff = self._filler_frames[i]
            ff.show()
            self.frames.append((ff, None, None))
            self.players.append(None)
            self.last_play_attempts.append(0.0)

        # 5. Build tile map
        self.tile_map = self._get_tile_map(self.view_mode)

        # 6. Update page indicator and window title
        self._update_page_label()
        self._update_window_title()

        # 7. Ensure overlay labels stay on top
        if hasattr(self, 'group_label'):
            self.group_label.raise_()
        if hasattr(self, 'time_label'):
            self.time_label.raise_()
        if hasattr(self, 'page_label'):
            self.page_label.raise_()

    def _update_page_label(self):
        """Update the page indicator label."""
        total_pages = self._total_pages()
        if total_pages > 1:
            self.page_label.setText(f"Trang {self.current_page + 1}/{total_pages}")
            self.page_label.adjustSize()
            self.page_label.show()
            self.page_label.raise_()
        else:
            self.page_label.hide()

    def _create_area_panel(self, parent):
        """Create the right-side panel for displaying area counts."""
        self.area_panel = QtWidgets.QWidget(parent)
        self.area_panel.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 240);
                border-left: 2px solid #FFA500;
            }
        """)
        
        # Create scroll area for area counts
        scroll = QtWidgets.QScrollArea(self.area_panel)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
        """)
        
        # Container widget for area items
        self.area_container = QtWidgets.QWidget()
        self.area_container.setStyleSheet("background: transparent;")
        self.area_layout = QtWidgets.QVBoxLayout(self.area_container)
        self.area_layout.setContentsMargins(10, 10, 10, 10)
        self.area_layout.setSpacing(10)
        self.area_layout.addStretch()
        
        scroll.setWidget(self.area_container)
        
        # Title label
        title_label = QtWidgets.QLabel("NHẬN DIỆN", self.area_panel)
        title_label.setStyleSheet("""
            QLabel {
                background-color: #FFA500;
                color: white;
                font-size: 22px;
                font-weight: bold;
                padding: 10px;
                border: none;
            }
        """)
        title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        # Layout for panel
        panel_layout = QtWidgets.QVBoxLayout(self.area_panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)
        panel_layout.addWidget(title_label)
        panel_layout.addWidget(scroll)
        
        # # Status label
        # self.area_status_label = QtWidgets.QLabel("Đang kết nối...", self.area_panel)
        # self.area_status_label.setStyleSheet("""
        #     QLabel {
        #         background-color: rgba(0, 0, 0, 100);
        #         color: #FFA500;
        #         font-size: 12px;
        #         padding: 5px;
        #         border: none;
        #     }
        # """)
        # self.area_status_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        # panel_layout.addWidget(self.area_status_label)
        
        # For recognized areas (buồng giam), show panel immediately with zeros
        # For other areas, hide it (will be shown when data is available)
        window_area = None
        if self.all_cams:
            window_area = self.all_cams[0].get('area')
        
        if window_area and normalize_area_name(window_area) in ALLOWED_RECOGNITION_AREAS:
            # Will be shown after _layout_and_attach
            self.area_panel.hide()
        else:
            self.area_panel.hide()
        
        self.area_panel.raise_()
    
    def _init_socket(self):
        """Initialize socket connection for real-time updates."""
        if not SOCKET_AVAILABLE or not self.area_tracker:
            return
        
        def message_handler(payload):
            """Handle incoming socket messages."""
            try:
                if isinstance(payload, dict):
                    department_id = payload.get('department_id')
                    data_count = payload.get('data_count')
                    list_person = payload.get('list_person', [])

                    # The backend may send an empty `department_id`.
                    # For buồng giam 01/02 windows, we use `window_area` as a fallback.
                    if data_count:
                        effective_department_id = department_id
                        if not effective_department_id and self.all_cams:
                            window_area = self.all_cams[0].get('area')
                            if window_area and normalize_area_name(window_area) in ALLOWED_RECOGNITION_AREAS:
                                effective_department_id = window_area

                        if effective_department_id:
                            self.area_tracker.update_counts(effective_department_id, data_count, list_person)
                            QtCore.QTimer.singleShot(0, self._update_area_panel)
                
                elif isinstance(payload, str):
                    try:
                        parsed = json.loads(payload)
                        if isinstance(parsed, dict):
                            department_id = parsed.get('department_id')
                            data_count = parsed.get('data_count')
                            list_person = parsed.get('list_person', [])

                            if data_count:
                                effective_department_id = department_id
                                if not effective_department_id and self.all_cams:
                                    window_area = self.all_cams[0].get('area')
                                    if window_area and normalize_area_name(window_area) in ALLOWED_RECOGNITION_AREAS:
                                        effective_department_id = window_area

                                if effective_department_id:
                                    self.area_tracker.update_counts(effective_department_id, data_count, list_person)
                                    QtCore.QTimer.singleShot(0, self._update_area_panel)
                    except json.JSONDecodeError:
                        pass
            except Exception as e:
                print(f"[ERROR] Socket message handler error: {e}")
        
        try:
            self.socket_client = use_socket_statical(message_handler)
            self.socket_client.connect()
            # self.area_status_label.setText("Đã kết nối")
            # self.area_status_label.setStyleSheet("""
            #     QLabel {
            #         background-color: rgba(0, 150, 0, 150);
            #         color: white;
            #         font-size: 12px;
            #         padding: 5px;
            #         border: none;
            #     }
            # """)
        except Exception as e:
            print(f"[ERROR] Failed to initialize socket: {e}")
            self.area_status_label.setText("Lỗi kết nối")
            self.area_status_label.setStyleSheet("""
                QLabel {
                    background-color: rgba(150, 0, 0, 150);
                    color: white;
                    font-size: 12px;
                    padding: 5px;
                    border: none;
                }
            """)
    
    def _update_area_panel(self):
        """Update the area panel with current counts for this window's area only."""
        if not hasattr(self, 'area_layout'):
            return

        # Respect user's manual hide choice
        if self._panel_user_hidden:
            return

        # Detect window's area from first camera (more reliable than parsing group_name)
        window_area = None
        if self.all_cams:
            window_area = self.all_cams[0].get('area')
        
        # Panel only applies to specific areas
        if not window_area:
            self._hide_panel()
            return
        
        normalized_area = normalize_area_name(window_area)
        if normalized_area not in ALLOWED_RECOGNITION_AREAS:
            self._hide_panel()
            return
        
        # Hide panel if tracker is not available
        if not self.area_tracker:
            self._hide_panel()
            return
        
        # Get all area counts from tracker
        all_area_counts = self.area_tracker.get_area_counts()
        
        # Filter to only show this window's area
        counts = None
        if all_area_counts:
            for area_name, area_counts in all_area_counts.items():
                if normalize_area_name(area_name) == normalized_area:
                    counts = area_counts
                    break

        # If no live data yet, still show panel with zeros (for recognized areas)
        if not counts:
            counts = {
                "prisoner": 0,
                "officer": 0,
                "relative": 0,
                "list_person": [],
            }
        
        snapshot = self._build_panel_snapshot(counts)
        if snapshot == self._last_panel_snapshot:
            return

        self.area_panel.setUpdatesEnabled(False)
        try:
            # Clear existing area items
            while self.area_layout.count() > 1:  # Keep the stretch
                item = self.area_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            # Show panel and display this area's counts
            area_widget = self._create_area_item(self.group_name, counts)
            self.area_layout.insertWidget(self.area_layout.count() - 1, area_widget)

            # Display recognized persons if available
            list_person = counts.get('list_person', [])
            if list_person:
                # Add separator
                separator = QtWidgets.QFrame()
                separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
                separator.setStyleSheet("background-color: #ddd; max-height: 1px;")
                self.area_layout.insertWidget(self.area_layout.count() - 1, separator)
                
                # Add recognized persons section
                persons_label = QtWidgets.QLabel("NGƯỜI ĐƯỢC NHẬN DIỆN")
                persons_label.setStyleSheet("""
                    QLabel {
                        color: #FFA500;
                        font-size: 14px;
                        font-weight: bold;
                        background: transparent;
                        padding: 10px 5px 5px 5px;
                    }
                """)
                self.area_layout.insertWidget(self.area_layout.count() - 1, persons_label)
                
                # Display each person
                for person in list_person[:10]:  # Limit to 10 persons
                    person_widget = self._create_person_item(person)
                    self.area_layout.insertWidget(self.area_layout.count() - 1, person_widget)
        finally:
            self.area_panel.setUpdatesEnabled(True)

        self._last_panel_snapshot = snapshot
        self._show_panel()
    
    def _hide_panel(self):
        """Hide the area panel and adjust layout for full screen cameras."""
        if hasattr(self, 'area_panel'):
            self.area_panel.hide()
            self.panel_visible = False
            self._last_panel_snapshot = None
            # Recalculate layout without panel
            QtCore.QTimer.singleShot(10, self._layout_and_attach)
    
    def _show_panel(self):
        """Show the area panel and adjust layout."""
        if hasattr(self, 'area_panel'):
            self.area_panel.show()
            self.panel_visible = True
            # Recalculate layout with panel
            QtCore.QTimer.singleShot(10, self._layout_and_attach)
    
    def _create_area_item(self, area_name, counts):
        """Create a widget for displaying area counts - optimized for single area display."""
        widget = QtWidgets.QWidget()
        widget.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 255);
                border: 2px solid #FFA500;
                border-radius: 8px;
            }
        """)
        
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8)
        
        # Area name - larger and more prominent
        name_label = QtWidgets.QLabel(area_name)
        name_label.setStyleSheet("""
            QLabel {
                color: #FFA500;
                font-size: 22px;
                font-weight: bold;
                background: transparent;
                padding-bottom: 8px;
                border-bottom: 2px solid #FFA500;
            }
        """)
        name_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)
        
        # Counts - larger font for better visibility
        prisoner_label = QtWidgets.QLabel(f"👤 Can phạm: {counts['prisoner']:>5}")
        prisoner_label.setStyleSheet("""
            QLabel {
                color: "#7a99ff";
                font-size: 20px;
                font-weight: 500;
                background: transparent;
                padding: 5px;
            }
        """)
        layout.addWidget(prisoner_label)
        
        officer_label = QtWidgets.QLabel(f"👮 Cán bộ:     {counts['officer']:>6}")
        officer_label.setStyleSheet("""
            QLabel {
                color: #1dcb5f;
                font-size: 20px;
                font-weight: 500;
                background: transparent;
                padding: 5px;
            }
        """)
        layout.addWidget(officer_label)
        
        relative_label = QtWidgets.QLabel(f"👨‍👩‍👧 Khách:  {counts['relative']:>11}")
        relative_label.setStyleSheet("""
            QLabel {
                color: "#ffbc92";
                font-size: 20px;
                font-weight: 500;
                background: transparent;
                padding: 5px;
            }
        """)
        layout.addWidget(relative_label)
        
        # Total - more prominent
        total = counts['prisoner'] + counts['officer'] + counts['relative']
        total_label = QtWidgets.QLabel(f"📊 TỔNG:       {total:>5}")
        total_label.setStyleSheet("""
            QLabel {
                color: #FFA500;
                font-size: 22px;
                font-weight: bold;
                background: rgba(255, 200, 100, 100);
                border-top: 2px solid #FFA500;
                padding: 10px 5px;
                border-radius: 4px;
            }
        """)
        total_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(total_label)
        
        return widget
    
    def _create_person_item(self, person):
        """Create a widget for displaying a recognized person.

        If the person has not been identified (no subject_name or score == 0),
        only the captured face image is shown (larger, centred).
        Otherwise the full layout with face image, profile image, name and score is shown.
        """
        subject_name = person.get('subject_name', '')
        score = person.get('score', 0)
        is_identified = bool(subject_name) and score > 0

        widget = QtWidgets.QWidget()
        widget.setStyleSheet("""
            QWidget {
                background-color: rgba(240, 240, 240, 255);
                border: 2px solid #FFA500;
                border-radius: 5px;
                padding: 5px;
            }
        """)

        face_url = person.get('face_url', '')

        if not is_identified:
            # Unidentified: show only the captured face image, centred and larger
            layout = QtWidgets.QVBoxLayout(widget)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(6)
            layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

            face_label = QtWidgets.QLabel()
            face_label.setFixedSize(200, 200)
            face_label.setStyleSheet("""
                QLabel {
                    background-color: #ddd;
                    border: 2px solid #FFA500;
                    border-radius: 5px;
                }
            """)
            face_label.setScaledContents(True)
            face_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

            if face_url:
                full_url = IMAGE_BASE_URL + face_url if face_url.startswith('/') else urljoin(IMAGE_BASE_URL + '/', face_url)
                self._load_face_image(full_url, face_label)
            else:
                face_label.setText("📷")
                face_label.setStyleSheet("""
                    QLabel {
                        background-color: #ddd;
                        border: 2px solid #FFA500;
                        border-radius: 5px;
                        font-size: 36px;
                    }
                """)

            layout.addWidget(face_label, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

            unknown_label = QtWidgets.QLabel("Chưa xác định")
            unknown_label.setStyleSheet("""
                QLabel {
                    color: #555;
                    font-size: 15px;
                    font-weight: bold;
                    font-style: italic;
                    background: transparent;
                }
            """)
            unknown_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(unknown_label)

            return widget

        # Identified: full layout — face image | profile image + name
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Face image + score column
        face_column = QtWidgets.QVBoxLayout()
        face_column.setContentsMargins(0, 0, 0, 0)
        face_column.setSpacing(6)
        face_column.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        face_label = QtWidgets.QLabel()
        face_label.setFixedSize(130, 130)
        face_label.setStyleSheet("""
            QLabel {
                background-color: #ddd;
                border: 2px solid #FFA500;
                border-radius: 5px;
            }
        """)
        face_label.setScaledContents(True)
        face_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        if face_url:
            full_url = IMAGE_BASE_URL + face_url if face_url.startswith('/') else urljoin(IMAGE_BASE_URL + '/', face_url)
            self._load_face_image(full_url, face_label)
        else:
            face_label.setText("📷")
            face_label.setStyleSheet("""
                QLabel {
                    background-color: #ddd;
                    border: 2px solid #FFA500;
                    border-radius: 5px;
                    font-size: 24px;
                }
            """)
        face_column.addWidget(face_label)

        score_percent = int(score * 100)
        score_label = QtWidgets.QLabel(f"{score_percent}%")
        score_label.setFixedWidth(face_label.width())
        score_label.setStyleSheet("""
            QLabel {
                background-color: rgba(100, 100, 100, 200);
                color: white;
                font-size: 12px;
                font-weight: bold;
                padding: 4px 6px;
                border-radius: 3px;
                border: 2px solid #FFA500;
            }
        """)
        score_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        face_column.addWidget(score_label)
        layout.addLayout(face_column)

        # Profile image + name column
        profile_column = QtWidgets.QVBoxLayout()
        profile_column.setContentsMargins(0, 0, 0, 0)
        profile_column.setSpacing(6)
        profile_column.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        profile_label = QtWidgets.QLabel()
        profile_label.setFixedSize(face_label.size())
        profile_label.setStyleSheet("""
            QLabel {
                background-color: #ddd;
                border: 2px solid #FFA500;
                border-radius: 5px;
            }
        """)
        profile_label.setScaledContents(True)
        profile_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        csv_url = get_subject_image_url(subject_name)
        if csv_url:
            self._load_face_image(csv_url, profile_label)
        else:
            profile_label.setText("🖼️")
        profile_column.addWidget(profile_label)

        name_label = QtWidgets.QLabel(subject_name)
        name_label.setFixedWidth(face_label.width())
        name_label.setWordWrap(False)
        name_label.setStyleSheet("""
            QLabel {
                color: #333;
                font-size: 11px;
                font-weight: bold;
                background: transparent;
            }
        """)
        name_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        metrics = name_label.fontMetrics()
        elided = metrics.elidedText(subject_name, QtCore.Qt.TextElideMode.ElideRight, face_label.width() - 6)
        name_label.setText(elided)
        if elided != subject_name:
            name_label.setToolTip(subject_name)
        profile_column.addWidget(name_label)

        layout.addLayout(profile_column)

        return widget

    def _build_panel_snapshot(self, counts):
        """Return a lightweight representation of the panel to detect real changes."""
        persons = []
        for person in counts.get('list_person', [])[:10]:
            persons.append((
                person.get('subject_name') or '',
                person.get('face_url') or '',
                round(person.get('score', 0.0), 4)
            ))
        return (
            counts.get('prisoner', 0),
            counts.get('officer', 0),
            counts.get('relative', 0),
            tuple(persons)
        )

    def _load_face_image(self, full_url: str, face_label: QtWidgets.QLabel):
        """Load face image using shared network manager with caching to prevent flicker."""
        if not full_url:
            return
        
        # Use cached pixmap if available
        cached = self.image_cache.get(full_url)
        if cached and not cached.isNull():
            face_label.setPixmap(cached)
            return
        
        # Register label for pending update
        label_ref = weakref.ref(face_label)
        self.pending_image_labels[full_url].append(label_ref)
        face_label.destroyed.connect(
            lambda _=None, url=full_url, ref=label_ref: self._cleanup_pending_label(url, ref)
        )
        
        # Avoid duplicate requests
        if full_url in self.pending_requests:
            return
        
        self.pending_requests.add(full_url)
        request = QtNetwork.QNetworkRequest(QUrl(full_url))
        reply = self.network_manager.get(request)
        reply.finished.connect(lambda url=full_url, r=reply: self._handle_image_reply(url, r))

    def _handle_image_reply(self, url: str, reply: QtNetwork.QNetworkReply):
        """Handle network reply for image loading."""
        try:
            self.pending_requests.discard(url)
            if reply.error() == QtNetwork.QNetworkReply.NetworkError.NoError:
                data = reply.readAll()
                pixmap = QPixmap()
                if pixmap.loadFromData(data) and not pixmap.isNull():
                    self.image_cache[url] = pixmap
                    for label_ref in self.pending_image_labels.get(url, []):
                        label = label_ref()
                        if label:
                            try:
                                label.setPixmap(pixmap)
                            except RuntimeError:
                                pass
            else:
                print(f"[WARN] Failed to load image {url}: {reply.errorString()}")
        finally:
            reply.deleteLater()
            self.pending_image_labels.pop(url, None)

    def _cleanup_pending_label(self, url: str, label_ref: weakref.ReferenceType):
        """Remove label reference from pending list when label is destroyed."""
        refs = self.pending_image_labels.get(url)
        if not refs:
            return
        try:
            refs.remove(label_ref)
        except ValueError:
            pass
        if not refs and url not in self.pending_requests:
            self.pending_image_labels.pop(url, None)
    
    def _create_total_item(self, prisoner, officer, relative):
        """Create a widget for displaying total counts."""
        widget = QtWidgets.QWidget()
        widget.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 200, 100, 255);
                border: 2px solid #FFA500;
                border-radius: 5px;
            }
        """)
        
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        # Title
        title_label = QtWidgets.QLabel("TỔNG CỘNG TẤT CẢ KHU VỰC")
        title_label.setStyleSheet("""
            QLabel {
                color: #333;
                font-size: 14px;
                font-weight: bold;
                background: transparent;
            }
        """)
        layout.addWidget(title_label)
        
        # Counts
        prisoner_label = QtWidgets.QLabel(f"👤 Can phạm: {prisoner:>5}")
        prisoner_label.setStyleSheet("""
            QLabel {
                color: "#7a99ff";
                font-size: 12px;
                background: transparent;
            }
        """)
        layout.addWidget(prisoner_label)
        
        officer_label = QtWidgets.QLabel(f"👮 Cán bộ:     {officer:>6}")
        officer_label.setStyleSheet("""
            QLabel {
                color: #1dcb5f;
                font-size: 12px;
                background: transparent;
            }
        """)
        layout.addWidget(officer_label)
        
        relative_label = QtWidgets.QLabel(f"👨‍👩‍👧 Khách:  {relative:>11}")
        relative_label.setStyleSheet("""
            QLabel {
                color: "#ffbc92";
                font-size: 12px;
                background: transparent;
            }
        """)
        layout.addWidget(relative_label)
        
        total = prisoner + officer + relative
        total_label = QtWidgets.QLabel(f"📊 Tổng:       {total:>5}")
        total_label.setStyleSheet("""
            QLabel {
                color: #000;
                font-size: 15px;
                font-weight: bold;
                background: transparent;
                border-top: 2px solid #FFA500;
                padding-top: 5px;
            }
        """)
        layout.addWidget(total_label)
        
        return widget

    def _get_tile_map(self, view_mode: int):
        """Return tile boundaries for grid based on view_mode.

        Args:
            view_mode: Number of grid slots (1, 2, 4, 9, or 16).
                - 1: 1x1
                - 2: 1x2 (1 col, 2 rows)
                - 4: 2x2
                - 9: 3x3
                - 16: 4x4

        Returns:
            Dict mapping slot index to (x_start, y_start, x_end, y_end).
        """
        import math
        
        # Special case for view_mode=2 (1x2 layout: 1 column, 2 rows)
        if view_mode == 2:
            return {
                0: (0, 0, 1, 1),  # Top camera: col 0, row 0
                1: (0, 1, 1, 2),  # Bottom camera: col 0, row 1
            }
        
        # For other modes, use square grid (NxN)
        n = int(math.sqrt(view_mode))  # 1->1, 4->2, 9->3, 16->4
        tile_map = {}
        idx = 0
        for row in range(n):
            for col in range(n):
                tile_map[idx] = (col, row, col + 1, row + 1)
                idx += 1
        return tile_map

    def _layout_and_attach(self):
        """Set frame geometry based on tile map and re-attach persistent players."""
        screen = self.windowHandle().screen() if self.windowHandle() else QtWidgets.QApplication.primaryScreen()
        geom = screen.geometry()
        sw, sh = geom.width(), geom.height()
        
        # Calculate available width based on panel visibility
        if hasattr(self, 'panel_visible') and self.panel_visible:
            available_width = sw - PANEL_WIDTH
            panel_x = available_width
        else:
            available_width = sw
            panel_x = sw  # Panel is hidden, position it off-screen

        # Determine segments from tile_map
        max_x_seg = max(t[2] for t in self.tile_map.values())
        max_y_seg = max(t[3] for t in self.tile_map.values())
        x_bounds = compute_boundaries(available_width, max_x_seg)
        y_bounds = compute_boundaries(sh, max_y_seg)
        
        # Position area panel on the right (or off-screen if hidden)
        if hasattr(self, 'area_panel'):
            self.area_panel.setGeometry(panel_x, 0, PANEL_WIDTH, sh)
            if hasattr(self, 'panel_visible') and self.panel_visible:
                self.area_panel.raise_()

        # Set geometry for each frame and re-attach player to its frame
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

            # Re-attach persistent player to this frame's window handle
            player = self.players[idx] if idx < len(self.players) else None
            if player:
                set_player_window_for_platform(player, frame)

            if lbl:
                lbl.adjustSize()
                lbl.move(frame.x() + 8, frame.y() + frame.height() - lbl.height() - 8)
                lbl.raise_()

        # Position group label at top-right corner (adjust for panel)
        if self.group_label:
            self.group_label.adjustSize()
            self.group_label.move(available_width - self.group_label.width() - 20, 10)
            self.group_label.raise_()

        # Position time label at top center (adjust for panel)
        if self.time_label:
            self.time_label.adjustSize()
            self.time_label.move((available_width - self.time_label.width()) // 2, 10)
            self.time_label.raise_()

        # Position page label at bottom center
        if hasattr(self, 'page_label') and self.page_label.isVisible():
            self.page_label.adjustSize()
            self.page_label.move((available_width - self.page_label.width()) // 2, sh - self.page_label.height() - 15)
            self.page_label.raise_()

    def _update_time(self):
        """Update the time label with current time."""
        self.time_label.setText(datetime.now().strftime("%H:%M:%S %d/%m/%Y"))
        self.time_label.adjustSize()
        screen = self.windowHandle().screen() if self.windowHandle() else QtWidgets.QApplication.primaryScreen()
        sw = screen.geometry().width()
        # Adjust available width based on panel visibility
        if hasattr(self, 'panel_visible') and self.panel_visible:
            available_width = sw - PANEL_WIDTH
        else:
            available_width = sw
        self.time_label.move((available_width - self.time_label.width()) // 2, 10)
        self.time_label.raise_()

    def _monitor_players(self):
        """Check player status and update labels."""
        if self._rebuilding:
            return  # Skip monitoring during view rebuild
        screen = self.windowHandle().screen() if self.windowHandle() else QtWidgets.QApplication.primaryScreen()
        sw = screen.geometry().width()
        # Adjust available width based on panel visibility
        if hasattr(self, 'panel_visible') and self.panel_visible:
            available_width = sw - PANEL_WIDTH
        else:
            available_width = sw
        
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
                            self.group_label.move(available_width - self.group_label.width() - 20, 10)
                            self.group_label.raise_()
            else:
                if lbl:
                    lbl.setText(f"{cam.get('name','')}")
                    lbl.adjustSize()
                    lbl.raise_()
                    if self.group_label:
                        self.group_label.move(available_width - self.group_label.width() - 20, 10)
                        self.group_label.raise_()

    def _start_playback(self, idx):
        """Start or restart playback for a specific camera (uses persistent pool)."""
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

        # Also update the pool timestamp so monitor stays consistent
        cam_to_pool = {id(c): i for i, (_f, _l, c) in enumerate(self._cam_frames)}
        pool_idx = cam_to_pool.get(id(cam))
        if pool_idx is not None:
            self._cam_play_ts[pool_idx] = now

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

    def eventFilter(self, obj, event):
        """Intercept right-click on any camera QFrame and show context menu."""
        if event.type() == QtCore.QEvent.Type.MouseButtonPress:
            if event.button() == QtCore.Qt.MouseButton.RightButton:
                # Check if the object is one of our camera frames or filler frames
                is_cam_frame = any(obj is f for (f, _l, _c) in self._cam_frames)
                is_filler = any(obj is f for f in self._filler_frames)
                if is_cam_frame or is_filler:
                    global_pos = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
                    menu_event = QtGui.QContextMenuEvent(
                        QtGui.QContextMenuEvent.Reason.Mouse,
                        event.pos(),
                        global_pos,
                    )
                    self.contextMenuEvent(menu_event)
                    return True  # Event handled
        return super().eventFilter(obj, event)

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
        elif event.key() in (QtCore.Qt.Key.Key_Right, QtCore.Qt.Key.Key_PageDown):
            self._next_page()
        elif event.key() in (QtCore.Qt.Key.Key_Left, QtCore.Qt.Key.Key_PageUp):
            self._prev_page()
        elif event.key() == QtCore.Qt.Key.Key_1:
            self._change_view_mode(1)
        elif event.key() == QtCore.Qt.Key.Key_2:
            self._change_view_mode(2)
        elif event.key() == QtCore.Qt.Key.Key_3:
            self._change_view_mode(4)
        elif event.key() == QtCore.Qt.Key.Key_4:
            self._change_view_mode(9)
        elif event.key() == QtCore.Qt.Key.Key_5:
            self._change_view_mode(16)
        else:
            super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        """Show context menu on right-click with view mode selection and navigation."""
        menu_style = """
            QMenu {
                background-color: rgba(40, 40, 40, 230);
                color: white;
                border: 1px solid #FFA500;
                border-radius: 4px;
                padding: 4px;
                font-size: 14px;
            }
            QMenu::item {
                padding: 8px 24px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #FFA500;
                color: black;
            }
            QMenu::item:disabled {
                color: #666;
            }
            QMenu::separator {
                height: 1px;
                background: #555;
                margin: 4px 8px;
            }
        """
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(menu_style)

        # ---------- View mode submenu ----------
        view_menu = menu.addMenu("🖥️ Chế độ xem")
        view_menu.setStyleSheet(menu_style)
        mode_labels = {1: "1 cam (1×1)", 2: "2 cam (1×2)", 4: "4 cam (2×2)", 9: "9 cam (3×3)", 16: "16 cam (4×4)"}
        for mode in VIEW_MODES:
            label = mode_labels.get(mode, f"{mode} cam")
            if mode == self.view_mode:
                label = f"✔ {label}"
            action = view_menu.addAction(label)
            action.triggered.connect(lambda checked, m=mode: self._change_view_mode(m))

        # ---------- Page navigation ----------
        total_pages = self._total_pages()
        if total_pages > 1:
            menu.addSeparator()
            prev_action = menu.addAction(f"⬅️ Trang trước ({self.current_page}/{total_pages})")
            prev_action.setEnabled(self.current_page > 0)
            prev_action.triggered.connect(self._prev_page)

            next_action = menu.addAction(f"➡️ Trang sau ({self.current_page + 2}/{total_pages})")
            next_action.setEnabled(self.current_page < total_pages - 1)
            next_action.triggered.connect(self._next_page)

        # ---------- Toggle panel ----------
        normalized_group = normalize_area_name(self.group_name)
        if normalized_group in ALLOWED_RECOGNITION_AREAS:
            menu.addSeparator()
            if self._panel_user_hidden:
                panel_action = menu.addAction("📊 Hiện bảng nhận diện")
            else:
                panel_action = menu.addAction("📊 Ẩn bảng nhận diện")
            panel_action.triggered.connect(self._toggle_panel)

        # ---------- Camera selection ----------
        menu.addSeparator()
        cam_select_action = menu.addAction(f"📷 Chọn camera ({len(self.all_cams)}/{len(self._all_available_cameras)})")
        cam_select_action.triggered.connect(self._show_camera_select_dialog)

        # ---------- Area label toggle/rename ----------
        menu.addSeparator()
        if self.group_label and self.group_label.isVisible():
            label_toggle_action = menu.addAction("🏷️ Ẩn tên khu vực")
        else:
            label_toggle_action = menu.addAction("🏷️ Hiện tên khu vực")
        label_toggle_action.triggered.connect(self._toggle_group_label)

        rename_action = menu.addAction("✏️ Đổi tên khu vực")
        rename_action.triggered.connect(self._rename_group_label)

        # ---------- Stream mode toggle ----------
        menu.addSeparator()
        stream_menu = menu.addMenu("🎯 Chế độ luồng")
        stream_menu.setStyleSheet(menu_style)

        # "people_stream" option — shows checkmark when active
        ai_label = ("✔ " if STREAM_MODE == "people_stream" else "   ") + "Luồng AI"
        ai_action = stream_menu.addAction(ai_label)
        ai_action.triggered.connect(lambda: self._set_stream_mode("people_stream"))

        # "origin_url" option — shows checkmark when active
        origin_label = ("✔ " if STREAM_MODE == "origin_url" else "   ") + "📷 Luồng gốc"
        origin_action = stream_menu.addAction(origin_label)
        origin_action.triggered.connect(lambda: self._set_stream_mode("origin_url"))

        # ---------- Fullscreen toggle ----------
        menu.addSeparator()
        if self._fullscreen:
            fs_action = menu.addAction("🔲 Thoát toàn màn hình (Ctrl+F)")
        else:
            fs_action = menu.addAction("🔳 Toàn màn hình (Ctrl+F)")
        fs_action.triggered.connect(lambda: self.showNormal() if self._fullscreen else self.showFullScreen())
        fs_action.triggered.connect(lambda: setattr(self, '_fullscreen', not self._fullscreen))

        menu.exec(event.globalPos())

    def _toggle_group_label(self):
        """Toggle the area name label visibility."""
        if self.group_label:
            if self.group_label.isVisible():
                self.group_label.hide()
            else:
                self.group_label.show()
                self.group_label.raise_()

    def _rename_group_label(self):
        """Open input dialog to rename the area label."""
        current_name = self.group_name
        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Đổi tên khu vực",
            "Nhập tên mới:",
            QtWidgets.QLineEdit.EchoMode.Normal,
            current_name,
        )
        if ok and new_name.strip():
            self.group_name = new_name.strip()
            self.group_label.setText(self.group_name)
            self.group_label.adjustSize()
            self._update_window_title()
            # Re-position label after text resize
            screen = self.windowHandle().screen() if self.windowHandle() else QtWidgets.QApplication.primaryScreen()
            sw = screen.geometry().width()
            available_width = sw - PANEL_WIDTH if (hasattr(self, 'panel_visible') and self.panel_visible) else sw
            self.group_label.move(available_width - self.group_label.width() - 20, 10)
            self.group_label.raise_()

    def _set_stream_mode(self, mode: str):
        """
        Switch the global stream mode and restart all camera players with the new URL.

        Args:
            mode: "people_stream" or "origin_url"
        """
        global STREAM_MODE
        if mode == STREAM_MODE:
            return  # No change needed

        STREAM_MODE = mode
        mode_label = "Luồng AI (people_stream)" if mode == "people_stream" else "Luồng gốc (origin_url)"
        print(f"[INFO] Stream mode changed to: {STREAM_MODE}")

        # Update every camera in the persistent pool and restart its player
        for idx, (frame, lbl, cam) in enumerate(self._cam_frames):
            # Resolve new URL based on updated STREAM_MODE
            resolve_cam_url(cam)
            new_url = cam["url"]

            # Stop and recreate the VLC player with the new URL
            player = self._cam_players[idx] if idx < len(self._cam_players) else None
            if player is not None:
                try:
                    player.stop()
                    media = vlc.Media(new_url)
                    player.set_media(media)
                    player.play()
                    print(f"[INFO] Restarted cam '{cam.get('name', idx)}' → {new_url}")
                except Exception as exc:
                    print(f"[WARN] Failed to restart cam '{cam.get('name', idx)}': {exc}")

        # Show brief status message in the page label (visible for 3 s)
        if hasattr(self, 'page_label'):
            self.page_label.setText(f"🎯 {mode_label}")
            self.page_label.adjustSize()
            self.page_label.show()
            self.page_label.raise_()
            QtCore.QTimer.singleShot(3000, self._update_page_label)

    def _change_view_mode(self, new_mode: int):
        """Switch to a different view mode (1, 4, 9, 16) and rebuild the view."""
        if new_mode == self.view_mode:
            return
        self._rebuilding = True
        self.view_mode = new_mode
        # Clamp current page to valid range
        total_pages = self._total_pages()
        if self.current_page >= total_pages:
            self.current_page = total_pages - 1
        self._rebuild_view()
        # Short delay for Qt geometry update, then re-attach players (no restart needed)
        QtCore.QTimer.singleShot(50, self._finish_rebuild)
        # Start or stop auto-rotate based on new view mode
        self._update_auto_rotate()

    def _next_page(self):
        """Navigate to the next page of cameras."""
        if self.current_page < self._total_pages() - 1:
            self._rebuilding = True
            self.current_page += 1
            self._rebuild_view()
            QtCore.QTimer.singleShot(50, self._finish_rebuild)

    def _prev_page(self):
        """Navigate to the previous page of cameras."""
        if self.current_page > 0:
            self._rebuilding = True
            self.current_page -= 1
            self._rebuild_view()
            QtCore.QTimer.singleShot(50, self._finish_rebuild)

    def _finish_rebuild(self):
        """Called after rebuild delay to attach players and resume monitoring."""
        self._rebuilding = False
        self._layout_and_attach()

    def _auto_rotate_tick(self):
        """Auto-rotate to the next page in single-cam (1×1) view mode.

        Cycles back to page 0 after the last page.
        """
        if self.view_mode != 1:
            # Safety: stop timer if view mode changed unexpectedly
            self._auto_rotate_timer.stop()
            return
        total_pages = self._total_pages()
        if total_pages <= 1:
            return  # Nothing to rotate
        # Cycle to next page (wrap around)
        self._rebuilding = True
        self.current_page = (self.current_page + 1) % total_pages
        self._rebuild_view()
        QtCore.QTimer.singleShot(50, self._finish_rebuild)

    def _update_auto_rotate(self):
        """Start auto-rotate timer when in 1×1 view with multiple pages, stop otherwise."""
        if self.view_mode == 1 and self._total_pages() > 1:
            if not self._auto_rotate_timer.isActive():
                self._auto_rotate_timer.start()
        else:
            if self._auto_rotate_timer.isActive():
                self._auto_rotate_timer.stop()

    def _toggle_panel(self):
        """Toggle the recognition panel visibility based on user action."""
        if self._panel_user_hidden:
            self._panel_user_hidden = False
            self._update_area_panel()
        else:
            self._panel_user_hidden = True
            self._hide_panel()

    def _show_camera_select_dialog(self):
        """Open dialog to let user choose which cameras to display in this window."""
        dialog = CameraSelectDialog(
            all_cameras=self._all_available_cameras,
            selected_cams=self.all_cams,
            parent=self,
        )
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            selected = dialog.get_selected_cameras()
            if not selected:
                return  # Don't allow empty selection
            self._apply_camera_selection(selected)

    def _apply_camera_selection(self, new_cams: list):
        """Replace current camera list, reusing existing players where possible.

        - Cameras that remain selected keep their player alive (no reconnect).
        - Cameras that were removed get stopped and cleaned up.
        - New cameras get fresh players created.
        """
        # Stop auto-rotate while rebuilding
        if hasattr(self, '_auto_rotate_timer') and self._auto_rotate_timer.isActive():
            self._auto_rotate_timer.stop()

        self._rebuilding = True
        central = self.centralWidget()

        # Build lookup: url -> (index, frame, label, player, timestamp)
        old_by_url = {}
        for i, (f, lbl, cam) in enumerate(self._cam_frames):
            url = cam["url"]
            player = self._cam_players[i] if i < len(self._cam_players) else None
            ts = self._cam_play_ts[i] if i < len(self._cam_play_ts) else 0.0
            old_by_url[url] = (f, lbl, cam, player, ts)

        new_urls = {c["url"] for c in new_cams}

        # --- 1. Stop and remove cameras no longer selected ---
        for url, (f, lbl, cam, player, ts) in old_by_url.items():
            if url not in new_urls:
                if player:
                    try:
                        player.stop()
                    except Exception:
                        pass
                f.hide()
                f.removeEventFilter(self)
                f.setParent(None)
                f.deleteLater()
                if lbl:
                    lbl.hide()
                    lbl.setParent(None)
                    lbl.deleteLater()

        # --- 2. Build new pool in the order of new_cams ---
        new_cam_frames = []
        new_cam_players = []
        new_cam_play_ts = []

        for cam in new_cams:
            url = cam["url"]
            if url in old_by_url:
                # Reuse existing frame + player (no reconnect needed)
                f, lbl, _old_cam, player, ts = old_by_url[url]
                new_cam_frames.append((f, lbl, cam))
                new_cam_players.append(player)
                new_cam_play_ts.append(ts)
            else:
                # Create new frame + player for newly added camera
                f = QtWidgets.QFrame(central)
                f.setStyleSheet("background: transparent; border: 0px;")
                f.hide()
                f.installEventFilter(self)

                lbl = QtWidgets.QLabel(central)
                lbl.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                lbl.setStyleSheet("""
                    background: transparent;
                    color: #FFA500;
                    padding: 4px;
                    font-size: 14px;
                    text-shadow: 1px 1px 2px black;
                """)
                lbl.setText(cam.get('name', ''))
                lbl.adjustSize()
                lbl.hide()

                new_cam_frames.append((f, lbl, cam))

                try:
                    player = self.vlc_instance.media_player_new()
                    player.video_set_mouse_input(False)
                    player.video_set_key_input(False)
                    media = self.vlc_instance.media_new(cam["url"], VLC_OPTS)
                    player.set_media(media)
                    set_player_window_for_platform(player, f)
                    player.play()
                    new_cam_players.append(player)
                except Exception as e:
                    print(f"[ERROR] init player failed for {cam.get('name')}: {e}")
                    new_cam_players.append(None)
                new_cam_play_ts.append(time.time())

        # --- 3. Replace pool state ---
        self._cam_frames = new_cam_frames
        self._cam_players = new_cam_players
        self._cam_play_ts = new_cam_play_ts

        # Filler frames are reusable, keep them
        self.frames.clear()
        self.players.clear()
        self.last_play_attempts.clear()
        self.tile_map.clear()

        # --- 4. Update camera list ---
        self.all_cams = new_cams
        self.current_page = 0

        # Update window title with new camera names
        cam_names = [c.get("name", "") for c in new_cams]
        self.group_name = f"Window ({', '.join(cam_names)})"
        self._update_window_title()

        # --- 5. Rebuild view (just visibility + geometry, no player recreation) ---
        self._rebuild_view()

        # --- 6. Finish rebuild after short delay ---
        QtCore.QTimer.singleShot(100, self._finish_rebuild)

        # --- 7. Restart auto-rotate if applicable ---
        QtCore.QTimer.singleShot(150, self._update_auto_rotate)

        self._rebuilding = False

    def closeEvent(self, event):
        # Disconnect socket
        if self.socket_client:
            try:
                self.socket_client.disconnect()
            except Exception:
                pass
        
        # Stop ALL persistent pool players (not just the active page)
        for p in self._cam_players:
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

    total_cams = len(CAM_LIST)
    print(f"[INFO] Total cameras: {total_cams}")

    # Hardcoded 6-window layout definition
    # Note: B11 does not exist — using E11 (Khu vực Lao động, IP 192.168.22.168) for Window 6
    WINDOW_SPECS = [
        {"label": "Khu vực buồng giam 01", "cam_names": ["A11", "A12"], "view_mode": 2},
        {"label": "Khu vực hàng rào",       "cam_names": ["B12"],         "view_mode": 4},
        {"label": "Khu vực cổng trại",      "cam_names": ["D11", "D12"],  "view_mode": 4},
        {"label": "Khu vực căn tin",        "cam_names": ["H11"],         "view_mode": 4},
        {"label": "Khu vực thăm gặp",       "cam_names": ["G14"],         "view_mode": 4},
        {"label": "Khu vực lao động",       "cam_names": ["E11"],         "view_mode": 4},
    ]

    windows = []

    for i, spec in enumerate(WINDOW_SPECS):
        # Filter CAM_LIST by cam name, preserving spec order
        name_set = set(spec["cam_names"])
        name_order = {name: idx for idx, name in enumerate(spec["cam_names"])}
        cams = sorted(
            [cam for cam in CAM_LIST if cam.get("name") in name_set],
            key=lambda c: name_order.get(c.get("name", ""), 999)
        )

        if not cams:
            print(f"[WARN] Window {i+1} '{spec['label']}': no cameras found for {spec['cam_names']}, skipping.")
            continue

        print(f"[INFO] Window {i+1} '{spec['label']}': {[c.get('name') for c in cams]}")

        # Create window with area label and full camera list for selection dialog
        win = CustomLayoutWindow(cams, vlc_instance, spec["label"],
                                 all_available_cameras=CAM_LIST)
        win.view_mode = spec["view_mode"]

        # For view_mode 2 (buồng giam): rebuild layout and schedule panel update
        if spec["view_mode"] == 2:
            win._rebuild_view()
            QtCore.QTimer.singleShot(80, win._layout_and_attach)
            QtCore.QTimer.singleShot(120, win._update_area_panel)

        win.move(50 * i, 50 * i)
        win.show()
        windows.append(win)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()