"""Recording metadata, recovery discovery and safe local file operations."""
from datetime import datetime
from pathlib import Path
import json
import os
import re
import wave

import psutil


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
        metadata = read_json(path.with_suffix(path.suffix + '.json'))
        records.append({'path': path, 'name': path.name, 'size': path.stat().st_size,
                        'date': datetime.fromtimestamp(path.stat().st_mtime).strftime('%d/%m/%Y %H:%M'),
                        'duration': metadata.get('duration', track_duration(path) if path.suffix.lower() == '.wav' else None),
                        'status': metadata.get('status', 'Bản ghi cũ')})
    return sorted(records, key=lambda r: r['path'].stat().st_mtime, reverse=True)


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
