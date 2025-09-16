import sys
from PyQt6 import QtWidgets, QtCore
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSize

import os
import time

# thêm đường dẫn chứa libvlc.dll
base_path = os.path.dirname(os.path.abspath(__file__))
os.add_dll_directory(base_path)

import vlc  # import sau khi add_dll_directory

LOG_FILE = "failed_cams.txt"

CAM_LIST = [
    {"url": "rtsp://192.168.22.5:38554/6385209cf41a711973ddb2bf_origin", "area": "KHU VỰC BUỒNG GIAM", "name": "A11"},
    {"url": "rtsp://192.168.22.5:38554/6385209cf41a711973ddb2bf_origin", "area": "KHU VỰC BUỒNG GIAM", "name": "A12"},
    {"url": "rtsp://192.168.22.5:38554/3f21870fc1e0a77d5e6abf9e_origin", "area": "KHU VỰC HÀNG RÀO PHÍA BẮC", "name": "B11"},
    {"url": "rtsp://192.168.22.5:38554/3f21870fc1e0a77d5e6abf9e_origin", "area": "KHU VỰC HÀNG RÀO PHÍA BẮC", "name": "B12"},
    {"url": "rtsp://192.168.22.5:38554/3f21870fc1e0a77d5e6abf9e_origin", "area": "KHU VỰC HÀNG RÀO PHÍA BẮC", "name": "B13"},
    {"url": "rtsp://192.168.22.5:38554/7966fe4435980970850a41e3_origin", "area": "KHU VỰC SOI CHIẾU THỦ CÔNG", "name": "C12"},
    {"url": "rtsp://192.168.22.5:38554/7966fe4435980970850a41e3_origin", "area": "KHU VỰC SOI CHIẾU THỦ CÔNG", "name": "C13"},
    {"url": "rtsp://admin:UNV123456%@192.168.22.88:554/ch01", "area": "KHU VỰC CỔNG TRẠI", "name": "D11"},
    {"url": "rtsp://192.168.22.5:38554/7d7da2895a68c864ec6ff55d_origin", "area": "KHU VỰC ĐIỂM DANH LAO ĐỘNG RA VÀO DOANH TRẠI", "name": "E11"},
    {"url": "rtsp://192.168.22.5:38554/7d7da2895a68c864ec6ff55d_origin", "area": "KHU VỰC ĐIỂM DANH LAO ĐỘNG RA VÀO DOANH TRẠI", "name": "E12"},
    {"url": "rtsp://192.168.22.5:38554/7d7da2895a68c864ec6ff55d_origin", "area": "KHU VỰC ĐIỂM DANH LAO ĐỘNG RA VÀO DOANH TRẠI", "name": "E13"},
    {"url": "rtsp://192.168.22.5:38554/8ababce1f3b51c3b12d017f0_origin", "area": "KHU VỰC THĂM GẶP", "name": "F11"},
    {"url": "rtsp://192.168.22.5:38554/8ababce1f3b51c3b12d017f0_origin", "area": "KHU VỰC THĂM GẶP", "name": "F12"}
]

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

AREAS = ["Tất cả"] + sorted(list({cam["area"] for cam in CAM_LIST}))

APP_STYLE = """
QWidget {
    font-family: "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 14px;
    background-color: #f5f5f7;
    color: #1d1d1f;
}
QLabel {
    color: #1d1d1f;
    font-weight: 500;
}
QComboBox, QSpinBox {
    border: 1px solid #c7c7cc;
    border-radius: 6px;
    padding: 4px 8px;
    background-color: white;
    min-height: 26px;
}
QComboBox::drop-down, QSpinBox::up-button, QSpinBox::down-button {
    width: 0px;
    border: none;
}
QComboBox::down-arrow, QSpinBox::up-arrow, QSpinBox::down-arrow {
    image: none;
    border: none;
    width: 0;
    height: 0;
}
QFrame#videoframe {
    border-radius: 0px;
    background-color: black;
}
"""

