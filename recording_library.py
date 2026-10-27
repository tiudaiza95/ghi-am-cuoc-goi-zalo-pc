"""Recording metadata, recovery discovery and safe local file operations."""
from datetime import datetime
from pathlib import Path
import json
import os
import re
import wave

import psutil
import subprocess


def read_json(path):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def atomic_json(path, data):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.writing')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def unique_path(path):
    path = Path(path)
    candidate, number = path, 2
    while candidate.exists():
        candidate = path.with_name(f'{path.stem}_{number}{path.suffix}')
        number += 1
    return candidate


def track_duration(path):
    try:
        with wave.open(str(path), 'rb') as wav:
            if wav.getnframes() < 1 or wav.getframerate() < 1:
                return 0.0
            # Do not mistake a header claiming frames for actual recorded data.
            if not wav.readframes(1):
                return 0.0
            return wav.getnframes() / wav.getframerate()
    except (OSError, EOFError, wave.Error):
        return 0.0


def live_owner(manifest):
    if manifest.get('active') is False:
        return False
    try:
        proc = psutil.Process(int(manifest['pid']))
        return abs(proc.create_time() - float(manifest['process_created'])) < 0.01
    except (KeyError, ValueError, TypeError, psutil.Error):
        return False


def recovery_candidates(folder):
    result = []
    for temp in Path(folder).glob('zcc_temp_*'):
        if not temp.is_dir():
            continue
        manifest = read_json(temp / 'session.json')
        if manifest.get('saved_to') or live_owner(manifest):
            continue
        if any(track_duration(temp / f'{role}.wav') for role in ('speaker', 'microphone')):
            result.append(temp)
    return sorted(result, key=lambda p: p.stat().st_mtime, reverse=True)


def list_recordings(folder):
    records = []
    for path in Path(folder).iterdir() if Path(folder).is_dir() else []:
        if not path.is_file() or path.suffix.lower() not in ('.mp3', '.wav') or '.partial.' in path.name:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue  # Another process may move a file during a refresh.
        metadata = read_json(path.with_suffix(path.suffix + '.json'))
        try:
            recorded_at = datetime.fromisoformat(metadata.get('started_at'))
        except (ValueError, TypeError):
            recorded_at = datetime.fromtimestamp(stat.st_mtime)
        duration = metadata.get('duration')
        try:
            duration = float(duration)
            if not __import__('math').isfinite(duration) or duration < 0:
                duration = None
        except (TypeError, ValueError, OverflowError):
            duration = track_duration(path) if path.suffix.lower() == '.wav' else None
        records.append({'path': path, 'name': path.name, 'size': stat.st_size,
                        'date': recorded_at.strftime('%d/%m/%Y %H:%M'),
                        'duration': duration, 'metadata': metadata,
                        'timestamp': recorded_at.isoformat(),
                        'status': metadata.get('status', 'Bản ghi cũ')})
    return sorted(records, key=lambda r: r['timestamp'], reverse=True)


def rename_recording(path, name):
    path = Path(path)
    name = name.strip()
    if not name or name in ('.', '..') or name.endswith(('.', ' ')) or len(name) > 160:
        raise ValueError('Tên tệp không hợp lệ hoặc quá dài.')
    if re.search(r'[<>:"/\\|?*\x00-\x1f]', name) or re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', name, re.I):
        raise ValueError('Tên chứa ký tự Windows không cho phép.')
    dest = path.with_name(name + path.suffix)
    if dest == path:
        return path
    if dest.exists():
        raise FileExistsError('Đã có bản ghi cùng tên.')
    path.rename(dest)
    sidecar = path.with_suffix(path.suffix + '.json')
    if sidecar.exists():
        try:
            sidecar.rename(dest.with_suffix(dest.suffix + '.json'))
        except OSError:
            dest.rename(path)
            raise
    return dest


def matches_date(record, period, now=None):
    from datetime import timedelta
    now = now or datetime.now()
    try:
        day = datetime.fromisoformat(record['timestamp']).date()
    except (ValueError, KeyError, TypeError):
        return period == 'Tất cả ngày'
    if period == 'Hôm nay':
        return day == now.date()
    if period == '7 ngày qua':
        return now.date() - timedelta(days=6) <= day <= now.date()
    if period == '30 ngày qua':
        return now.date() - timedelta(days=29) <= day <= now.date()
    return True


