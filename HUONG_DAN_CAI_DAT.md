# Cài đặt và chuyển máy — Ghi Âm Zalo PC 2.8.0

1. Copy toàn bộ folder phát hành hoặc tải ZIP từ đám mây về máy mới; giải nén trước.
2. Chạy **Ghi-Am-Zalo-PC-2.8.0-Setup.exe**. Bộ cài có sẵn thành phần cần để chạy, không cần Python hoặc tải FFmpeg trên máy mới.
3. Chọn thư mục cài và shortcut Desktop rồi Install. Phần mềm cài cho tài khoản Windows hiện tại, không yêu cầu quyền quản trị.
4. Mở Ghi Âm Zalo PC. Trong Cài đặt, chọn đúng Micro và Loa/tai nghe đang dùng trong Zalo; kiểm tra nơi lưu bản ghi. Chọn Sáng hoặc Tối trong mục Giao diện.
5. Thử một cuộc gọi ngắn, mở Bản ghi để kiểm tra có tiếng cả hai bên. Nhận diện có thể khác giữa phiên bản Zalo và thiết bị âm thanh.

## Nâng cấp trên máy hiện tại

Dừng và lưu cuộc gọi trước. Chọn Thoát ứng dụng trong menu khay của bản cũ, sau đó chạy bộ cài. Bộ cài sẽ yêu cầu đóng ứng dụng nếu còn chạy; không ép tắt phiên ghi. Bản 2.8.0 lưu dữ liệu trong Data/ và Recordings/ bên cạnh EXE. Nếu nâng cấp từ bản cũ trên máy khác, hãy sao lưu và copy cài đặt/bản ghi cũ vào các thư mục này; sửa nơi lưu bản ghi trong Cài đặt. Các bản cũ nằm ở thư mục con phiên bản vẫn được giữ nguyên; dùng shortcut mới sau khi cài.

## Dữ liệu và gỡ cài đặt

- Cài đặt/nhật ký: `Data/` bên cạnh EXE.
- Bản ghi mặc định: `Recordings/` bên cạnh EXE; nếu đã đổi nơi lưu, xem đường dẫn trong Cài đặt.
- Source và bộ cài không chứa các dữ liệu này. Muốn chuyển bản ghi sang máy mới, copy riêng thư mục bản ghi, rồi chọn nó trong Cài đặt. Không bê nguyên cấu hình thiết bị cũ sang máy khác.
- Gỡ bằng Settings > Apps > Ghi Âm Zalo PC. Gỡ cài đặt giữ lại bản ghi và cấu hình.

## Nội dung gói

- Setup.exe: cài phần mềm.
- Source/: mã nguồn để sửa và phát triển; Source.zip: bản sao nén.
- SHA256SUMS.txt: mã kiểm tra bộ cài và source ZIP.
- HUONG_DAN_GITHUB.md: cách sao lưu và chia sẻ.

Bản hiện tại chưa ký chứng thư số; Windows có thể hiển thị Unknown publisher/SmartScreen. Chỉ chạy gói đúng nguồn và đối chiếu SHA256 bằng `Get-FileHash` nếu cần; không tắt phần mềm bảo vệ. Hỗ trợ Windows 10/11 x64; chưa kiểm thử máy ảo sạch hoặc mọi tai nghe/Bluetooth. Không cam kết tương thích macOS, Linux hay Windows 32-bit.