class CameraWidget(QtWidgets.QWidget):
    def __init__(self, parent=None, cam_name=""):
        super().__init__(parent)
        self.cam_name = cam_name
        self.full_window = None
        self.video_ratio = 16/9

        self.stack_layout = QtWidgets.QStackedLayout(self)
        self.stack_layout.setContentsMargins(0, 0, 0, 0)
        self.stack_layout.setSpacing(0)

        self.videoframe = QtWidgets.QFrame()
        self.videoframe.setObjectName("videoframe")
        self.videoframe.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.stack_layout.addWidget(self.videoframe)

        self.name_label = QtWidgets.QLabel(self.cam_name, self)
        self.name_label.setStyleSheet("color: white; font-size: 13px; background: rgba(0,0,0,0.6); padding: 4px;")
        self.name_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignTop)
        self.name_label.raise_()

        self.full_btn = QtWidgets.QPushButton("⛶", self)
        self.full_btn.setStyleSheet("background: transparent; color: white; font-size: 18px; border: none;")
        self.full_btn.setFixedSize(28, 28)
        self.full_btn.raise_()
        self.full_btn.clicked.connect(self.open_fullscreen)

        vlc_args = ["--network-caching=300", "--rtsp-tcp", "--no-xlib"]
        self.instance = vlc.Instance(vlc_args)
        self.player = self.instance.media_player_new()

    def resizeEvent(self, event):
        btn_size = self.full_btn.size()
        self.full_btn.move(self.width() - btn_size.width() - 6, self.height() - btn_size.height() - 6)
        self.name_label.move(self.width() - self.name_label.width() - 10, 6)
        super().resizeEvent(event)

    def play(self, url: str):
        if not url:
            return
        try:
            media = self.instance.media_new(url)
            self.player.set_media(media)
            if sys.platform.startswith("win"):
                self.player.set_hwnd(int(self.videoframe.winId()))
            elif sys.platform.startswith("linux"):
                self.player.set_xwindow(self.videoframe.winId())
            elif sys.platform.startswith("darwin"):
                self.player.set_nsobject(int(self.videoframe.winId()))
            self.player.play()
            QtCore.QTimer.singleShot(1200, self.update_video_ratio)
            QtCore.QTimer.singleShot(2500, self.update_video_ratio)
            QtCore.QTimer.singleShot(2000, lambda: self.check_stream(url))
        except Exception as e:
            self.log_failed(url, str(e))

    def update_video_ratio(self):
        try:
            w = self.player.video_get_width()
            h = self.player.video_get_height()
            if w and h:
                self.video_ratio = w / h
        except Exception:
            pass

    def stop(self):
        try:
            self.player.stop()
        except Exception:
            pass

    def check_stream(self, url):
        state = self.player.get_state()
        if state not in (vlc.State.Playing, vlc.State.Buffering):
            self.log_failed(url, f"VLC state: {state}")

    def log_failed(self, url, reason):
        print(f"[ERROR] Camera failed: {url} - {reason}")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {url} - {reason}\n")

    def open_fullscreen(self):
        if self.full_window is None:
            self.full_window = FullScreenWindow(self)
        self.full_window.showFullScreen()