def session_description(path):
    data = read_json(Path(path).with_suffix(Path(path).suffix + '.json'))
    def stamp(value):
        try:
            return datetime.fromisoformat(value).strftime('%H:%M:%S • %d/%m/%Y')
        except (ValueError, TypeError):
            return 'Không có dữ liệu (bản cũ hoặc phiên bị gián đoạn)'
    devices = data.get('devices') or {}
    lines = [f"Bắt đầu: {stamp(data.get('started_at'))}",
             f"Kết thúc: {stamp(data.get('ended_at'))}",
             f"Micro: {devices.get('microphone', 'Chưa lưu thông tin')}",
             f"Loa / tai nghe: {devices.get('speaker', 'Chưa lưu thông tin')}",
             f"Nguồn thu: {data.get('status', 'Không có dữ liệu')}"]
    for role, duration in (data.get('source_durations') or {}).items():
        lines.append(f"{'Micro' if role == 'microphone' else 'Loa'}: {duration:.1f} giây")
    if data.get('warnings'):
        lines.append('Lưu ý: ' + '; '.join(data['warnings']))
    lines.append('Đủ hai nguồn nghĩa là có dữ liệu ở cả hai luồng, không đảm bảo cả hai đều có tiếng nói.')
    return '\n'.join(lines)


def search_key(text):
    import unicodedata
    value = unicodedata.normalize('NFD', str(text).casefold()).replace('đ', 'd')
    return ''.join(c for c in value if unicodedata.category(c) != 'Mn')


def update_record_metadata(path, **changes):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError('Bản ghi đã được di chuyển hoặc xóa.')
    sidecar = path.with_suffix(path.suffix + '.json')
    data = read_json(sidecar)
    # Preserve the recording date before creating metadata for a legacy file.
    data.setdefault('started_at', datetime.fromtimestamp(path.stat().st_mtime).isoformat())
    data.update(changes)
    atomic_json(sidecar, data)
    return data


def filter_records(records, query='', period='Tất cả ngày', starred=False, order='Mới nhất'):
    query = search_key(query.strip())
    items = [r for r in records if query in search_key(r['name'] + ' ' + str(r.get('metadata', {}).get('note', '')))
             and matches_date(r, period) and (not starred or r.get('metadata', {}).get('favorite') is True)]
    if order == 'Tên A–Z':
        return sorted(items, key=lambda r: search_key(r['name']))
    if order == 'Dài nhất':
        return sorted(items, key=lambda r: r.get('duration') or 0, reverse=True)
    return sorted(items, key=lambda r: r.get('timestamp', ''), reverse=order != 'Cũ nhất')


def filter_date_range(records, start='', end=''):
    def parse(value):
        try:
            return datetime.strptime(value.strip(), '%d/%m/%Y').date() if value.strip() else None
        except ValueError:
            raise ValueError('Ngày phải theo dạng DD/MM/YYYY, ví dụ 27/10/2026.') from None
    first, last = parse(start), parse(end)
    if first and last and first > last:
        raise ValueError('Ngày bắt đầu không được sau ngày kết thúc.')
    result = []
    for record in records:
        try:
            day = datetime.fromisoformat(record['timestamp']).date()
        except (ValueError, TypeError, KeyError):
            continue
        if (first is None or day >= first) and (last is None or day <= last):
            result.append(record)
    return result


def export_recordings_csv(records, destination):
    import csv
    import tempfile
    destination = Path(destination)
    def cell(value):
        value = str(value if value is not None else '')
        # Spreadsheet applications must treat user names and notes as text.
        return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8-sig', newline='',
                dir=destination.parent, suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            writer = csv.writer(stream)
            writer.writerow(['Tên bản ghi', 'Ngày ghi', 'Thời lượng (giây)', 'Dung lượng (byte)',
                             'Trạng thái', 'Quan trọng', 'Ghi chú'])
            for record in records:
                data = record.get('metadata', {})
                writer.writerow([cell(record['name']), cell(record.get('date')), record.get('duration'),
                    record.get('size'), cell(record.get('status')), 'Có' if data.get('favorite') else '',
                    cell(data.get('note'))])
        temporary.replace(destination)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def cleanup_old_recordings(folder, days):
    if not days or days <= 0:
        return 0
    from datetime import timedelta
    cutoff = datetime.now() - timedelta(days=days)
    deleted = 0
    folder = Path(folder)
    if not folder.is_dir():
        return 0
    for path in folder.iterdir():
        if not path.is_file() or path.suffix.lower() not in ('.mp3', '.wav'):
            continue
        sidecar = path.with_suffix(path.suffix + '.json')
        meta = read_json(sidecar)
        if meta.get('favorite') is True:
            continue
        try:
            ts = meta.get('started_at')
            dt = datetime.fromisoformat(ts) if ts else datetime.fromtimestamp(path.stat().st_mtime)
        except Exception:
            dt = datetime.fromtimestamp(path.stat().st_mtime)
        if dt < cutoff:
            try:
                path.unlink(missing_ok=True)
                sidecar.unlink(missing_ok=True)
                deleted += 1
            except OSError:
                pass
    return deleted


def add_timestamp_mark(path, seconds, label=''):
    path = Path(path)
    sidecar = path.with_suffix(path.suffix + '.json')
    data = read_json(sidecar)
    marks = data.setdefault('timestamps', [])
    sec = max(0.0, round(float(seconds), 1))
    tag = str(label).strip() or f'{int(sec//60):02d}:{int(sec%60):02d}'
    marks.append({'time': sec, 'label': tag})
    marks.sort(key=lambda m: m['time'])
    atomic_json(sidecar, data)
    return data


