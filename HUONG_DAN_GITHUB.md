# Đưa lên GitHub để sao lưu và chia sẻ

## Cách đơn giản qua website

1. Đăng nhập https://github.com, chọn **+ > New repository**.
2. Đặt tên `ghi-am-zalo-pc`. Chọn **Private** nếu chỉ sao lưu và dùng cá nhân, hoặc **Public** nếu muốn người khác xem/tải mã nguồn. Không chọn thêm README/.gitignore vì Source đã có.
3. Tạo repository. Chọn **uploading an existing file** (hoặc Add file > Upload files).
4. Mở thư mục **Source** của gói này, kéo các file và thư mục bên trong lên. Nhớ có cả `.gitignore`, assets, tests, packaging. Không kéo cả folder phát hành, file EXE, ZIP, bản ghi, settings hay nhật ký.
5. Ghi commit `Release 2.7.0: dark mode and installer`, chọn **Commit changes**. Kiểm tra main.py và README.md xuất hiện ngay ở thư mục gốc repository.
6. Vào **Releases > Draft a new release**; tạo tag `v2.7.0`, chọn nhánh chứa source vừa tải lên.
7. Đặt tiêu đề `Ghi Âm Zalo PC 2.7.0`. Đính kèm Setup.exe, Source.zip và SHA256SUMS.txt từ gói phát hành. Bấm **Publish release** khi đã kiểm tra xong.
8. Share link trang Release cho người tải phần mềm. Repository Private chỉ người được cấp quyền mới truy cập được; không cần đổi Public chỉ để chuyển sang máy khác của bạn.

## Khi cập nhật

Giữ một thư mục source chính để sửa. Sau mỗi thay đổi, kiểm thử, đóng gói rồi commit source mới và tạo tag/release mới (ví dụ v2.4.2). Giữ release cũ để quay lại khi có lỗi. Source ZIP chỉ là ảnh chụp một phiên bản; lịch sử Git giúp theo dõi từng lần sửa.

## Nếu dùng Git trên máy

Mở PowerShell trong thư mục Source. Tạo repository trống trên GitHub trước; thay URL mẫu bên dưới bằng URL thật:

```powershell
git init -b main
git add .
git commit -m "Release 2.7.0"
git remote add origin https://github.com/TEN_TAI_KHOAN/ghi-am-zalo-pc.git
git push -u origin main
```

Nếu Git yêu cầu tên/email, thiết lập bằng thông tin của bạn trước khi commit. Đăng nhập qua trình duyệt khi Git yêu cầu; không dán mật khẩu/token vào source hoặc README.

## Lưu ý khi phát hành công khai

Bộ cài có thành phần bên thứ ba. Giữ notices/licenses đi kèm; xem THIRD_PARTY.md để lấy nguồn gốc FFmpeg và các thư viện. Trước khi phân phối công khai rộng rãi, chuẩn bị đầy đủ mã nguồn tương ứng và điều kiện phân phối của các thành phần đi kèm, đặc biệt bản FFmpeg GPL. Chưa tự chọn giấy phép cho mã nguồn riêng của bạn.

Tài liệu chính thức:
- https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository
- https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository
- https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github

Chưa có nội dung nào được tự đăng lên tài khoản GitHub của bạn.
