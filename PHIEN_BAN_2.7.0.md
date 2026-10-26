# Ghi Âm Zalo PC 2.7.0

- Lọc theo khoảng ngày tự chọn DD/MM/YYYY, kết hợp tìm kiếm và đánh dấu quan trọng. Để trống một đầu để lọc không giới hạn đầu đó. Khoảng ngày được áp dụng cùng bộ lọc nhanh đang chọn.
- Xuất danh sách đang hiển thị ra CSV UTF-8 có BOM để mở trong Excel, gồm tên, ngày, thời lượng, dung lượng, trạng thái, đánh dấu và ghi chú. Không xuất âm thanh hay đường dẫn cá nhân.
- Hạn chế lỗi thư viện khi file bị di chuyển trong lúc quét; dữ liệu thời lượng không hợp lệ không làm hỏng danh sách.
- CSV được ghi qua file tạm; tên và ghi chú được xử lý để tránh bị hiểu thành công thức bảng tính.

Chưa kiểm thử cuộc gọi Zalo thực tế sau cập nhật. Nhận diện cuộc gọi phụ thuộc giao diện Zalo.
