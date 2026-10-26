# Ghi Âm Zalo PC 2.8.0

Bản nâng cấp toàn diện các tính năng ghi âm chuyên nghiệp, quản trị dữ liệu và hỗ trợ AI:

1. **Ghi âm tách 2 kênh riêng biệt (Dual-Channel Split Audio)**:
   - Tùy chọn chế độ kênh: Trộn stereo thông thường (Mixed) hoặc Tách kênh chuyên nghiệp (Split: Mic bên Trái - FL, Người gọi bên Phải - FR).
   - Rất thuận tiện cho việc nghe lại từng bên, kiểm tra chất lượng âm thanh, bóc băng và lưu trữ pháp lý/chứng từ.

2. **Cân bằng âm lượng tự động (Volume Normalization)**:
   - Tích hợp bộ lọc âm thanh động thông minh (`dynaudnorm`) và bộ nén biên độ chống vỡ tiếng (`alimiter`).
   - Tự động khuếch đại giọng người nói nhỏ và hạ mức âm thanh quá to/hét, mang lại trải nghiệm nghe đồng đều, rõ ràng và êm tai.

3. **Phím tắt toàn cục nhanh (Global Hotkey Ctrl + Shift + R)**:
   - Bắt đầu/Dừng ghi âm tức thì bằng tổ hợp phím `Ctrl + Shift + R` từ bất kỳ cửa sổ nào trong Windows.
   - Sử dụng Win32 API native nhẹ nhàng, không chiếm tài nguyên hệ thống.

4. **Widget nổi thu nhỏ (Floating Mini Overlay)**:
   - Cửa sổ nổi nhỏ gọn luôn hiển thị trên cùng (Always-on-top) khi đang ghi âm.
   - Hiển thị chấm đỏ nhấp nháy, đồng hồ đếm giây thực tế, nút dừng ghi âm nhanh [■] và nút phóng to mở ứng dụng [↗].
   - Có thể kéo thả di chuyển đến bất kỳ góc nào trên màn hình làm việc.

5. **Tùy chỉnh tốc độ phát lại (Playback Speed Control)**:
   - Trình phát tích hợp cho phép chọn tốc độ phát linh hoạt: `0.75x`, `1.0x`, `1.25x`, `1.5x`, `2.0x`.
   - Tiết kiệm thời gian rà soát thông tin các cuộc gọi dài mà không cần dùng ứng dụng ngoài.

6. **Đánh dấu mốc thời gian & Ghi chú mốc (Audio Bookmarks / Timestamps)**:
   - Thêm mốc thời gian quan trọng ngay khi đang nghe bản ghi (`+ Đánh dấu mốc`).
   - Nhảy nhanh đến mốc thời gian chỉ với một cú nhấp chuột.
   - Dữ liệu mốc được lưu trữ tự động và an toàn trong metadata JSON đi kèm bản ghi.

7. **Tự động dọn dẹp bản ghi cũ theo chu kỳ (Retention Auto-Cleanup)**:
   - Thiết lập thời gian lưu trữ linh hoạt: Vĩnh viễn (mặc định), 30 ngày, 60 ngày hoặc 90 ngày.
   - Tự động dọn dẹp các bản ghi cũ khi khởi động ứng dụng giúp giải phóng dung lượng ổ cứng.

8. **Đồng bộ sao lưu thư mục thứ hai / Đám mây (Secondary / Cloud Backup Sync)**:
   - Tự động sao chép thêm một bản copy ngay khi hoàn tất lưu bản ghi vào thư mục thứ hai được chỉ định (như Google Drive, OneDrive, NAS, ổ đĩa ngoài).
   - Đảm bảo an toàn dữ liệu kép, chống mất mát thông tin.

9. **Tích hợp bóc băng tự động bằng Gemini AI (AI Audio Transcription)**:
   - Bóc băng cuộc gọi trực tiếp sang văn bản tiếng Việt sử dụng Gemini API (`gemini-2.5-flash`).
   - Hỗ trợ lưu trữ bản bóc băng vào metadata, xem lại trực tiếp trên giao diện Thư viện bản ghi.
   - Hướng dẫn nhập API Key an toàn trong phần Cài đặt.
