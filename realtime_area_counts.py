"""
Real-time Area Counts Display
Hiển thị số lượng prisoner, officer, relative theo area theo thời gian thực
"""
import time
import json
import os
from collections import defaultdict
from hooks.use_socket import use_socket_statical
from department_mapping import get_department_info


class AreaCountTracker:
    """Theo dõi và hiển thị số lượng theo area"""
    
    def __init__(self):
        # Dictionary để lưu trữ counts theo department_id
        # Format: {department_id: {'prisoner': int, 'officer': int, 'relative': int}}
        self.dept_counts = {}
        self.last_update_time = None
        
    def update_counts(self, department_id, data_count):
        """
        Cập nhật counts cho một department
        
        Args:
            department_id: ID của department
            data_count: Dictionary chứa counts {'prisoner': int, 'officer': int, 'relative': int}
        """
        # Lưu counts theo department_id
        if data_count:
            self.dept_counts[department_id] = {
                'prisoner': data_count.get('prisoner', 0),
                'officer': data_count.get('officer', 0),
                'relative': data_count.get('relative', 0)
            }
        
        self.last_update_time = time.strftime('%H:%M:%S')
    
    def _aggregate_by_area(self):
        """
        Tổng hợp counts theo area từ tất cả departments
        
        Returns:
            Dictionary {area: {'prisoner': int, 'officer': int, 'relative': int}}
        """
        area_counts = defaultdict(lambda: {
            'prisoner': 0,
            'officer': 0,
            'relative': 0
        })
        
        # Duyệt qua tất cả departments và tổng hợp theo area
        for department_id, counts in self.dept_counts.items():
            dept_info = get_department_info(department_id)
            area = dept_info.get('area', '') if dept_info else ''
            
            # Nếu không có area, sử dụng department_id làm area
            if not area:
                area = f"UNKNOWN_AREA ({department_id[:8]}...)"
            
            # Cộng dồn counts vào area
            area_counts[area]['prisoner'] += counts['prisoner']
            area_counts[area]['officer'] += counts['officer']
            area_counts[area]['relative'] += counts['relative']
        
        return area_counts
        
    def display_counts(self):
        """Hiển thị counts theo area"""
        # Xóa màn hình (clear screen)
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print("=" * 80)
        print("REALTIME COUNTS BY AREA - SỐ LƯỢNG THEO KHU VỰC")
        print("=" * 80)
        
        if self.last_update_time:
            print(f"Cập nhật lần cuối: {self.last_update_time}")
        else:
            print("Đang chờ dữ liệu...")
        
        print("\n" + "-" * 80)
        
        # Tổng hợp counts theo area
        area_counts = self._aggregate_by_area()
        
        if not area_counts:
            print("Chưa có dữ liệu")
            return
        
        # Sắp xếp areas theo tên
        sorted_areas = sorted(area_counts.keys())
        
        # Tính tổng
        total_prisoner = 0
        total_officer = 0
        total_relative = 0
        
        # Hiển thị từng area
        for area in sorted_areas:
            counts = area_counts[area]
            prisoner = counts['prisoner']
            officer = counts['officer']
            relative = counts['relative']
            
            total_prisoner += prisoner
            total_officer += officer
            total_relative += relative
            
            print(f"\n{area}:")
            print(f"  👤 Prisoner (Phạm nhân): {prisoner:>5}")
            print(f"  👮 Officer (Cán bộ):     {officer:>5}")
            print(f"  👨‍👩‍👧 Relative (Thân nhân): {relative:>5}")
            print(f"  📊 Tổng:                 {prisoner + officer + relative:>5}")
        
        # Hiển thị tổng
        print("\n" + "=" * 80)
        print("TỔNG CỘNG TẤT CẢ KHU VỰC:")
        print(f"  👤 Prisoner (Phạm nhân): {total_prisoner:>5}")
        print(f"  👮 Officer (Cán bộ):     {total_officer:>5}")
        print(f"  👨‍👩‍👧 Relative (Thân nhân): {total_relative:>5}")
        print(f"  📊 Tổng:                 {total_prisoner + total_officer + total_relative:>5}")
        print("=" * 80)
        print("\nNhấn Ctrl+C để dừng...")


def message_handler(payload):
    """
    Xử lý message từ socket
    
    Args:
        payload: Payload từ socket server
    """
    try:
        # Xử lý payload
        if isinstance(payload, dict):
            department_id = payload.get('department_id')
            data_count = payload.get('data_count')
            
            if department_id and data_count:
                # Cập nhật counts
                tracker.update_counts(department_id, data_count)
                # Hiển thị lại
                tracker.display_counts()
        
        elif isinstance(payload, str):
            # Thử parse JSON string
            try:
                parsed = json.loads(payload)
                if isinstance(parsed, dict):
                    department_id = parsed.get('department_id')
                    data_count = parsed.get('data_count')
                    
                    if department_id and data_count:
                        tracker.update_counts(department_id, data_count)
                        tracker.display_counts()
            except json.JSONDecodeError:
                pass
    
    except Exception as e:
        print(f"\nLỗi xử lý message: {e}")


def main():
    """Hàm main"""
    global tracker
    
    print("Đang khởi tạo kết nối Socket.IO...")
    print("Đang kết nối đến server...")
    
    # Tạo tracker
    tracker = AreaCountTracker()
    
    # Tạo socket client
    client = use_socket_statical(message_handler)
    
    try:
        # Kết nối
        from hooks.use_socket import SOCKET_URL
        print(f"Kết nối đến: {SOCKET_URL}")
        client.connect()
        
        # Chờ kết nối
        time.sleep(2)
        
        if client.is_connected:
            print("✓ Kết nối thành công!")
            print("Đang lắng nghe dữ liệu...\n")
            time.sleep(1)
            
            # Hiển thị màn hình ban đầu
            tracker.display_counts()
            
            # Giữ kết nối và cập nhật realtime
            while True:
                time.sleep(0.5)  # Cập nhật mỗi 0.5 giây
        else:
            print("✗ Kết nối thất bại!")
    
    except KeyboardInterrupt:
        print("\n\nĐã dừng bởi người dùng")
    except Exception as e:
        print(f"\nLỗi: {e}")
    finally:
        client.disconnect()
        print("Đã ngắt kết nối")


if __name__ == "__main__":
    tracker = None
    main()

