"""Abre o Caissa.exe numa aba, espera a janela, captura por PrintWindow e fecha.

    python packaging/capturar_janela.py <aba> <saida.png> [segundos] [--menu Ferramentas] [--acao Configurações…]

Com `--menu`, abre o menu de nome dado (pela barra, com `Alt`+tecla) e captura o menu aberto;
com `--acao`, aciona o item de menu com esse texto e captura a janela que ele abre.
O `janela.json` ao lado do .exe recebe `active_tab` e volta ao que era ao fim.
"""

import argparse
import ctypes
import ctypes.wintypes as w
import json
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

EXE = Path(__file__).resolve().parents[1] / "dist" / "Caissa" / "Caissa.exe"
JANELA = EXE.parent / "data" / "janela.json"

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)


def janelas_do_processo(pid: int, minimo: int = 200):
    achadas = []

    def cb(hwnd, _):
        p = w.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd):
            n = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, n, 256)
            r = w.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            if r.right - r.left > minimo:
                achadas.append((hwnd, n.value, r))
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return achadas


class BMI(ctypes.Structure):
    _fields_ = [("biSize", w.DWORD), ("biWidth", w.LONG), ("biHeight", w.LONG), ("biPlanes", w.WORD),
                ("biBitCount", w.WORD), ("biCompression", w.DWORD), ("biSizeImage", w.DWORD),
                ("biXPelsPerMeter", w.LONG), ("biYPelsPerMeter", w.LONG), ("biClrUsed", w.DWORD),
                ("biClrImportant", w.DWORD)]


def capturar(hwnd, saida: Path) -> None:
    r = w.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    largura, altura = r.right - r.left, r.bottom - r.top
    hdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, largura, altura)
    gdi32.SelectObject(mdc, bmp)
    user32.PrintWindow(hwnd, mdc, 2)
    bmi = BMI(ctypes.sizeof(BMI), largura, -altura, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(largura * altura * 4)
    gdi32.GetDIBits(mdc, bmp, 0, altura, buf, ctypes.byref(bmi), 0)
    Image.frombuffer("RGBA", (largura, altura), buf, "raw", "BGRA", 0, 1).convert("RGB").save(saida)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)
    print(f"capturada {largura}x{altura} -> {saida}")


def tecla(vk: int, alt: bool = False) -> None:
    VK_MENU = 0x12
    if alt:
        user32.keybd_event(VK_MENU, 0, 0, 0)
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, 2, 0)
    if alt:
        user32.keybd_event(VK_MENU, 0, 2, 0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("aba")
    ap.add_argument("saida", type=Path)
    ap.add_argument("segundos", nargs="?", type=float, default=25.0)
    ap.add_argument("--menu", default="", help="letra do menu a abrir por Alt+letra (ex.: F de Ferramentas)")
    ap.add_argument("--acao", type=int, default=0, help="quantas setas para baixo ate o item; Enter abre")
    ap.add_argument("--paleta", default="", help="texto ASCII a digitar na paleta (Ctrl+Shift+P) e Enter")
    args = ap.parse_args()

    estado = json.loads(JANELA.read_text(encoding="utf-8"))
    original = estado.get("active_tab")
    estado["active_tab"] = args.aba
    JANELA.write_text(json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8")

    user32.SetProcessDPIAware()
    proc = subprocess.Popen([str(EXE)], cwd=str(EXE.parent))
    fim = time.time() + args.segundos
    hwnd = None
    while time.time() < fim:
        js = janelas_do_processo(proc.pid, 600)
        if js:
            hwnd = js[0][0]
        time.sleep(1.0)
    if hwnd is None:
        print("janela nao apareceu")
        proc.kill()
        return 1
    try:
        if args.paleta:
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.5)
            VK_CONTROL, VK_SHIFT, VK_RETURN = 0x11, 0x10, 0x0D
            user32.keybd_event(VK_CONTROL, 0, 0, 0)
            user32.keybd_event(VK_SHIFT, 0, 0, 0)
            tecla(ord("P"))
            user32.keybd_event(VK_SHIFT, 0, 2, 0)
            user32.keybd_event(VK_CONTROL, 0, 2, 0)
            time.sleep(1.0)
            for ch in args.paleta:
                tecla(ord(ch.upper()))
                time.sleep(0.05)
            time.sleep(0.8)
            paleta = [j for j in janelas_do_processo(proc.pid, 200) if j[0] != hwnd]
            if paleta:
                capturar(paleta[0][0], args.saida.with_name(args.saida.stem + "_paleta.png"))
            tecla(VK_RETURN)
            time.sleep(2.5)
            novas = [j for j in janelas_do_processo(proc.pid, 200) if j[0] != hwnd]
            capturar(novas[0][0] if novas else hwnd, args.saida)
        elif args.menu:
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.5)
            tecla(ord(args.menu.upper()), alt=True)
            time.sleep(0.8)
            if args.acao:
                VK_DOWN, VK_RETURN = 0x28, 0x0D
                for _ in range(args.acao):
                    tecla(VK_DOWN)
                    time.sleep(0.15)
                tecla(VK_RETURN)
                time.sleep(2.0)
                novas = [j for j in janelas_do_processo(proc.pid, 200) if j[0] != hwnd]
                alvo = novas[0][0] if novas else hwnd
                capturar(alvo, args.saida)
            else:
                capturar(hwnd, args.saida)
        else:
            capturar(hwnd, args.saida)
    finally:
        for h, _n, _r in janelas_do_processo(proc.pid, 200):
            user32.PostMessageW(h, 0x0010, 0, 0)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        estado = json.loads(JANELA.read_text(encoding="utf-8"))
        estado["active_tab"] = original
        JANELA.write_text(json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
