# Ghi Âm Zalo PC 2.9.0

Ứng dụng Windows ghi âm cuộc gọi Zalo chuyên nghiệp từ micro và âm thanh thiết bị phát. Tích hợp AI Gemini 3.1 Flash-Lite để bóc băng và tóm tắt cuộc gọi / việc cần làm, công cụ cắt gọt âm thanh trực tiếp, bộ lọc khử ồn môi trường, biểu đồ sóng âm trực quan, âm thanh báo hiệu trạng thái, widget nổi thu nhỏ, phím tắt toàn cục Ctrl+Shift+R, ghi âm tách 2 kênh (Mic/Loa), cân bằng âm lượng tự động, nghe lại tùy chỉnh tốc độ, đánh dấu mốc thời gian, tự dọn dẹp bản ghi cũ và sao lưu thư mục thứ hai/đám mây.

Đây là phần mềm độc lập, không phải sản phẩm chính thức của Zalo. Nhận diện cuộc gọi dựa trên cửa sổ, có thể bị ảnh hưởng khi Zalo cập nhật. Âm thanh phát từ ứng dụng khác trên cùng loa cũng có thể lọt vào bản ghi. Chỉ ghi khi các bên đã được thông báo và đồng ý theo yêu cầu áp dụng.

Chi tiết tính năng mới và kiểm thử: **PHIEN_BAN_2.9.0.md**.

## Sử dụng

Xem **HUONG_DAN_CAI_DAT.md**. Bộ cài dành cho Windows 10/11 x64, kèm Python runtime và FFmpeg. Không cần cài Python, không cần mạng trong lúc cài.

## Phát triển và sao lưu

- Source là mã nguồn ứng dụng; không phải thư mục chứa bản ghi cá nhân.
- Python 3.14 x64 đã được dùng để xây dựng bản này.
- Cài phụ thuộc: `py -3 -m pip install -r requirements-lock.txt`.
- Chạy kiểm thử: `py -3 -m unittest discover -s tests -q`.
- Chạy mã nguồn: `py -3 main.py`.
- Đóng gói: cài Inno Setup 6 và FFmpeg từ nguồn chính thức, rồi chạy `DONG_GOI_BO_CAI.bat`. Giữ LICENSE và README.txt gốc của bộ FFmpeg.
- Script `packaging/build_release.py` tạo bộ cài, source ZIP, checksum và ZIP tổng trong `release/`.
- Đưa source lên GitHub theo **HUONG_DAN_GITHUB.md**; đặt bộ cài vào Releases.

Mã nguồn của chủ dự án chưa được gán giấy phép phát hành công khai. Các thành phần bên thứ ba giữ giấy phép riêng, xem THIRD_PARTY.md và thư mục licenses của bản đã cài.
