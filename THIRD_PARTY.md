# Third-party components

The application runs FFmpeg as a separate executable. The bundled binary is copied unchanged from the installed Gyan FFmpeg distribution. Exact version/configuration: licenses/FFmpeg-version.txt. Original provider README and GPL license: licenses/FFmpeg-README.txt and licenses/FFmpeg-LICENSE.

- FFmpeg upstream source: https://git.ffmpeg.org/ffmpeg.git and https://github.com/FFmpeg/FFmpeg
- Windows build provider and source links: https://www.gyan.dev/ffmpeg/builds/
- FFmpeg licensing: https://ffmpeg.org/legal.html

Source/ in this package contains the recorder's own source, not the complete corresponding source of every bundled third-party binary. Preserve the included license notices. For public redistribution, obtain and distribute the corresponding source/build materials required by the applicable licenses (including FFmpeg's enabled dependencies); the links above are provenance references and are not a substitute for those obligations.

Other components: Python (PSF), Tcl/Tk, CustomTkinter (MIT), darkdetect (BSD), packaging, psutil (BSD), PyAudioWPatch/PortAudio, pystray (LGPL), Pillow, six (MIT), PyInstaller bootloader exception. Available installed license texts are copied into licenses/. Pinned build versions are recorded in requirements-lock.txt. No third-party authors endorse this application.
