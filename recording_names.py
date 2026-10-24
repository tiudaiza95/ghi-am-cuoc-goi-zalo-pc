"""Conservative call-title parsing and Windows-safe recording filenames."""
import re
import unicodedata
from datetime import datetime


CALL_LABEL = r'(?:cuộc gọi(?: đến| đi| video| thoại)?|đang gọi(?: video| thoại)?|gọi video|gọi thoại|incoming call|outgoing call|video call|voice call|calling|zalo call)'


def caller_from_title(title: str) -> str:
    title = unicodedata.normalize('NFC', title).strip()
    title = re.sub(r'\s*[-–—|]\s*Zalo\s*$', '', title, flags=re.I)
    title = re.sub(r'^Zalo\s*[-–—|]\s*', '', title, flags=re.I)
    # Only strip complete UI labels at the edges, never words inside a name.
    match = re.match(rf'^{CALL_LABEL}\s*(?:[-–—|:]\s*|(?:với|từ|with|from|to)\s+)(.+)$', title, re.I)
    if match:
        candidate = match.group(1).strip()
    else:
        match = re.match(rf'^(.+?)\s*[-–—|]\s*{CALL_LABEL}$', title, re.I)
        candidate = match.group(1).strip() if match else ''
    if not candidate or re.fullmatch(rf'(?:Zalo|{CALL_LABEL}|đang kết nối|ringing)', candidate, re.I):
        return ''
    return candidate


def recording_stem(caller: str, when: datetime) -> str:
    name = unicodedata.normalize('NFC', caller)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', ' ', name)
    name = ''.join(c for c in name if unicodedata.category(c) != 'Cf')
    name = ' '.join(name.split()).strip(' .')[:80].rstrip(' .') or 'Zalo'
    if re.fullmatch(r'(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?', name, re.I):
        name = '_' + name
    return f'{name} - {when:%Hh%Mm%Ss - %d-%m-%Y}'
