# Ghi Âm Zalo PC 2.9.0

Bản nâng cấp thế hệ mới tích hợp mô hình AI Gemini 3.1 Flash-Lite, công cụ biên tập âm thanh và cải tiến trải nghiệm người dùng:

1. **Tích hợp Gemini 3.1 Flash-Lite (`gemini-3.1-flash-lite`)**:
   - Sử dụng mô hình mới nhất của Google cho tốc độ xử lý nhanh vượt trội và độ chính xác nhận diện tiếng Việt cao.
   - Sẵn sàng sẵn API Key mặc định của người dùng, không cần cấu hình phức tạp.

2. **AI Tóm tắt cuộc gọi & Trích xuất việc cần làm (Action Items)**:
   - Nút **"Tóm tắt AI"** chuyên dụng trong Thư viện: Tự động phân tích hội thoại và trích xuất:
     * 📌 **Tóm tắt nội dung chính**: 3–5 gạch đầu dòng cốt lõi của cuộc gọi.
     * ✅ **Danh sách việc cần làm (Action Items)**: Lịch hẹn, cam kết, nhiệm vụ và thời hạn cần thực hiện.
     * 💡 **Đánh giá thái độ / Cảm xúc**: Nhận định không khí cuộc gọi (Tích cực / Hợp tác / Căng thẳng).
   - Tách biệt rõ ràng với chức năng **"Bóc băng AI"** (phiên âm toàn văn từng câu).

3. **Công cụ cắt gọt âm thanh trực tiếp (Audio Trimming & Cutter)**:
   - Nút **"✂ Cắt đoạn"** trong Thư viện bản ghi:
   - Cho phép chọn mốc bắt đầu [A] và kết thúc [B], có nút gán nhanh vị trí đang phát hiện tại.
   - Cắt tức thì bằng FFmpeg stream copy không làm suy hao chất lượng âm thanh gốc và lưu thành file bản ghi mới.

4. **Bộ lọc khử ồn môi trường tự động (Noise Suppression / De-noise)**:
   - Tích hợp bộ lọc âm học `afftdn=nf=-25` của FFmpeg.
   - Tự động khử tiếng quạt gió laptop, tiếng gõ bàn phím cơ và tiếng rè nền của micro.
   - Có công tắc Bật/Tắt linh hoạt trong mục Cài đặt.

5. **Biểu đồ sóng âm thanh trực quan (Visual Audio Waveform)**:
   - Tích hợp thanh sóng âm tương tác trực quan ngay trên trình phát lại.
   - Hiển thị mật độ âm thanh, đổi màu theo tiến độ phát (`#007AFF`) và hiển thị các mốc đánh dấu (Bookmark marker).
   - Cho phép nhấp chuột hoặc kéo thả trực tiếp trên thanh sóng để tua nhanh đến bất kỳ đoạn nào.

6. **Âm thanh báo hiệu (Audio Cues / Beep Notifications)**:
   - Phát tiếng bíp âm thanh nhẹ nhàng vào tai nghe khi bắt đầu ghi âm (2 tiếng bíp cao) và khi lưu xong (1 tiếng bíp trầm).
   - Giúp người dùng nắm chắc trạng thái ghi âm mà không cần nhìn vào màn hình máy tính.
   - Có công tắc Bật/Tắt trong Cài đặt.
