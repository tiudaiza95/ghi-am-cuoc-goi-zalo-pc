"""Build a self-contained Windows installer plus a clean source backup."""
from pathlib import Path
import hashlib
import importlib.metadata as metadata
import json
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from audio_engine import find_ffmpeg
VERSION = '2.4.0'


def run(args):
    subprocess.run([str(x) for x in args], cwd=ROOT, check=True)


def main():
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise SystemExit('Install FFmpeg first, or place it in tools/ffmpeg.exe.')
    compilers = [Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/Inno Setup 6/ISCC.exe',
                 Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Inno Setup 6/ISCC.exe']
    compiler = next((p for p in compilers if p.is_file()), None)
    if not compiler:
        raise SystemExit('Install Inno Setup 6: winget install -e --id JRSoftware.InnoSetup')
    run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-q'])
    run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--distpath', f'dist/{VERSION}', 'ZaloCallCompanion.spec'])
    payload = ROOT / 'release/payload'
    output = ROOT / f'release/Ghi-Am-Zalo-PC-{VERSION}'
    source = output / 'Source'
    for folder in [payload / 'tools', payload / 'licenses', output, source]:
        folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / f'dist/{VERSION}/ZaloCallCompanion.exe', payload)
    shutil.copy2(ffmpeg, payload / 'tools/ffmpeg.exe')
    ffmpeg_root = Path(ffmpeg).parent.parent
    for name in ['LICENSE', 'README.txt']:
        candidate = ffmpeg_root / name
        if not candidate.is_file():
            candidate = Path(ffmpeg).parent / name
        if not candidate.is_file():
            raise SystemExit(f'Missing FFmpeg {name}; keep the original provider license/readme alongside FFmpeg.')
        shutil.copy2(candidate, payload / 'licenses' / ('FFmpeg-' + name))
    info = subprocess.run([ffmpeg, '-version'], capture_output=True, text=True, check=True).stdout
    (payload / 'licenses/FFmpeg-version.txt').write_text(info, encoding='utf-8')
    versions = {}
    for package in ['customtkinter', 'darkdetect', 'packaging', 'psutil', 'PyAudioWPatch', 'pystray', 'Pillow', 'six', 'pyinstaller']:
        distribution = metadata.distribution(package)
        versions[package] = distribution.version
        target = payload / 'licenses' / package
        target.mkdir(exist_ok=True)
        for item in distribution.files or []:
            if any(word in item.name.lower() for word in ['license', 'copying', 'notice']):
                path = Path(distribution.locate_file(item))
                if path.is_file():
                    shutil.copy2(path, target / item.name)
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.is_file():
        shutil.copy2(python_license, payload / 'licenses/Python-LICENSE.txt')
    for item in (Path(sys.base_prefix) / 'tcl').glob('*/license.terms'):
        shutil.copy2(item, payload / 'licenses' / (item.parent.name + '-license.txt'))
    (ROOT / 'requirements-lock.txt').write_text('\n'.join(f'{k}=={v}' for k,v in versions.items()) + '\n', encoding='utf-8')
    for name in ['README.md', 'HUONG_DAN_CAI_DAT.md', 'HUONG_DAN_GITHUB.md', 'THIRD_PARTY.md']:
        shutil.copy2(ROOT / name, output)
        shutil.copy2(ROOT / name, payload)
    # Whitelist source files: never copy user settings, recordings or logs.
    for item in ROOT.iterdir():
        if item.is_file() and (item.suffix in {'.py', '.md', '.txt', '.bat', '.ps1', '.spec'} or item.name == '.gitignore'):
            shutil.copy2(item, source)
    for name in ['assets', 'tests', 'packaging']:
        for item in (ROOT / name).rglob('*'):
            if item.is_file() and '__pycache__' not in item.parts:
                destination = source / item.relative_to(ROOT)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, destination)
    source_zip = output / f'Ghi-Am-Zalo-PC-{VERSION}-Source.zip'
    with zipfile.ZipFile(source_zip, 'w', zipfile.ZIP_DEFLATED) as archive:
        for item in source.rglob('*'):
            if item.is_file():
                archive.write(item, Path('Source') / item.relative_to(source))
    run([compiler, ROOT / 'packaging/setup.iss'])
    checksums = []
    for path in sorted(output.iterdir()):
        if path.suffix in {'.exe', '.zip'}:
            checksums.append(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name)
    (output / 'SHA256SUMS.txt').write_text('\n'.join(checksums) + '\n', encoding='utf-8')
    bundle = output.parent / (output.name + '.zip')
    with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as archive:
        for item in output.rglob('*'):
            if item.is_file():
                archive.write(item, Path(output.name) / item.relative_to(output))
    print(f'RELEASE: {output}\nCLOUD BACKUP: {bundle}')


if __name__ == '__main__':
    main()
