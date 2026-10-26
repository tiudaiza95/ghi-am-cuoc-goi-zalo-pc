"""Dual-source Windows WASAPI audio recording, WAV/MP3 after explicit start."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import faulthandler
import json
import multiprocessing
import os
import queue
import shutil
import sys
import subprocess
import tempfile
import threading
import time
import wave
from array import array
import uuid
import psutil
from app_paths import app_root
from recording_names import recording_stem
from recording_library import atomic_json, read_json, unique_path, track_duration, live_owner

try:
    import pyaudiowpatch as pyaudio
except ImportError:
    pyaudio = None

OUTPUT_RATE = 48000
CHUNK_FRAMES = 1024
ENCODE_TIMEOUT = 600
STOP_TIMEOUT = 3


def find_ffmpeg():
    app_dir = app_root()
    bundled = app_dir / 'tools' / 'ffmpeg.exe'
    if bundled.is_file():
        return str(bundled)
    executable = shutil.which('ffmpeg')
    if executable:
        return executable
    packages = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Microsoft/WinGet/Packages'
    return next((str(p) for p in packages.glob('Gyan.FFmpeg_*/ffmpeg-*/bin/ffmpeg.exe')
                 if p.is_file()), None)


def write_status(path, data):
    temporary = path.with_suffix('.writing')
    temporary.write_text(json.dumps(data), encoding='utf-8')
    temporary.replace(path)


def capture_process(role, dev_index, target, stop_signal):
    """One PortAudio runtime per process; native crashes cannot kill the UI."""
    started, faults = {}, []
    status = target.with_suffix('.json')
    with target.with_suffix('.crash.log').open('w', encoding='utf-8') as crash_log:
        faulthandler.enable(file=crash_log)
        try:
            capture_track(role, dev_index, target, stop_signal, started, faults,
                          threading.Lock(), status)
        finally:
            write_status(status, {'started': started.get(role), 'faults': faults})
            faulthandler.disable()


def scan_devices():
    if pyaudio is None:
        raise RuntimeError('Chưa cài thư viện PyAudioWPatch.')
    pa = pyaudio.PyAudio()
    try:
        host = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        api_id = int(host['index'])
        microphones = [dict(d) for d in pa.get_device_info_generator()
                       if int(d.get('hostApi', -1)) == api_id and
                       d.get('maxInputChannels', 0) > 0 and not d.get('isLoopbackDevice', False)]
        speakers = [dict(d) for d in pa.get_loopback_device_info_generator()]
        if not microphones or not speakers:
            raise RuntimeError('Không tìm thấy cả micro và thiết bị phát WASAPI. Kiểm tra cài đặt âm thanh Windows.')
        try:
            mic_index = int(host['defaultInputDevice'])
        except Exception:
            mic_index = int(microphones[0]['index'])
        try:
            output_index = int(pa.get_default_wasapi_loopback()['index'])
        except Exception:
            output_index = int(speakers[0]['index'])
        return microphones, speakers, mic_index, output_index
    finally:
        pa.terminate()


def capture_track(role, dev_index, target, stop_signal, started, faults, lock, status=None):
    pa = None
    stream = None
    try:
        pa = pyaudio.PyAudio()
        dev = pa.get_device_info_by_index(dev_index)
        channels = min(2, int(dev['maxInputChannels']))
        sample_rate = int(dev['defaultSampleRate'])
        if channels < 1 or sample_rate < 1:
            raise RuntimeError('Thiết bị âm thanh không hỗ trợ định dạng yêu cầu.')
        with target.open('wb', buffering=0) as raw, wave.open(raw, 'wb') as f:
            f.setnchannels(channels)
            f.setsampwidth(2)
            f.setframerate(sample_rate)
            f.writeframes(b'')
            stream = pa.open(format=pyaudio.paInt16, channels=channels, rate=sample_rate,
                             input=True, input_device_index=dev_index, frames_per_buffer=CHUNK_FRAMES)
            with lock:
                started[role] = time.perf_counter()
            if status is not None:
                write_status(status, {'started': started[role], 'faults': []})
            frames_written = 0
            last_report = time.monotonic()
            peak = 0.0
            while not stop_signal.is_set():
                available = stream.get_read_available()
                if available > 0:
                    data = stream.read(min(CHUNK_FRAMES, available), exception_on_overflow=False)
                    f.writeframes(data)
                    frames_written += len(data) // (channels * 2)
                    samples = array('h', data)
                    peak = max(peak, max((abs(v) for v in samples), default=0) / 32768)
                else:
                    # WASAPI loopback supplies no packets when the endpoint is silent.
                    # Never wait in a blocking read for packets that may never arrive.
                    if role == 'speaker':
                        elapsed_frames = int((time.perf_counter() - started[role]) * sample_rate)
                        missing = elapsed_frames - frames_written - int(sample_rate * 0.1)
                        if missing > 0:
                            count = min(missing, CHUNK_FRAMES)
                            f.writeframes(b'\0' * (count * channels * 2))
                            frames_written += count
                    stop_signal.wait(0.01)
                now = time.monotonic()
                if status is not None and now - last_report >= 0.2:
                    try:
                        write_status(status, {'started': started[role], 'faults': [],
                                             'level': peak, 'updated': now})
                    except OSError:
                        pass  # A brief status-file conflict must not interrupt recording.
                    last_report, peak = now, 0.0
    except Exception as ex:
        with lock:
            faults.append(f'{role}: {ex}')
        stop_signal.set()
    finally:
        if stream is not None:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
        if pa is not None:
            pa.terminate()


def encode_audio(speaker_file, microphone_file, started, destination, kind, channel_mode='mixed', normalize=False):
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError('Không tìm thấy FFmpeg. Chạy: winget install -e --id Gyan.FFmpeg, rồi mở lại ứng dụng.')
    tracks = [(role, path) for role, path in (('speaker', speaker_file), ('microphone', microphone_file))
              if track_duration(path) > 0]
    if not tracks:
        raise RuntimeError('Không có nguồn âm thanh hợp lệ để lưu.')
    if any(not isinstance(started.get(role), (int, float)) or started.get(role, 0) <= 0 for role, _ in tracks):
        started = {role: 0 for role, _ in tracks}
    origin = min((started.get(role, 0) for role, _ in tracks), default=0)
    cmd = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-n']
    graph = []
    track_roles = [role for role, _ in tracks]
    for index, (role, path) in enumerate(tracks):
        cmd += ['-i', str(path)]
        delay = max(0, round(1000 * (started.get(role, origin) - origin)))
        graph.append(f'[{index}:a]aresample={OUTPUT_RATE},adelay={delay}:all=1[a{index}]')
    if len(tracks) == 2 and channel_mode == 'split':
        mic_idx = track_roles.index('microphone')
        spk_idx = track_roles.index('speaker')
        graph.append(f'[a{mic_idx}]aformat=channel_layouts=mono[mic_m]')
        graph.append(f'[a{spk_idx}]aformat=channel_layouts=mono[spk_m]')
        filter_parts = ['[mic_m][spk_m]amerge=inputs=2']
    elif len(tracks) == 2:
        filter_parts = ['[a0][a1]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0']
    else:
        filter_parts = ['[a0]']
    if normalize:
        if filter_parts == ['[a0]']:
            filter_parts = ['[a0]dynaudnorm=f=150:g=15']
        else:
            filter_parts.append('dynaudnorm=f=150:g=15')
    if filter_parts == ['[a0]']:
        filter_parts = ['[a0]alimiter=limit=0.95[out]']
    else:
        filter_parts.append('alimiter=limit=0.95[out]')
    graph.append(','.join(filter_parts))
    cmd += ['-filter_complex', ';'.join(graph), '-map', '[out]', '-ac', '2', '-ar', str(OUTPUT_RATE)]
    if kind == 'MP3':
        cmd += ['-c:a', 'libmp3lame', '-b:a', '192k']
    else:
        cmd += ['-c:a', 'pcm_s16le']
    destination = Path(destination)
    temporary = destination.with_name(f'.{uuid.uuid4().hex}.partial{destination.suffix}')
    cmd.append(str(temporary))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=ENCODE_TIMEOUT,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except subprocess.TimeoutExpired as ex:
        raise RuntimeError('FFmpeg quá thời gian xử lý; WAV gốc được giữ lại để khôi phục.') from ex
    if proc.returncode:
        raise RuntimeError('Không thể ghép âm thanh: ' + proc.stderr[-1300:])
    if not temporary.is_file() or temporary.stat().st_size <= 44:
        raise RuntimeError('FFmpeg không tạo ra tệp có dữ liệu.')
    if destination.exists():
        raise FileExistsError(f'Tệp đã tồn tại, không ghi đè: {destination}')
    temporary.rename(destination)


class AudioSession:
    def __init__(self, events: queue.Queue):
        self.events = events
        self.state = 'idle'
        self.recorded_from: float | None = None
        self.recording_file: Path | None = None
        self._context = multiprocessing.get_context('spawn')
        self._workers = []
        self._stop = self._context.Event()
        self._lock = threading.Lock()
        self._started: dict[str, float] = {}
        self._faults: list[str] = []
        self._temporary: Path | None = None
        self._file_kind = 'MP3'
        self._forced_workers = set()
        self.elapsed = 0.0
        self.levels = {'speaker': 0.0, 'microphone': 0.0}
        self._launch_time = None
        self.session_details = {}
        self._ended_at = None
        self._channel_mode = 'mixed'
        self._normalize = False

    def start(self, microphone: int, speaker: int, folder: Path, file_kind: str, caller_name: str = '',
              channel_mode: str = 'mixed', normalize: bool = False):
        if self.state != 'idle':
            return False
        if pyaudio is None:
            raise RuntimeError('Chưa cài PyAudioWPatch.')
        if not find_ffmpeg():
            raise RuntimeError('Không tìm thấy FFmpeg. Vui lòng mở lại ứng dụng sau khi cài FFmpeg.')
        folder.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(folder).free < 256 * 1024 * 1024:
            raise RuntimeError('Ổ lưu bản ghi còn dưới 256 MB. Hãy giải phóng dung lượng trước khi ghi.')
        self._storage_checked = 0.0
        temp = Path(tempfile.mkdtemp(prefix='zcc_temp_', dir=folder))
        self._temporary = temp
        self._stop = self._context.Event()
        self._started = {}
        self._faults = []
        self._forced_workers = set()
        self.elapsed = 0.0
        self.levels = {'speaker': 0.0, 'microphone': 0.0}
        self._file_kind = file_kind
        self._channel_mode = channel_mode
        self._normalize = normalize
        self._session_date = datetime.now()
        self._ended_at = None
        filename = recording_stem(caller_name, self._session_date)
        dest = folder / f'{filename}.{file_kind.lower()}'
        i = 2
        while dest.exists():
            dest = folder / f'{filename}_{i}.{file_kind.lower()}'
            i += 1
        self.recording_file = dest
        atomic_json(temp / 'session.json', {'pid': os.getpid(), 'process_created': psutil.Process().create_time(),
                    'active': True, 'destination': str(dest), 'format': file_kind,
                    'created': self._session_date.isoformat(),
                    'session_details': dict(self.session_details)})
        self._workers = [
            self._context.Process(name='speaker', target=capture_process,
                                  args=('speaker', speaker, temp / 'speaker.wav', self._stop)),
            self._context.Process(name='microphone', target=capture_process,
                                  args=('microphone', microphone, temp / 'microphone.wav', self._stop)),
        ]
        self.state = 'starting'
        self.recorded_from = None
        self._launch_time = time.monotonic()
        launched = []
        try:
            for worker in self._workers:
                worker.start()
                launched.append(worker)
        except Exception as ex:
            self._workers = launched
            with self._lock:
                self._faults.append(f'Không khởi động được luồng thu âm: {ex}')
            self.stop()
            return False
        self.events.put(('info', 'Đang mở micro và thiết bị phát trong tiến trình riêng...'))
        return True

    def set_caller_name(self, name):
        """Update the destination before saving, without restarting capture."""
        if not name or self.state not in ('starting', 'recording'):
            return
        stem = recording_stem(name, self._session_date)
        destination = self.recording_file.with_name(stem + self.recording_file.suffix)
        index = 2
        while destination.exists():
            destination = destination.with_name(f'{stem}_{index}{self.recording_file.suffix}')
            index += 1
        manifest = self._temporary / 'session.json'
        data = json.loads(manifest.read_text(encoding='utf-8'))
        data['destination'] = str(destination)
        atomic_json(manifest, data)
        self.recording_file = destination

    def stop(self):
        if self.state not in ('starting', 'recording'):
            return False
        self.elapsed = max(0, time.monotonic() - self.recorded_from) if self.recorded_from else 0
        self._ended_at = datetime.now().isoformat()
        if self._temporary:
            try:
                manifest_path = self._temporary / 'session.json'
                manifest = read_json(manifest_path)
                manifest['ended_at'] = self._ended_at
                atomic_json(manifest_path, manifest)
            except OSError as ex:
                self.events.put(('info', 'Không lưu được thời điểm kết thúc: ' + str(ex)))
        self.state = 'saving'
        self._stop.set()
        threading.Thread(target=self._complete, daemon=True).start()
        return True

    def error_if_any(self) -> str | None:
        self._read_worker_status()
        if self.state in ('starting', 'recording') and self._temporary and time.monotonic() - getattr(self, '_storage_checked', 0) >= 5:
            self._storage_checked = time.monotonic()
            try:
                if shutil.disk_usage(self._temporary).free < 128 * 1024 * 1024:
                    with self._lock:
                        warning = 'Dung lượng còn dưới 128 MB; dừng thu để lưu phần đã ghi.'
                        if warning not in self._faults:
                            self._faults.append(warning)
            except OSError as ex:
                with self._lock:
                    warning = 'Không truy cập được ổ lưu bản ghi: ' + str(ex)
                    if warning not in self._faults:
                        self._faults.append(warning)
        with self._lock:
            return '; '.join(self._faults) if self._faults else None

    def _read_worker_status(self):
        with self._lock:
            for worker in self._workers:
                role = worker.name
                if self._temporary is not None and isinstance(role, str):
                    try:
                        data = json.loads((self._temporary / f'{role}.json').read_text(encoding='utf-8'))
                        if data.get('started') is not None:
                            self._started[role] = data['started']
                        self.levels[role] = float(data.get('level', 0)) if time.monotonic() - data.get('updated', 0) < 1.5 else 0
                        for fault in data.get('faults', []):
                            if fault not in self._faults:
                                self._faults.append(fault)
                    except (OSError, ValueError):
                        pass
                code = worker.exitcode
                if isinstance(code, int) and code != 0 and role not in self._forced_workers:
                    fault = f'{role}: tiến trình thu âm bị lỗi (0x{code & 0xffffffff:08X}). WAV/log tạm: {self._temporary}'
                    if fault not in self._faults:
                        self._faults.append(fault)
                    self._stop.set()
            if self.state == 'starting' and len(self._started) == 2 and not self._faults:
                self.recorded_from = time.monotonic() - max(0, time.perf_counter() - min(self._started.values()))
                self.state = 'recording'
                self.events.put(('ready', 'Hai nguồn thu đã sẵn sàng.'))
            elif self.state == 'starting' and self._launch_time and time.monotonic() - self._launch_time > 15:
                if 'Quá thời gian mở thiết bị.' not in self._faults:
                    self._faults.append('Quá thời gian mở thiết bị.')

    def refresh(self):
        if self.state in ('starting', 'recording'):
            self._read_worker_status()

    def _save_tracks(self, temp, destination, kind, recovering=False):
        sources = {role: temp / f'{role}.wav' for role in ('speaker', 'microphone')}
        available = [role for role, path in sources.items() if track_duration(path) > 0]
        if not available:
            raise RuntimeError('Chưa thu được dữ liệu âm thanh. Hãy kiểm tra thiết bị.')
        incomplete = len(available) < 2 or bool(self._faults)
        label = ('Chỉ micro' if available == ['microphone'] else 'Chỉ loa') if len(available) == 1 else ('Không đầy đủ' if incomplete else 'Đủ hai nguồn')
        if incomplete:
            destination = destination.with_stem(destination.stem + ' - ' + label)
        destination = unique_path(destination)
        if getattr(self, '_channel_mode', 'mixed') != 'mixed' or getattr(self, '_normalize', False):
            encode_audio(sources['speaker'], sources['microphone'], self._started, destination, kind,
                         channel_mode=self._channel_mode, normalize=self._normalize)
        else:
            encode_audio(sources['speaker'], sources['microphone'], self._started, destination, kind)
        self.recording_file = destination
        duration = max(track_duration(sources[r]) for r in available)
        manifest = read_json(temp / 'session.json')
        details = manifest.get('session_details', {})
        ended_at = (manifest.get('ended_at') if recovering else self._ended_at)
        try:
            atomic_json(destination.with_suffix(destination.suffix + '.json'),
                        {'duration': duration, 'status': label, 'sources': available,
                         'created': datetime.now().isoformat(), 'recovered': recovering,
                         'started_at': manifest.get('created'), 'ended_at': ended_at,
                         'devices': details.get('devices', {}), 'purpose': details.get('purpose', 'call'),
                         'source_durations': {r: track_duration(sources[r]) for r in available},
                         'channel_mode': getattr(self, '_channel_mode', 'mixed'),
                         'normalized': getattr(self, '_normalize', False),
                         'warnings': list(self._faults)})
            manifest = read_json(temp / 'session.json')
            manifest.update(active=False, saved_to=str(destination), ended_at=ended_at)
            atomic_json(temp / 'session.json', manifest)
        except OSError as ex:
            self.events.put(('info', f'Đã lưu âm thanh, nhưng chưa lưu được thông tin bổ sung: {ex}'))
        if incomplete or recovering:
            self.events.put(('info', f'{label}. Giữ WAV gốc tại: {temp}'))
        else:
            shutil.rmtree(temp, ignore_errors=True)
        return destination

    def _complete(self):
        temp = self._temporary
        outcome = None
        try:
            deadline = time.monotonic() + STOP_TIMEOUT
            for worker in self._workers:
                worker.join(timeout=max(0, deadline - time.monotonic()))
            for worker in self._workers:
                if worker.is_alive():
                    self._forced_workers.add(worker.name)
                    worker.terminate()
                    worker.join(timeout=2)
                    self.events.put(('info', f'Đã yêu cầu kết thúc nguồn {worker.name} bị treo; lưu dữ liệu đã thu.'))
            if any(worker.is_alive() for worker in self._workers):
                self.state = 'blocked'
                self.events.put(('blocked', 'Thiết bị chưa dừng. Đang chờ giải phóng micro/loa; chưa thể ghi phiên mới.'))
                return
            self._read_worker_status()
            self._save_tracks(temp, self.recording_file, self._file_kind)
            outcome = ('saved', str(self.recording_file))
        except Exception as ex:
            outcome = ('error', f'{ex}\n\nTệp WAV tạm (nếu có): {temp}')
            if temp is not None:
                try:
                    manifest = read_json(temp / 'session.json')
                    manifest['active'] = False
                    atomic_json(temp / 'session.json', manifest)
                except OSError:
                    pass
        finally:
            if outcome is not None:
                self.recorded_from = None
                self.state = 'idle'
                self.events.put(outcome)

    def recover(self, temp, kind='MP3'):
        if self.state != 'idle':
            raise RuntimeError('Hãy chờ phiên hiện tại lưu xong.')
        temp = Path(temp)
        manifest = read_json(temp / 'session.json')
        if live_owner(manifest):
            raise RuntimeError('Phiên này đang được ứng dụng khác sử dụng.')
        if manifest.get('saved_to'):
            raise RuntimeError('Phiên này đã được lưu: ' + manifest['saved_to'])
        if not manifest:
            for proc in psutil.process_iter(['name', 'pid']):
                if proc.info['pid'] != os.getpid() and (proc.info['name'] or '').lower() == 'zalocallcompanion.exe':
                    # Old versions do not write a manifest, so do not recover while they may be writing.
                    try:
                        if proc.pid not in {p.pid for p in psutil.Process().parents()}:
                            raise RuntimeError('Hãy đóng các bản Companion cũ trước khi khôi phục phiên cũ.')
                    except psutil.NoSuchProcess:
                        pass
        self.state = 'saving'
        self._faults = []
        self.elapsed = 0
        self._started = {role: read_json(temp / f'{role}.json').get('started', 0) or 0 for role in ('speaker', 'microphone')}
        def complete_recovery():
            try:
                name = Path(manifest.get('destination', '')).stem or ('Khoi phuc - ' + temp.name)
                destination = temp.parent / (name + ' - Khoi phuc.' + kind.lower())
                result = self._save_tracks(temp, destination, kind, recovering=True)
                outcome = ('saved', str(result))
            except Exception as ex:
                outcome = ('error', f'Không khôi phục được: {ex}\nWAV gốc: {temp}')
            self.state = 'idle'
            self.events.put(outcome)
        threading.Thread(target=complete_recovery, daemon=True).start()

    def retry_completion(self):
        """Called by the UI poll; never reuse devices while old workers live."""
        if self.state == 'blocked' and not any(w.is_alive() for w in self._workers):
            self.state = 'saving'
            threading.Thread(target=self._complete, daemon=True).start()
