"""Explicit hardware probe: open selected streams with start=False; never record."""
import json
import multiprocessing
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def probe(index):
    import pyaudiowpatch as pa
    engine = pa.PyAudio()
    try:
        device = engine.get_device_info_by_index(index)
        stream = engine.open(format=pa.paInt16, channels=min(2, int(device['maxInputChannels'])),
                             rate=int(device['defaultSampleRate']), input=True,
                             input_device_index=index, frames_per_buffer=1024, start=False)
        stream.close()
    finally:
        engine.terminate()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    settings = json.loads((Path(os.environ['APPDATA']) / 'ZaloCallCompanion/settings.json').read_text(encoding='utf-8'))
    indices = [int(settings[key].rsplit('[#', 1)[1].rstrip(']')) for key in ('microphone', 'speaker')]
    for attempt in range(3):
        workers = [multiprocessing.get_context('spawn').Process(target=probe, args=(index,)) for index in indices]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(15)
            if worker.is_alive():
                worker.terminate()
                worker.join(5)
                raise SystemExit('Device open timed out')
            if worker.exitcode:
                raise SystemExit(f'Device open failed: {worker.exitcode}')
            worker.close()
        print(f'Round {attempt + 1}: both devices opened and closed, no audio captured')
