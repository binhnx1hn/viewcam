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
import weakref
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
VLC_OPTS = (
    ":network-caching=0 :live-caching=0 :file-caching=0 :disc-caching=0 :drop-late-frames :skip-frames"
)
PANEL_WIDTH = 350  # Width of the right-side panel for area counts
IMAGE_BASE_URL = "http://192.168.22.2:10000/movis_data"  # Base URL for face images

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
            
            # Nếu không có area, sử dụng department_id làm area
            if not area:
                area = f"UNKNOWN_AREA ({department_id[:8]}...)"
            
            # Cộng dồn counts vào area
            area_counts[area]['prisoner'] += counts['prisoner']
            area_counts[area]['officer'] += counts['officer']
            area_counts[area]['relative'] += counts['relative']
            
            # Tổng hợp list_person (chỉ lấy những người có subject_name, face_url, và score)
            if 'list_person' in counts:
                for person in counts['list_person']:
                    if (person.get('subject_name') and 
                        person.get('face_url') and 
                        person.get('score', 0) > 0):
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
        self.group_name = group_name  # Store group name for filtering area counts
        self.frames = []  # list of (frame, label, cam) or (frame, None, None) for black tile
        self.players = []  # vlc players (index-aligned to frames)
        self.last_play_attempts = [0.0] * max(4, num_cams)  # Track last play attempt per cam

        # Initialize area count tracker
        self.area_tracker = AreaCountTracker() if SOCKET_AVAILABLE else None
        self.socket_client = None
        self.panel_visible = False  # Track if panel should be visible (only when data exists)
        self.network_manager = QtNetwork.QNetworkAccessManager(self)
        self.image_cache = {}
        self.pending_image_labels = defaultdict(list)
        self.pending_requests = set()

        central = QtWidgets.QWidget()
        central.setContentsMargins(0, 0, 0, 0)
        central.setStyleSheet("background: transparent;")
        self.setCentralWidget(central)
        
        # Create right panel for area counts
        self._create_area_panel(central)
        
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

        # Initialize socket connection if available
        if SOCKET_AVAILABLE and self.area_tracker:
            self._init_socket()
        else:
            # Show status when socket is not available
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
            # Hide panel initially if no tracker
            self.panel_visible = False

        # Show fullscreen and layout
        QtCore.QTimer.singleShot(50, self.showFullScreen)
        QtCore.QTimer.singleShot(80, self._layout_and_attach)

        self._fullscreen = True

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
                font-size: 16px;
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
        
        # Initially hide the panel (will show when data is available)
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
                    
                    if department_id and data_count:
                        self.area_tracker.update_counts(department_id, data_count, list_person)
                        QtCore.QTimer.singleShot(0, self._update_area_panel)
                
                elif isinstance(payload, str):
                    try:
                        parsed = json.loads(payload)
                        if isinstance(parsed, dict):
                            department_id = parsed.get('department_id')
                            data_count = parsed.get('data_count')
                            list_person = parsed.get('list_person', [])
                            
                            if department_id and data_count:
                                self.area_tracker.update_counts(department_id, data_count, list_person)
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
        
        # Hide panel if tracker is not available
        if not self.area_tracker:
            self._hide_panel()
            return
        
        # Clear existing area items
        while self.area_layout.count() > 1:  # Keep the stretch
            item = self.area_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Get all area counts
        all_area_counts = self.area_tracker.get_area_counts()
        
        # Hide panel if no data at all
        if not all_area_counts:
            self._hide_panel()
            return
        
        # Filter to only show this window's area (group_name)
        current_area_counts = {}
        if self.group_name in all_area_counts:
            current_area_counts[self.group_name] = all_area_counts[self.group_name]
        
        # Hide panel if no data for this area
        if not current_area_counts:
            self._hide_panel()
            return
        
        # Show panel and display this area's counts
        counts = current_area_counts[self.group_name]
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
        
        self._show_panel()
    
    def _hide_panel(self):
        """Hide the area panel and adjust layout for full screen cameras."""
        if hasattr(self, 'area_panel'):
            self.area_panel.hide()
            self.panel_visible = False
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
                font-size: 16px;
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
                font-size: 14px;
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
                font-size: 14px;
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
                font-size: 14px;
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
                font-size: 16px;
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
        """Create a widget for displaying a recognized person with face image, name, and score."""
        widget = QtWidgets.QWidget()
        widget.setStyleSheet("""
            QWidget {
                background-color: rgba(240, 240, 240, 255);
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)
        
        # Face image
        face_label = QtWidgets.QLabel()
        face_label.setFixedSize(60, 60)
        face_label.setStyleSheet("""
            QLabel {
                background-color: #ddd;
                border: 2px solid #FFA500;
                border-radius: 5px;
            }
        """)
        face_label.setScaledContents(True)
        face_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        face_url = person.get('face_url', '')
        if face_url:
            # Construct full URL
            if face_url.startswith('/'):
                full_url = IMAGE_BASE_URL + face_url
            else:
                full_url = urljoin(IMAGE_BASE_URL + '/', face_url)
            self._load_face_image(full_url, face_label)
        else:
            # Placeholder if no image
            face_label.setText("📷")
            face_label.setStyleSheet("""
                QLabel {
                    background-color: #ddd;
                    border: 2px solid #FFA500;
                    border-radius: 5px;
                    font-size: 24px;
                }
            """)
        
        layout.addWidget(face_label)
        
        # Person info (name and score)
        info_layout = QtWidgets.QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(5)
        
        # Name
        name = person.get('subject_name', 'Unknown')
        name_label = QtWidgets.QLabel(name)
        name_label.setStyleSheet("""
            QLabel {
                color: #333;
                font-size: 13px;
                font-weight: bold;
                background: transparent;
            }
        """)
        name_label.setWordWrap(True)
        info_layout.addWidget(name_label)
        
        # Score
        score = person.get('score', 0)
        score_percent = int(score * 100) if score > 0 else 0
        score_label = QtWidgets.QLabel(f"{score_percent}%")
        score_label.setStyleSheet("""
            QLabel {
                background-color: rgba(100, 100, 100, 200);
                color: white;
                font-size: 12px;
                font-weight: bold;
                padding: 3px 8px;
                border-radius: 3px;
            }
        """)
        score_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(score_label)
        
        layout.addLayout(info_layout, 1)
        
        return widget

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

        # Position group label (adjust for panel)
        if self.group_label:
            self.group_label.move(available_width - self.group_label.width() - 20, 10)
            self.group_label.raise_()

        # Position time label at top center (adjust for panel)
        if self.time_label:
            self.time_label.adjustSize()
            self.time_label.move((available_width - self.time_label.width()) // 2, 10)
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
        # Disconnect socket
        if self.socket_client:
            try:
                self.socket_client.disconnect()
            except Exception:
                pass
        
        # Stop players
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