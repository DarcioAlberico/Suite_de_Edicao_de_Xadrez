"""Abre o Caissa.exe numa aba, espera a janela, captura por PrintWindow e fecha.

    python capture_exe.py <aba> <saida.png> [segundos]
"""
import ctypes
import ctypes.wintypes as w
import json
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

EXE = Path(r"C:\Python-Chess2\Suite_de_Edicao_de_Xadrez\dist\Caissa\Caissa.exe")
JANELA = EXE.parent / "data" / "janela.json"
aba, saida = sys.argv[1], Path(sys.argv[2])
espera = float(sys.argv[3]) if len(sys.argv) > 3 else 25.0

estado = json.loads(JANELA.read_text(encoding="utf-8"))
original = estado.get("active_tab")
estado["active_tab"] = aba
JANELA.write_text(json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8")

proc = subprocess.Popen([str(EXE)], cwd=str(EXE.parent))
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
user32.SetProcessDPIAware()

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)


def janela_do_processo(pid: int):
    achada = []

    def cb(hwnd, _):
        p = w.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd):
            n = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, n, 256)
            r = w.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            if r.right - r.left > 600:
                achada.append((hwnd, n.value, r))
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return achada


fim = time.time() + espera
hwnd = None
while time.time() < fim:
    js = janela_do_processo(proc.pid)
    if js:
        hwnd, titulo, r = js[0]
    time.sleep(1.0)
if hwnd is None:
    print("janela nao apareceu"); proc.kill(); sys.exit(1)

r = w.RECT()
user32.GetWindowRect(hwnd, ctypes.byref(r))
largura, altura = r.right - r.left, r.bottom - r.top
hdc = user32.GetWindowDC(hwnd)
mdc = gdi32.CreateCompatibleDC(hdc)
bmp = gdi32.CreateCompatibleBitmap(hdc, largura, altura)
gdi32.SelectObject(mdc, bmp)
user32.PrintWindow(hwnd, mdc, 2)


class BMI(ctypes.Structure):
    _fields_ = [("biSize", w.DWORD), ("biWidth", w.LONG), ("biHeight", w.LONG), ("biPlanes", w.WORD),
                ("biBitCount", w.WORD), ("biCompression", w.DWORD), ("biSizeImage", w.DWORD),
                ("biXPelsPerMeter", w.LONG), ("biYPelsPerMeter", w.LONG), ("biClrUsed", w.DWORD),
                ("biClrImportant", w.DWORD)]


bmi = BMI(ctypes.sizeof(BMI), largura, -altura, 1, 32, 0, 0, 0, 0, 0, 0)
buf = ctypes.create_string_buffer(largura * altura * 4)
gdi32.GetDIBits(mdc, bmp, 0, altura, buf, ctypes.byref(bmi), 0)
img = Image.frombuffer("RGBA", (largura, altura), buf, "raw", "BGRA", 0, 1)
img.convert("RGB").save(saida)
print(f"capturada {largura}x{altura}: {titulo!r} -> {saida}")

user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
try:
    proc.wait(timeout=15)
except subprocess.TimeoutExpired:
    proc.kill()
estado = json.loads(JANELA.read_text(encoding="utf-8"))
estado["active_tab"] = original
JANELA.write_text(json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8")