class FullScreenWindow(QtWidgets.QMainWindow):
    def __init__(self, cam_widget):
        super().__init__()
        self.cam_widget = cam_widget
        self.full_videoframe = QtWidgets.QFrame()
        self.full_videoframe.setStyleSheet("background-color: black;")
        self.setCentralWidget(self.full_videoframe)

        if sys.platform.startswith("win"):
            self.cam_widget.player.set_hwnd(int(self.full_videoframe.winId()))
        elif sys.platform.startswith("linux"):
            self.cam_widget.player.set_xwindow(self.full_videoframe.winId())
        elif sys.platform.startswith("darwin"):
            self.cam_widget.player.set_nsobject(int(self.full_videoframe.winId()))

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Escape:
            if sys.platform.startswith("win"):
                self.cam_widget.player.set_hwnd(int(self.cam_widget.videoframe.winId()))
            elif sys.platform.startswith("linux"):
                self.cam_widget.player.set_xwindow(self.cam_widget.videoframe.winId())
            elif sys.platform.startswith("darwin"):
                self.cam_widget.player.set_nsobject(int(self.cam_widget.videoframe.winId()))
            self.close()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Movis VMS")
        self.resize(1600, 900)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        # VBoxLayout chính
        self.vbox = QtWidgets.QVBoxLayout(central)
        self.vbox.setContentsMargins(10, 10, 10, 10)
        self.vbox.setSpacing(15)

        # Control bar layout (luôn sát top)
        hbox = QtWidgets.QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(8)
        self.num_cam_spin = QtWidgets.QSpinBox()
        self.num_cam_spin.setRange(1, 16)
        self.num_cam_spin.setValue(min(16, len(CAM_LIST)))
        hbox.addWidget(QtWidgets.QLabel("Số camera hiển thị:"))
        hbox.addWidget(self.num_cam_spin)
        hbox.addStretch()
        self.area_combo = QtWidgets.QComboBox()
        self.area_combo.addItems(AREAS)
        hbox.addWidget(QtWidgets.QLabel("Khu vực:"))
        hbox.addWidget(self.area_combo)
        self.vbox.addLayout(hbox)

        # Grid camera layout ngay sát control bar
        self.grid = QtWidgets.QGridLayout()
        self.grid.setSpacing(0)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.vbox.addLayout(self.grid)

        # Thêm stretch để camera dồn lên trên
        self.vbox.addStretch()

        # Tạo các widget camera
        self.cams = []
        for cam_data in CAM_LIST:
            cam = CameraWidget(self, cam_name=cam_data["name"])
            self.cams.append(cam)

        self.num_cam_spin.valueChanged.connect(self.update_display)
        self.area_combo.currentIndexChanged.connect(self.update_display)

        self.play_all()
        self.update_display()

    def play_all(self):
        for cam, cam_data in zip(self.cams, CAM_LIST):
            cam.play(cam_data["url"])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QtCore.QTimer.singleShot(50, self.update_display)

    def update_display(self):
        num_to_show = min(self.num_cam_spin.value(), 6)  # giới hạn tối đa 6 cam
        self.num_cam_spin.setValue(num_to_show)

        selected_area = self.area_combo.currentText()
        filtered_indices = [i for i, cam_data in enumerate(CAM_LIST)
                            if selected_area == "Tất cả" or cam_data["area"] == selected_area]
        show_indices = filtered_indices[:num_to_show]

        # Xóa grid cũ
        for i in reversed(range(self.grid.count())):
            item = self.grid.itemAt(i)
            if item:
                widget = item.widget()
                if widget:
                    self.grid.removeWidget(widget)

        n = len(show_indices)
        if n == 0:
            return

        # --- Fix layout: 2 hàng × 3 cột ---
        rows, cols = 2, 3

        container_width = max(1, self.centralWidget().width() - (self.vbox.contentsMargins().left() + self.vbox.contentsMargins().right()))
        col_width = container_width // cols

        for r in range(rows):
            row_indices = [show_indices[r*cols + c] for c in range(cols) if r*cols + c < n]
            if not row_indices:
                continue
            # lấy tỉ lệ video max trong hàng để đồng bộ chiều cao
            ratios = [getattr(self.cams[i], "video_ratio", 16/9) for i in row_indices]
            max_ratio = max(ratios)
            row_height = int(col_width / max_ratio)

            for c_idx, cam_idx in enumerate(row_indices):
                cam = self.cams[cam_idx]
                cam.setVisible(True)
                cam.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
                cam.setFixedHeight(row_height)
                self.grid.addWidget(cam, r, c_idx)

        # Ẩn các cam không hiển thị
        for i, cam in enumerate(self.cams):
            if i not in show_indices:
                cam.setVisible(False)


def main():
    app = QtWidgets.QApplication(sys.argv)
    try:
        icon = QIcon()
        icon.addFile(resource_path("16.png"), QSize(16,16))
        icon.addFile(resource_path("32.png"), QSize(32,32))
        icon.addFile(resource_path("48.png"), QSize(48,48))
        icon.addFile(resource_path("64.png"), QSize(64,64))
        app.setWindowIcon(icon)
    except Exception:
        pass

    win = MainWindow()
    try:
        win.setWindowIcon(app.windowIcon())
    except Exception:
        pass

    app.setStyleSheet(APP_STYLE)
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
