# Hướng dẫn đóng gói multiplecam.py thành file .exe

## Yêu cầu

1. Python 3.8 trở lên
2. Cài đặt các thư viện cần thiết:
   ```bash
   pip install -r requirements.txt
   ```

## Cách build

### Cách 1: Sử dụng script tự động (Windows)

Chạy file `build_exe.bat`:
```bash
build_exe.bat
```

### Cách 2: Build thủ công

```bash
pyinstaller multiplecam.spec
```

Sau khi build xong, file `.exe` sẽ nằm trong thư mục `dist\multiplecam.exe`

## Triển khai

Khi triển khai file `.exe` lên máy khác, cần đảm bảo:

1. **File .exe** - File chính cần chạy
2. **Thư mục plugins/** - Chứa các plugin VLC (đã được đóng gói trong exe)
3. **File camera.json** - File cấu hình camera (có thể tạo mới hoặc chỉnh sửa)
4. **File department_mapping.json** - File mapping department (đã được đóng gói trong exe)

**Lưu ý**: File `.exe` đã được đóng gói tất cả các file cần thiết, bạn chỉ cần copy file `.exe` là có thể chạy được trên máy khác (không cần cài Python).

## Cấu hình

- File `camera.json`: Cấu hình danh sách camera
- File `department_mapping.json`: Mapping department ID với area (đã được đóng gói trong exe)

## Troubleshooting

### Lỗi thiếu DLL
Nếu gặp lỗi thiếu DLL khi chạy trên máy khác:
- Đảm bảo file `libvlc.dll` và `libvlccore.dll` đã được đóng gói (kiểm tra trong spec file)
- Có thể cần cài đặt Visual C++ Redistributable trên máy đích

### Lỗi không tìm thấy camera.json
- File `camera.json` sẽ được tạo tự động nếu không tìm thấy
- Hoặc bạn có thể tạo file này với cấu trúc tương tự như trong code

### Lỗi socket connection
- Kiểm tra kết nối mạng đến server socket
- Kiểm tra biến môi trường `VITE_INDENTIFY_WS` nếu cần thay đổi URL