def remove_timestamp_mark(path, index):
    path = Path(path)
    sidecar = path.with_suffix(path.suffix + '.json')
    data = read_json(sidecar)
    marks = data.get('timestamps', [])
    if 0 <= index < len(marks):
        marks.pop(index)
        atomic_json(sidecar, data)
    return data


def trim_audio(source_path, start_seconds, end_seconds, destination_path=None):
    from audio_engine import find_ffmpeg
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError('Không tìm thấy FFmpeg.')
    source = Path(source_path)
    if not source.is_file():
        raise FileNotFoundError(f'Không tìm thấy file: {source_path}')
    start_seconds = max(0.0, float(start_seconds))
    end_seconds = float(end_seconds)
    if end_seconds <= start_seconds:
        raise ValueError('Thời gian kết thúc phải lớn hơn thời gian bắt đầu.')
    if destination_path is None:
        start_str = f'{int(start_seconds)}s'
        end_str = f'{int(end_seconds)}s'
        destination_path = source.with_name(f'{source.stem}_cut_{start_str}_{end_str}{source.suffix}')
    else:
        destination_path = Path(destination_path)
    cmd = [
        ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
        '-ss', str(start_seconds),
        '-to', str(end_seconds),
        '-i', str(source)
    ]
    if source.suffix.lower() == '.mp3':
        cmd += ['-c:a', 'libmp3lame', '-b:a', '192k']
    else:
        cmd += ['-c:a', 'pcm_s16le']
    cmd.append(str(destination_path))
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if proc.returncode != 0 or not destination_path.is_file():
        raise RuntimeError('Lỗi cắt âm thanh: ' + proc.stderr[-500:])
    return destination_path


def transcribe_with_gemini(api_key, path, model='gemini-3.1-flash-lite', task='transcribe'):
    import base64
    import urllib.request
    import urllib.error
    api_key = api_key.strip()
    if not api_key:
        raise ValueError('Chưa nhập Gemini API Key. Nhập key trong Cài đặt.')
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError('Không tìm thấy file âm thanh.')
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError('File âm thanh quá 20MB. Hãy chọn bản ghi ngắn hơn hoặc xuất MP3.')
    raw_bytes = path.read_bytes()
    b64 = base64.b64encode(raw_bytes).decode('ascii')
    mime = 'audio/mp3' if path.suffix.lower() == '.mp3' else 'audio/wav'
    if task == 'summary':
        prompt = (
            'Bạn là thư ký chuyên nghiệp. Hãy nghe bản ghi âm cuộc gọi này và thực hiện tóm tắt chi tiết bằng tiếng Việt theo định dạng sau:\n\n'
            '📌 TÓM TẮT NỘI DUNG CUỘC GỌI:\n'
            '- (3-5 gạch đầu dòng tóm tắt các vấn đề cốt lõi được thảo luận)\n\n'
            '✅ DANH SÁCH VIỆC CẦN LÀM (ACTION ITEMS):\n'
            '- (Các cam kết, nhiệm vụ, thời hạn, mốc hẹn gặp hoặc thanh toán nếu có)\n\n'
            '💡 ĐÁNH GIÁ THÁI ĐỘ / CẢM XÚC:\n'
            '- (Tích cực / Hợp tác / Bình thường / Căng thẳng kèm lý do ngắn gọn)'
        )
    else:
        prompt = (
            'Bạn là thư ký chuyên nghiệp. Hãy nghe bản ghi âm cuộc gọi này và bóc băng chi tiết toàn bộ nội dung hội thoại bằng tiếng Việt:\n'
            '- Ghi rõ vai người nói nếu phân biệt được (Người gọi / Người nhận hoặc Tên).\n'
            '- Kèm mốc thời gian nếu có.\n'
            'Trình bày rõ ràng, sạch sẽ, chuẩn xác.'
        )
    payload = {
        'contents': [{
            'parts': [
                {'text': prompt},
                {'inline_data': {'mime_type': mime, 'data': b64}}
            ]
        }]
    }
    req_data = json.dumps(payload).encode('utf-8')
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}'
    req = urllib.request.Request(url, data=req_data, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = json.loads(resp.read().decode('utf-8'))
            text = body['candidates'][0]['content']['parts'][0]['text']
            if task == 'summary':
                update_record_metadata(path, summary=text)
            else:
                update_record_metadata(path, transcription=text)
            return text
    except urllib.error.HTTPError as ex:
        err_msg = ex.read().decode('utf-8', errors='ignore')
        raise RuntimeError(f'Lỗi Gemini API ({ex.code}): {err_msg[:200]}') from ex
    except Exception as ex:
        raise RuntimeError(f'Không kết nối được Gemini API: {ex}') from ex
