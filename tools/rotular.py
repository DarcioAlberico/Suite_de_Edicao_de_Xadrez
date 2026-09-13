"""Rotulagem de páginas digitalizadas — a bancada de verificação e treino (Sol §SOL-0/§SOL-11).

O que o FineReader chama de *verificação*: a página à esquerda com as regiões que o
layout achou (ou que você desenhou), e à direita, uma linha por vez — o recorte da
imagem, o que o motor leu com as palavras duvidosas destacadas, as leituras alternativas
dos outros candidatos, o motivo da dúvida e o campo onde a verdade é confirmada ou
digitada.  Cada decisão fica gravada com quem, quando e quanto tempo levou.

O que sai daqui (menu *Exportar*): itens ``pdf-scan`` para o manifesto dourado, as
correções no formato da fila de revisão, e a verdade por linha no formato que o
``lstmtraining`` consome.  *Treinar…* roda o ajuste fino do Tesseract sobre essa verdade
(``caissa.ocr.training``) e grava o modelo, o relatório e o registro de pesos.

    python tools/rotular.py [pasta_do_projeto] [--pdf livro.pdf] [--reviewer nome]

Sem argumentos abre ``labeling/`` na raiz do repositório.  Nenhum Qt aqui: é uma
ferramenta de bancada em Tk, separada do shell F9.
"""

from __future__ import annotations

import argparse
import json
import queue
import re
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from PIL import Image, ImageTk  # noqa: E402

from caissa.ocr.labeling import (  # noqa: E402
    LabelProject,
    LineLabel,
    LineStatus,
    PageLabels,
    RegionLabel,
)
from caissa.ocr.labeling.export import (  # noqa: E402
    calibration_pairs,
    corrections,
    manifest_items,
    merge_into_manifest,
    withheld_lines,
    write_ground_truth,
)
from caissa.ocr.labeling.recognise import (  # noqa: E402
    kinds_for_menu,
    label_page,
    page_count,
    page_size,
    recognise_rect,
    render_rgb,
)
from caissa.ocr.training import (  # noqa: E402
    FineTuneConfig,
    TesseractFineTuner,
    TrainingToolsError,
    download_base_model,
    find_training_tools,
    preflight,
)

DEFAULT_PROJECT = REPO_ROOT / "labeling"
DEFAULT_MANIFEST = REPO_ROOT / "benchmarks" / "corpus" / "golden" / "manifest.private.json"
DEFAULT_MODELS = REPO_ROOT / "models" / "tessdata"
DEFAULT_BEST = REPO_ROOT / "models" / "tessdata_best"

STATUS_COLOR = {
    LineStatus.PENDING: "#d97706",  # amber: still to look at
    LineStatus.ACCEPTED: "#16a34a",  # green
    LineStatus.EDITED: "#2563eb",  # blue
    LineStatus.REJECTED: "#9ca3af",  # grey: kept as image
}
REGION_COLOR = "#7c3aed"
SELECTED_COLOR = "#dc2626"
CLICK_SLOP_PX = 4
CROP_HEIGHT_PX = 90  # the line strip on the right, before it is scaled down
CROP_MAX_ZOOM = 3.0
WEAK_WORDS_SHOWN = 6
PAGE_CACHE_SIZE = 6  # rendered pages kept in memory, by (document, page, dpi)
FEN_RANKS = 8


class Worker:
    """One background thread at a time; results come back through ``after``."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.queue: queue.Queue[tuple[Any, Any]] = queue.Queue()
        self.busy = False
        self.root.after(60, self._poll)

    def run(self, fn: Any, done: Any) -> bool:
        if self.busy:
            return False
        self.busy = True

        def target() -> None:
            try:
                result = fn()
                self.queue.put((done, ("ok", result)))
            except Exception as exc:  # noqa: BLE001 - surfaced to the reviewer
                self.queue.put((done, ("error", exc)))

        threading.Thread(target=target, daemon=True).start()
        return True

    def _poll(self) -> None:
        try:
            while True:
                done, payload = self.queue.get_nowait()
                self.busy = False
                done(*payload)
        except queue.Empty:
            pass
        self.root.after(60, self._poll)


class LabelWindow:
    def __init__(self, root: tk.Tk, project: LabelProject) -> None:
        self.root = root
        self.project = project
        self.worker = Worker(root)
        self.service: Any = None
        self.document: str | None = None
        self.page_index = 0
        self.page: PageLabels | None = None
        self.current: tuple[RegionLabel, LineLabel] | None = None
        self.selected_region: RegionLabel | None = None
        self.scale = 1.6  # canvas px per point
        self.photo: ImageTk.PhotoImage | None = None
        self.crop_photo: ImageTk.PhotoImage | None = None
        self.page_cache: dict[tuple[str, int, int], Image.Image] = {}
        self.drawing = False
        self.drag_start: tuple[float, float] | None = None
        self.drag_item: int | None = None
        self.opened_at = 0.0
        self.only_doubtful = tk.BooleanVar(value=False)
        self.dpi_var = tk.IntVar(value=300)
        self.lang_var = tk.StringVar(value="por+eng")
        self.page_var = tk.StringVar(value="0")
        self._build()
        self._bind_keys()
        docs = sorted(project.documents)
        if docs:
            self._select_document(docs[0])
        self._refresh_status()

    # ------------------------------------------------------------------ UI --

    def _build(self) -> None:  # noqa: PLR0915 - one widget tree, laid out top to bottom
        root = self.root
        root.title(f"Rotulagem — {self.project.name}")
        root.geometry("1500x900")

        bar = ttk.Frame(root, padding=(6, 4))
        bar.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(bar, text="Adicionar PDF…", command=self.add_pdf).pack(side=tk.LEFT)
        ttk.Label(bar, text=" documento:").pack(side=tk.LEFT)
        self.doc_box = ttk.Combobox(
            bar, state="readonly", width=44, values=sorted(self.project.documents)
        )
        self.doc_box.pack(side=tk.LEFT, padx=(2, 8))
        self.doc_box.bind(
            "<<ComboboxSelected>>", lambda _e: self._select_document(self.doc_box.get())
        )
        ttk.Button(bar, text="◀", width=3, command=lambda: self.go_page(self.page_index - 1)).pack(
            side=tk.LEFT
        )
        entry = ttk.Entry(bar, textvariable=self.page_var, width=5, justify=tk.CENTER)
        entry.pack(side=tk.LEFT)
        entry.bind("<Return>", lambda _e: self.go_page(int(self.page_var.get() or 0)))
        self.page_total = ttk.Label(bar, text="/ 0")
        self.page_total.pack(side=tk.LEFT)
        ttk.Button(bar, text="▶", width=3, command=lambda: self.go_page(self.page_index + 1)).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Label(bar, text="DPI").pack(side=tk.LEFT)
        ttk.Spinbox(bar, from_=150, to=600, increment=50, textvariable=self.dpi_var, width=5).pack(
            side=tk.LEFT, padx=(2, 6)
        )
        ttk.Label(bar, text="idioma").pack(side=tk.LEFT)
        ttk.Combobox(
            bar,
            textvariable=self.lang_var,
            width=10,
            values=[
                "por+eng",
                "eng",
                "por",
                "spa+eng",
                "deu+eng",
                "rus+eng",
                "fra+eng",
                "ita+eng",
                "nld+eng",
            ],
        ).pack(side=tk.LEFT, padx=(2, 8))
        ttk.Button(bar, text="Reconhecer página (F5)", command=self.recognise_page).pack(
            side=tk.LEFT
        )
        self.draw_button = ttk.Button(bar, text="Desenhar região (D)", command=self.toggle_drawing)
        self.draw_button.pack(side=tk.LEFT, padx=(4, 8))
        ttk.Checkbutton(
            bar, text="só duvidosas", variable=self.only_doubtful, command=self._fill_tree
        ).pack(side=tk.LEFT)
        ttk.Button(bar, text="Aceitar confiáveis da página", command=self.accept_confident).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(bar, text="Treinar…", command=self.open_training).pack(side=tk.RIGHT)
        export = ttk.Menubutton(bar, text="Exportar")
        menu = tk.Menu(export, tearoff=False)
        menu.add_command(
            label="Verdade para treino (ground_truth/)", command=self.export_ground_truth
        )
        menu.add_command(label="Fundir no manifesto dourado…", command=self.export_manifest)
        menu.add_command(label="Correções e pares de calibração", command=self.export_corrections)
        menu.add_separator()
        menu.add_command(label="Idioma do documento = caixa «idioma»", command=self.apply_language)
        menu.add_command(label="Resumo do projeto", command=self.show_summary)
        export["menu"] = menu
        export.pack(side=tk.RIGHT, padx=(0, 6))
        ttk.Button(bar, text="Salvar (Ctrl+S)", command=self.save).pack(side=tk.RIGHT, padx=(0, 6))

        body = ttk.Panedwindow(root, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(body)
        body.add(left, weight=3)
        zoom_bar = ttk.Frame(left)
        zoom_bar.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(zoom_bar, text="−", width=3, command=lambda: self.zoom(1 / 1.25)).pack(
            side=tk.LEFT
        )
        ttk.Button(zoom_bar, text="+", width=3, command=lambda: self.zoom(1.25)).pack(side=tk.LEFT)
        ttk.Button(zoom_bar, text="Ajustar largura", command=self.fit_width).pack(
            side=tk.LEFT, padx=4
        )
        self.zoom_label = ttk.Label(zoom_bar, text="")
        self.zoom_label.pack(side=tk.LEFT, padx=8)
        self.canvas = tk.Canvas(left, background="#3f3f46", highlightthickness=0, cursor="arrow")
        vbar = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.canvas.yview)
        hbar = ttk.Scrollbar(left, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        hbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<ButtonPress-3>", self._on_right_click)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind(
            "<Shift-MouseWheel>",
            lambda e: self.canvas.xview_scroll(-1 if e.delta > 0 else 1, "units"),
        )
        self.canvas.bind(
            "<Control-MouseWheel>", lambda e: self.zoom(1.15 if e.delta > 0 else 1 / 1.15)
        )

        right = ttk.Frame(body, padding=(6, 2))
        body.add(right, weight=2)

        self.crop_label = tk.Label(right, background="#e5e7eb", anchor=tk.W)
        self.crop_label.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))
        self.context_label = ttk.Label(right, text="", foreground="#6b7280")
        self.context_label.pack(side=tk.TOP, anchor=tk.W)

        ttk.Label(right, text="Leitura do motor (palavras fracas em destaque):").pack(
            side=tk.TOP, anchor=tk.W
        )
        self.reading = tk.Text(
            right,
            height=2,
            wrap=tk.WORD,
            font=("Segoe UI", 12),
            state=tk.DISABLED,
            background="#f9fafb",
        )
        self.reading.tag_configure("weak", background="#fde68a")
        self.reading.tag_configure("bad", background="#fca5a5")
        self.reading.pack(side=tk.TOP, fill=tk.X)
        self.alternatives = tk.Listbox(right, height=3, font=("Segoe UI", 10), activestyle="none")
        self.alternatives.pack(side=tk.TOP, fill=tk.X, pady=(2, 0))
        self.alternatives.bind("<Double-Button-1>", self._use_alternative)
        self.reason_label = ttk.Label(right, text="", foreground="#b45309", wraplength=560)
        self.reason_label.pack(side=tk.TOP, anchor=tk.W)

        ttk.Label(
            right,
            text="Verdade (Enter aceita a leitura · Ctrl+Enter grava o que você digitou · "
            "Ctrl+R rejeita):",
        ).pack(side=tk.TOP, anchor=tk.W, pady=(4, 0))
        self.truth = tk.Text(right, height=3, wrap=tk.WORD, font=("Segoe UI", 13), undo=True)
        self.truth.pack(side=tk.TOP, fill=tk.X)
        self.truth.bind("<Return>", self._on_enter)
        self.truth.bind("<Control-Return>", self._on_ctrl_enter)
        self.truth.bind("<Control-r>", lambda _e: self.decide(LineStatus.REJECTED))
        self.truth.bind("<Control-z>", self._undo_line)
        self.truth.bind("<Control-Down>", lambda _e: self.step(1))
        self.truth.bind("<Control-Up>", lambda _e: self.step(-1))
        self.truth.bind("<Alt-Key-1>", lambda _e: self._use_alternative(index=0))
        self.truth.bind("<Alt-Key-2>", lambda _e: self._use_alternative(index=1))
        for key, glyph in FIGURINE_KEYS.items():
            self.truth.bind(f"<Alt-Key-{key}>", lambda _e, g=glyph: self.insert_figurine(g))

        # The figurine palette: what the truth must carry for the Tesseract
        # fine-tune to learn ♔♕♖♗♘♙ (its alphabet is extended from the truth).
        palette = ttk.Frame(right)
        palette.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(palette, text="Figurinas:").pack(side=tk.LEFT)
        for key, glyph in FIGURINE_KEYS.items():
            ttk.Button(
                palette,
                text=f"{glyph} (Alt+{key.upper()})",
                width=9,
                command=lambda g=glyph: self.insert_figurine(g),
            ).pack(side=tk.LEFT, padx=1)
        ttk.Button(palette, text="Letras → figurinas", command=self.letters_to_figurines).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        buttons = ttk.Frame(right)
        buttons.pack(side=tk.TOP, fill=tk.X, pady=4)
        ttk.Button(
            buttons, text="Aceitar leitura", command=lambda: self.decide(LineStatus.ACCEPTED)
        ).pack(side=tk.LEFT)
        ttk.Button(
            buttons, text="Gravar edição", command=lambda: self.decide(LineStatus.EDITED)
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(
            buttons, text="Rejeitar (imagem)", command=lambda: self.decide(LineStatus.REJECTED)
        ).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Desfazer decisão", command=self._undo_line).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(buttons, text="◀ anterior", command=lambda: self.step(-1)).pack(side=tk.RIGHT)
        ttk.Button(buttons, text="próxima ▶", command=lambda: self.step(1)).pack(
            side=tk.RIGHT, padx=4
        )

        columns = ("n", "regiao", "estado", "conf", "texto")
        self.tree = ttk.Treeview(right, columns=columns, show="headings", selectmode="browse")
        for col, title, width in (
            ("n", "#", 40),
            ("regiao", "reg.", 40),
            ("estado", "estado", 80),
            ("conf", "conf.", 50),
            ("texto", "texto", 420),
        ):
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, stretch=(col == "texto"), anchor=tk.W)
        for status, color in STATUS_COLOR.items():
            self.tree.tag_configure(status.value, foreground=color)
        self.tree.tag_configure("doubt", font=("Segoe UI", 9, "bold"))
        tree_bar = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_bar.set)
        tree_bar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        self.status = ttk.Label(root, text="", anchor=tk.W, padding=(6, 3), relief=tk.SUNKEN)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    def _bind_keys(self) -> None:
        root = self.root
        root.bind("<F5>", lambda _e: self.recognise_page())
        root.bind("<Control-s>", lambda _e: self.save())
        root.bind("<Prior>", lambda _e: self.go_page(self.page_index - 1))
        root.bind("<Next>", lambda _e: self.go_page(self.page_index + 1))
        root.bind("<Escape>", lambda _e: self._stop_drawing())
        root.bind(
            "<Key-d>", lambda e: self.toggle_drawing() if e.widget is not self.truth else None
        )
        root.protocol("WM_DELETE_WINDOW", self.close)

    # ------------------------------------------------------------ service --

    def _service(self) -> Any:
        if self.service is None:
            from caissa.ingest.pdf.ocr_service import OcrService

            self.service = OcrService(lang=self.lang_var.get())
        return self.service

    # ---------------------------------------------------------- documents --

    def add_pdf(self) -> None:
        path = filedialog.askopenfilename(title="PDF digitalizado", filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        book = self.project.add_document(path)
        self.project.save()
        self.doc_box["values"] = sorted(self.project.documents)
        self._select_document(book)

    def _select_document(self, book: str) -> None:
        if book not in self.project.documents:
            return
        self.document = book
        self.doc_box.set(book)
        try:
            total = page_count(self.project.pdf_for(book))
        except Exception as exc:  # noqa: BLE001 - a missing PDF is a status line, not a crash
            messagebox.showerror(
                "PDF", f"Não foi possível abrir {self.project.documents[book]}:\n{exc}"
            )
            return
        self.page_total.configure(text=f"/ {total - 1}")
        remembered = self.project.languages.get(book)
        if remembered:
            self.lang_var.set(remembered)
        labelled = self.project.pages_of(book)
        self.go_page(labelled[0].page_index if labelled else 0)

    def go_page(self, index: int) -> None:
        if self.document is None:
            return
        total = page_count(self.project.pdf_for(self.document))
        index = max(0, min(total - 1, index))
        self._flush_timer()
        self.page_index = index
        self.page_var.set(str(index))
        self.page = self.project.page(self.document, index)
        self.current = None
        self.selected_region = None
        self._render_page()
        self._fill_tree()
        if self.page and self.page.regions:
            self._select_first_pending()
        else:
            self._show_line(None)
        self._refresh_status()

    # --------------------------------------------------------- recognition --

    def recognise_page(self) -> None:
        if self.document is None:
            messagebox.showinfo("Rotulagem", "Adicione um PDF primeiro.")
            return
        decided = self.page is not None and any(line.done for _, line in self.page.lines())
        if decided and not messagebox.askyesno(
            "Reconhecer de novo",
            "Esta página já tem decisões. Reconhecer de novo descarta todas. Continuar?",
        ):
            return
        pdf, book, index = self.project.pdf_for(self.document), self.document, self.page_index
        dpi, lang = int(self.dpi_var.get()), self.lang_var.get()
        if self.project.languages.get(book) != lang:
            self.project.set_language(book, lang)
        self._set_status(f"Reconhecendo página {index} a {dpi} DPI ({lang})…")
        service = self._service()

        def work() -> PageLabels:
            return label_page(service, pdf, book, index, dpi=dpi, lang=lang)

        def done(kind: str, payload: Any) -> None:
            if kind == "error":
                messagebox.showerror("OCR", str(payload))
                self._refresh_status()
                return
            page: PageLabels = payload
            self.project.put_page(page)
            self.project.save()
            if self.page_index == page.page_index and self.document == page.document:
                self.page = page
                self._render_page()
                self._fill_tree()
                self._select_first_pending()
            self._refresh_status()

        if not self.worker.run(work, done):
            self._set_status("Aguarde: há uma tarefa em andamento.")

    def toggle_drawing(self) -> None:
        if self.page is None:
            self._ensure_page()
        self.drawing = not self.drawing
        self.canvas.configure(cursor="crosshair" if self.drawing else "arrow")
        self.draw_button.configure(
            text="Desenhando… (Esc)" if self.drawing else "Desenhar região (D)"
        )

    def _stop_drawing(self) -> None:
        if self.drawing:
            self.toggle_drawing()

    def _ensure_page(self) -> PageLabels | None:
        """A page record without recognition.

        So regions can be drawn on a page the layout was never run on.
        """
        if self.page is not None or self.document is None:
            return self.page
        pdf = self.project.pdf_for(self.document)
        width, height = page_size(pdf, self.page_index)
        self.page = PageLabels(
            document=self.document,
            pdf_path=str(pdf),
            page_index=self.page_index,
            width_pt=width,
            height_pt=height,
            dpi=float(self.dpi_var.get()),
            lang=self.lang_var.get(),
        )
        self.project.put_page(self.page)
        return self.page

    def _recognise_drawn(self, rect: tuple[float, float, float, float]) -> None:
        page = self._ensure_page()
        if page is None:
            return
        service = self._service()
        self._set_status("Reconhecendo a região desenhada…")

        def work() -> RegionLabel:
            return recognise_rect(service, page, rect, lang=self.lang_var.get())

        def done(kind: str, payload: Any) -> None:
            if kind == "error":
                messagebox.showerror("OCR", str(payload))
                return
            region: RegionLabel = payload
            page.regions.append(region)
            self.project.save()
            self._render_page()
            self._fill_tree()
            if region.lines:
                self._select_line(region, region.lines[0])
            self._refresh_status()

        self.worker.run(work, done)

    # -------------------------------------------------------------- canvas --

    def _page_image(self) -> Image.Image | None:
        if self.document is None:
            return None
        dpi = round(72 * self.scale)
        key = (self.document, self.page_index, dpi)
        image = self.page_cache.get(key)
        if image is None:
            rgb = render_rgb(self.project.pdf_for(self.document), self.page_index, dpi)
            image = Image.fromarray(rgb)
            if len(self.page_cache) > PAGE_CACHE_SIZE:
                self.page_cache.pop(next(iter(self.page_cache)))
            self.page_cache[key] = image
        return image

    def _render_page(self) -> None:
        self.canvas.delete("all")
        image = self._page_image()
        if image is None:
            return
        self.photo = ImageTk.PhotoImage(image)
        self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW, tags=("page",))
        self.canvas.configure(scrollregion=(0, 0, image.width, image.height))
        self.zoom_label.configure(text=f"{self.scale * 100 / 1.6:.0f} %")
        self._draw_boxes()

    def _px(self, rect: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        s = self.scale
        return rect[0] * s, rect[1] * s, rect[2] * s, rect[3] * s

    def _draw_boxes(self) -> None:
        self.canvas.delete("box")
        if self.page is None:
            return
        for region in self.page.regions:
            x0, y0, x1, y1 = self._px(region.rect)
            selected = region is self.selected_region
            self.canvas.create_rectangle(
                x0 - 2,
                y0 - 2,
                x1 + 2,
                y1 + 2,
                outline=SELECTED_COLOR if selected else REGION_COLOR,
                width=2 if selected else 1,
                dash=() if selected else (4, 3),
                tags=("box", f"region{region.index}"),
            )
            self.canvas.create_text(
                x0 - 2,
                y0 - 4,
                text=f"{region.index} {region.kind}",
                anchor=tk.SW,
                fill=REGION_COLOR,
                font=("Segoe UI", 8),
                tags=("box",),
            )
            for line in region.lines:
                lx0, ly0, lx1, ly1 = self._px(line.box)
                is_current = (
                    self.current is not None
                    and line is self.current[1]
                    and region is self.current[0]
                )
                self.canvas.create_rectangle(
                    lx0,
                    ly0,
                    lx1,
                    ly1,
                    outline=STATUS_COLOR[line.status],
                    width=3 if is_current else 1,
                    tags=("box",),
                )

    def zoom(self, factor: float) -> None:
        self.scale = max(0.4, min(6.0, self.scale * factor))
        self._render_page()

    def fit_width(self) -> None:
        if self.page is None and self.document is None:
            return
        width_pt = (
            self.page.width_pt
            if self.page
            else page_size(self.project.pdf_for(self.document), self.page_index)[0]
        )  # type: ignore[arg-type]
        avail = max(200, self.canvas.winfo_width() - 4)
        self.scale = max(0.4, min(6.0, avail / width_pt))
        self._render_page()

    def _on_wheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def _canvas_point(self, event: tk.Event) -> tuple[float, float]:
        return self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

    def _on_press(self, event: tk.Event) -> None:
        self.drag_start = self._canvas_point(event)
        if self.drawing:
            x, y = self.drag_start
            self.drag_item = self.canvas.create_rectangle(
                x, y, x, y, outline=SELECTED_COLOR, width=2, tags=("box",)
            )
        else:
            self.canvas.scan_mark(event.x, event.y)

    def _on_drag(self, event: tk.Event) -> None:
        if self.drag_start is None:
            return
        if self.drawing and self.drag_item is not None:
            x, y = self._canvas_point(event)
            self.canvas.coords(self.drag_item, self.drag_start[0], self.drag_start[1], x, y)
        elif not self.drawing:
            self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _on_release(self, event: tk.Event) -> None:
        if self.drag_start is None:
            return
        x, y = self._canvas_point(event)
        sx, sy = self.drag_start
        moved = abs(x - sx) > CLICK_SLOP_PX or abs(y - sy) > CLICK_SLOP_PX
        self.drag_start = None
        if self.drawing:
            if self.drag_item is not None:
                self.canvas.delete(self.drag_item)
                self.drag_item = None
            self._stop_drawing()
            if moved:
                s = self.scale
                self._recognise_drawn(
                    (min(sx, x) / s, min(sy, y) / s, max(sx, x) / s, max(sy, y) / s)
                )
            return
        if not moved:
            self._click_at(x / self.scale, y / self.scale)

    def _click_at(self, x: float, y: float) -> None:
        if self.page is None:
            return
        best: tuple[float, RegionLabel, LineLabel | None] | None = None
        for region in self.page.regions:
            for line in region.lines:
                bx0, by0, bx1, by1 = line.box
                if bx0 <= x <= bx1 and by0 <= y <= by1:
                    area = (bx1 - bx0) * (by1 - by0)
                    if best is None or area < best[0]:
                        best = (area, region, line)
            rx0, ry0, rx1, ry1 = region.rect
            if best is None and rx0 <= x <= rx1 and ry0 <= y <= ry1:
                best = ((rx1 - rx0) * (ry1 - ry0) + 1e9, region, None)
        if best is None:
            return
        _, region, line = best
        if line is not None:
            self._select_line(region, line)
        else:
            self.selected_region = region
            self._draw_boxes()

    def _on_right_click(self, event: tk.Event) -> None:
        if self.page is None:
            return
        x, y = self._canvas_point(event)
        x, y = x / self.scale, y / self.scale
        region = next(
            (
                r
                for r in self.page.regions
                if r.rect[0] <= x <= r.rect[2] and r.rect[1] <= y <= r.rect[3]
            ),
            None,
        )
        if region is None:
            return
        self.selected_region = region
        self._draw_boxes()
        menu = tk.Menu(self.root, tearoff=False)
        kinds = tk.Menu(menu, tearoff=False)
        for kind in kinds_for_menu():
            kinds.add_command(label=kind, command=lambda k=kind, r=region: self._set_kind(r, k))
        menu.add_cascade(label=f"Tipo da região {region.index} ({region.kind})", menu=kinds)
        menu.add_command(
            label="Aceitar linhas confiáveis desta região",
            command=lambda r=region: self.accept_confident(r),
        )
        menu.add_command(
            label="Rejeitar todas as linhas (não é texto)",
            command=lambda r=region: self._reject_region(r),
        )
        menu.add_command(
            label=f"FEN inicial dos lances… ({region.start_fen or 'sem FEN'})",
            command=lambda r=region: self._set_start_fen(r),
        )
        menu.add_separator()
        menu.add_command(label="Remover região", command=lambda r=region: self._remove_region(r))
        menu.tk_popup(event.x_root, event.y_root)

    def _set_kind(self, region: RegionLabel, kind: str) -> None:
        region.kind = kind
        self.project.save()
        self._draw_boxes()
        self._fill_tree()

    def _set_start_fen(self, region: RegionLabel) -> None:
        """The position before the region's first move.

        So the legality replay has somewhere to start (Sol §SOL-8).
        """
        fen = simpledialog.askstring(
            "FEN inicial",
            "FEN da posição antes do primeiro lance desta região (vazio remove):",
            initialvalue=region.start_fen,
            parent=self.root,
        )
        if fen is None:
            return
        fen = fen.strip()
        if fen:
            problem = _fen_problem(fen)
            if problem:
                messagebox.showerror("FEN", problem)
                return
        region.start_fen = fen
        self.project.save()
        self._fill_tree()

    def _remove_region(self, region: RegionLabel) -> None:
        if self.page is None:
            return
        if any(line.done for line in region.lines) and not messagebox.askyesno(
            "Remover região", "A região tem decisões gravadas. Remover mesmo assim?"
        ):
            return
        self.page.regions.remove(region)
        if self.current and self.current[0] is region:
            self.current = None
        self.selected_region = None
        self.project.save()
        self._render_page()
        self._fill_tree()
        self._select_first_pending()

    def _reject_region(self, region: RegionLabel) -> None:
        if self.page is None:
            return
        for line in region.lines:
            self.project.decide(self.page, line, LineStatus.REJECTED, note="região rejeitada")
        self.project.save()
        self._after_decision()

    # --------------------------------------------------------------- lines --

    def _visible_lines(self) -> list[tuple[RegionLabel, LineLabel]]:
        if self.page is None:
            return []
        threshold = self.project.doubt_threshold
        pairs = list(self.page.lines())
        if self.only_doubtful.get():
            pairs = [(r, line) for r, line in pairs if not line.done and line.doubtful(threshold)]
        return pairs

    def _fill_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        threshold = self.project.doubt_threshold
        for region, line in self._visible_lines():
            tags = [line.status.value]
            if not line.done and line.doubtful(threshold):
                tags.append("doubt")
            text = line.text if line.done else line.hypothesis
            self.tree.insert(
                "",
                tk.END,
                iid=f"{region.index}:{line.index}",
                values=(
                    line.index,
                    region.index,
                    _status_pt(line.status),
                    f"{line.confidence:.2f}",
                    text.replace("\n", " "),
                ),
                tags=tags,
            )
        if self.current is not None:
            iid = f"{self.current[0].index}:{self.current[1].index}"
            if self.tree.exists(iid):
                self.tree.selection_set(iid)
                self.tree.see(iid)

    def _on_tree_select(self, _event: tk.Event) -> None:
        selection = self.tree.selection()
        if not selection or self.page is None:
            return
        region_index, line_index = (int(v) for v in selection[0].split(":"))
        region = next((r for r in self.page.regions if r.index == region_index), None)
        if region is None:
            return
        line = next((c for c in region.lines if c.index == line_index), None)
        if line is not None and (self.current is None or line is not self.current[1]):
            self._select_line(region, line, from_tree=True)

    def _select_first_pending(self) -> None:
        pairs = self._visible_lines()
        pending = next(((r, line) for r, line in pairs if not line.done), None) or (
            pairs[0] if pairs else None
        )
        if pending:
            self._select_line(*pending)
        else:
            self._show_line(None)

    def _select_line(
        self, region: RegionLabel, line: LineLabel, *, from_tree: bool = False
    ) -> None:
        self._flush_timer()
        self.current = (region, line)
        self.selected_region = region
        self.opened_at = time.perf_counter()
        self._draw_boxes()
        self._show_line(line)
        self._scroll_to(line)
        if not from_tree:
            iid = f"{region.index}:{line.index}"
            if self.tree.exists(iid):
                self.tree.selection_set(iid)
                self.tree.see(iid)

    def _scroll_to(self, line: LineLabel) -> None:
        image = self.photo
        if image is None:
            return
        x0, y0, x1, y1 = self._px(line.box)
        height, width = image.height(), image.width()
        cy = (y0 + y1) / 2 - self.canvas.winfo_height() / 2
        self.canvas.yview_moveto(max(0.0, cy / max(1, height)))
        if x0 < self.canvas.canvasx(0) or x1 > self.canvas.canvasx(self.canvas.winfo_width()):
            self.canvas.xview_moveto(max(0.0, (x0 - 20) / max(1, width)))

    def _show_line(self, line: LineLabel | None) -> None:
        self.reading.configure(state=tk.NORMAL)
        self.reading.delete("1.0", tk.END)
        self.alternatives.delete(0, tk.END)
        self.truth.delete("1.0", tk.END)
        if line is None or self.page is None:
            self.reading.configure(state=tk.DISABLED)
            self.crop_label.configure(
                image="", text="Reconheça a página (F5) ou desenhe uma região (D)."
            )
            self.context_label.configure(text="")
            self.reason_label.configure(text="")
            return
        region = self.current[0] if self.current else None
        # Crop, magnified.
        pad = 3.0
        x0, y0, x1, y1 = line.box
        rgb = render_rgb(
            self.page.pdf_path,
            self.page.page_index,
            300,
            clip=(x0 - pad, y0 - pad, x1 + pad, y1 + pad),
        )
        image = Image.fromarray(rgb)
        avail = max(300, self.crop_label.winfo_width() - 8)
        ratio = min(
            avail / max(1, image.width), CROP_HEIGHT_PX / max(1, image.height), CROP_MAX_ZOOM
        )
        image = image.resize(
            (max(1, int(image.width * ratio)), max(1, int(image.height * ratio))), Image.LANCZOS
        )
        self.crop_photo = ImageTk.PhotoImage(image)
        self.crop_label.configure(image=self.crop_photo, text="")
        # Reading with weak words highlighted.
        threshold = self.project.doubt_threshold
        for n, word in enumerate(line.words):
            tag = (
                ()
                if word.confidence >= threshold
                else (("bad",) if word.confidence < threshold * 0.7 else ("weak",))
            )
            self.reading.insert(tk.END, word.text, tag)
            if n < len(line.words) - 1:
                self.reading.insert(tk.END, " ")
        if not line.words:
            self.reading.insert(tk.END, line.hypothesis)
        self.reading.configure(state=tk.DISABLED)
        for source, text in line.alternatives:
            self.alternatives.insert(tk.END, f"{source}: {text}")
        if not line.alternatives:
            self.alternatives.insert(tk.END, "(nenhum candidato leu esta linha de outro jeito)")
        partition = self.page.region_partition(region).value if region else ""
        if partition == "blind":
            partition = "blind (cega: não treina)"
        weak = line.low_confidence_words(threshold)
        parts = [
            f"linha {line.index} · região {region.index} ({region.kind})" if region else "",
            f"conf. {line.confidence:.2f}",
            f"partição {partition}",
        ]
        if line.done:
            parts.append(
                f"{_status_pt(line.status)} por {line.reviewer or '?'} em {line.seconds:.0f}s"
            )
        self.context_label.configure(text=" · ".join(p for p in parts if p))
        reasons = []
        if weak:
            reasons.append("palavras fracas: " + ", ".join(weak[:WEAK_WORDS_SHOWN]))
        if region and region.reasons:
            reasons.append("; ".join(region.reasons[:2]))
        if line.alternatives:
            reasons.append(
                f"{len(line.alternatives)} leitura(s) alternativa(s) — Alt+1/Alt+2 copia"
            )
        self.reason_label.configure(text=" · ".join(reasons))
        self.truth.insert("1.0", line.text if line.done else line.hypothesis)
        self.truth.focus_set()
        self.truth.mark_set(tk.INSERT, tk.END)

    def _use_alternative(self, _event: tk.Event | None = None, *, index: int | None = None) -> str:
        if index is None:
            selection = self.alternatives.curselection()
            index = int(selection[0]) if selection else 0
        if self.current and index < len(self.current[1].alternatives):
            self.truth.delete("1.0", tk.END)
            self.truth.insert("1.0", self.current[1].alternatives[index][1])
        return "break"

    def insert_figurine(self, glyph: str) -> str:
        """Type a figurine at the cursor of the truth field."""
        self.truth.insert(tk.INSERT, glyph)
        self.truth.focus_set()
        return "break"

    def letters_to_figurines(self) -> None:
        """English piece letters in the truth's move tokens become figurines.

        ``Nf3`` → ``♘f3``, ``22...Bf8`` → ``22...♗f8``; a pawn move, a word
        or a lone capital is left alone.  Undo with Ctrl+Z.
        """
        text = self.truth.get("1.0", tk.END).rstrip("\n")
        converted = letters_to_figurines(text)
        if converted != text:
            self.truth.delete("1.0", tk.END)
            self.truth.insert("1.0", converted)
        self.truth.focus_set()

    def _on_enter(self, _event: tk.Event) -> str:
        typed = self.truth.get("1.0", tk.END).strip()
        if self.current and typed and typed != self.current[1].hypothesis.strip():
            self.decide(LineStatus.EDITED)
        else:
            self.decide(LineStatus.ACCEPTED)
        return "break"

    def _on_ctrl_enter(self, _event: tk.Event) -> str:
        self.decide(LineStatus.EDITED)
        return "break"

    def decide(self, status: LineStatus) -> str:
        if self.current is None or self.page is None:
            return "break"
        _, line = self.current
        typed = self.truth.get("1.0", tk.END).strip()
        seconds = time.perf_counter() - self.opened_at if self.opened_at else 0.0
        self.opened_at = 0.0
        if status is LineStatus.EDITED and not typed:
            status = LineStatus.REJECTED
        if status is LineStatus.EDITED and typed == line.hypothesis.strip():
            status = LineStatus.ACCEPTED
        self.project.decide(
            self.page,
            line,
            status,
            text=typed if status is LineStatus.EDITED else None,
            seconds=seconds,
        )
        self._after_decision(advance=True)
        return "break"

    def _undo_line(self, _event: tk.Event | None = None) -> str:
        if self.current and self.page:
            self.project.reset(self.page, self.current[1])
            self._after_decision()
        return "break"

    def _after_decision(self, *, advance: bool = False) -> None:
        self.project.save()
        self._fill_tree()
        self._draw_boxes()
        self._refresh_status()
        if advance:
            self.step(1, pending_only=True)
        elif self.current:
            self._show_line(self.current[1])

    def step(self, delta: int, *, pending_only: bool = False) -> str:
        pairs = self._visible_lines()
        if not pairs:
            return "break"
        if self.current is None:
            self._select_line(*pairs[0])
            return "break"
        try:
            position = next(i for i, (r, line) in enumerate(pairs) if line is self.current[1])
        except StopIteration:
            position = -1
        if pending_only:
            after = pairs[position + 1 :] + pairs[: position + 1]
            target = next(((r, line) for r, line in after if not line.done), None)
            if target is None:
                self._flush_timer()
                self._show_line(self.current[1])
                self._set_status("Página concluída: todas as linhas decididas.")
                return "break"
        else:
            target = pairs[(position + delta) % len(pairs)]
        self._select_line(*target)
        return "break"

    def accept_confident(self, region: RegionLabel | None = None) -> None:
        """FineReader's "skip what the engine is sure about".

        Every pending line with no weak word, no disagreeing candidate and
        text is accepted.
        """
        if self.page is None:
            return
        threshold = self.project.doubt_threshold
        regions = [region] if region else self.page.regions
        count = 0
        for reg in regions:
            for line in reg.lines:
                if not line.done and not line.doubtful(threshold):
                    self.project.decide(
                        self.page, line, LineStatus.ACCEPTED, note="aceita em lote (confiante)"
                    )
                    count += 1
        self._after_decision()
        self._set_status(f"{count} linha(s) confiantes aceitas; as duvidosas continuam pendentes.")

    def _flush_timer(self) -> None:
        """Time spent on a line that was left without a verdict still counts for the page."""
        if self.opened_at and self.page is not None:
            self.page.seconds += time.perf_counter() - self.opened_at
        self.opened_at = 0.0

    # -------------------------------------------------------------- status --

    def _set_status(self, text: str) -> None:
        self.status.configure(text=text)

    def _refresh_status(self) -> None:
        if self.page is None:
            self._set_status("Sem reconhecimento nesta página. F5 reconhece; D desenha uma região.")
            return
        counts = self.page.counts()
        threshold = self.project.doubt_threshold
        doubtful = sum(
            1 for _, line in self.page.lines() if not line.done and line.doubtful(threshold)
        )
        blind = (
            f" · {self.page.blind_regions} região(ões) na partição cega: entram no manifesto, "
            f"ficam fora do treino e da calibração"
            if self.page.blind_regions
            else ""
        )
        minutes, seconds = divmod(int(self.page.seconds), 60)
        self._set_status(
            f"{counts['total']} linhas · {counts['pending']} pendentes ({doubtful} duvidosas) · "
            f"{counts['accepted']} aceitas · {counts['edited']} editadas · "
            f"{counts['rejected']} rejeitadas · tempo na página {minutes:02d}:{seconds:02d}{blind}"
        )

    # ------------------------------------------------------------- exports --

    def save(self) -> str:
        self._flush_timer()
        self.project.save()
        self._set_status(f"Projeto salvo em {self.project.root}")
        return "break"

    def export_ground_truth(self) -> None:
        self.save()
        out = self.project.root / "ground_truth"
        self._set_status("Gerando a verdade por linha…")

        def work() -> Any:
            return write_ground_truth(self.project, out)

        def done(kind: str, payload: Any) -> None:
            if kind == "error":
                messagebox.showerror("Exportar", str(payload))
                return
            report = payload
            messagebox.showinfo(
                "Verdade para treino",
                f"{report.written} linhas escritas em {out}\n"
                f"por partição: {report.by_partition}\n"
                f"retidas (regiões cegas): {report.withheld_blind} · "
                f"minúsculas: {report.skipped_tiny}",
            )
            self._refresh_status()

        self.worker.run(work, done)

    def export_manifest(self) -> None:
        self.save()
        items = manifest_items(self.project)
        if not items:
            messagebox.showinfo(
                "Manifesto",
                "Nenhuma região completa (todas as linhas decididas e ao menos uma mantida).",
            )
            return
        path = filedialog.asksaveasfilename(
            title="Manifesto dourado",
            initialdir=str(DEFAULT_MANIFEST.parent),
            initialfile=DEFAULT_MANIFEST.name,
            defaultextension=".json",
            confirmoverwrite=False,
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        try:
            added, replaced = merge_into_manifest(path, items)
        except Exception as exc:  # noqa: BLE001 - shown to the reviewer
            messagebox.showerror("Manifesto", str(exc))
            return
        messagebox.showinfo("Manifesto", f"{added} itens novos, {replaced} substituídos em {path}")

    def export_corrections(self) -> None:
        self.save()
        rows = corrections(self.project)
        pairs = calibration_pairs(self.project)
        (self.project.root / "corrections.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        (self.project.root / "calibration_pairs.json").write_text(
            json.dumps(pairs, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        messagebox.showinfo(
            "Correções",
            f"{len(rows)} correções e {len(pairs)} linhas de pares gravadas em "
            f"{self.project.root}\n(retidas por região cega: {withheld_lines(self.project)})",
        )

    def apply_language(self) -> None:
        """Stamp the selected document (and its labelled pages) with the
        language in the box — for pages recognised under the wrong default."""
        if self.document is None:
            return
        lang = self.lang_var.get().strip()
        changed = self.project.set_language(self.document, lang)
        self.project.save()
        messagebox.showinfo(
            "Idioma",
            f"{self.document}: idioma {lang}; {changed} página(s) rotulada(s) re-marcadas "
            f"(faceta prose_lang = {lang.split('+')[0]}). Refaça «Fundir no manifesto» para "
            f"o corpus refletir.",
        )
        self._refresh_status()

    def show_summary(self) -> None:
        summary = self.project.summary()
        lines = summary.pop("lines")
        text = "\n".join(f"{k}: {v}" for k, v in summary.items())
        text += "\nlinhas: " + ", ".join(f"{k} {v}" for k, v in lines.items())
        messagebox.showinfo("Resumo do projeto", text)

    def open_training(self) -> None:
        self.save()
        TrainingDialog(self.root, self.project)

    def close(self) -> None:
        self.save()
        self.root.destroy()


#: Alt+key → figurine, in the truth field and on the palette.
FIGURINE_KEYS = {"k": "♔", "q": "♕", "r": "♖", "b": "♗", "n": "♘", "p": "♙"}
_LETTER_TO_FIGURINE = {"K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘"}
#: A piece letter that starts a move: optional glued move number before it,
#: a square (with optional disambiguation and capture) after it.
_PIECE_MOVE = re.compile(
    r"(?<![A-Za-z♔-♙])(?P<number>\d{1,3}\.{0,3})?(?P<piece>[KQRBN])"
    r"(?=[a-h]?[1-8]?x?[a-h][1-8])"
)


def letters_to_figurines(text: str) -> str:
    """``Nf3`` → ``♘f3`` for every English piece letter that starts a move."""
    return _PIECE_MOVE.sub(
        lambda m: (m.group("number") or "") + _LETTER_TO_FIGURINE[m.group("piece")], text
    )


def _fen_problem(fen: str) -> str:
    """Why ``fen`` is not a position, or an empty string when it is."""
    try:
        import chess
    except ImportError:
        ranks = fen.split()[0].count("/") + 1
        shaped = len(fen.split()) in (4, 5, 6) and ranks == FEN_RANKS
        return "" if shaped else "FEN com formato inválido."
    try:
        chess.Board(fen)
    except ValueError as exc:
        return f"FEN inválida: {exc}"
    return ""


def _status_pt(status: LineStatus) -> str:
    return {
        LineStatus.PENDING: "pendente",
        LineStatus.ACCEPTED: "aceita",
        LineStatus.EDITED: "editada",
        LineStatus.REJECTED: "rejeitada",
    }[status]


# --------------------------------------------------------------------------- #
# Training dialog
# --------------------------------------------------------------------------- #


class TrainingDialog:
    def __init__(self, parent: tk.Tk, project: LabelProject) -> None:
        self.project = project
        self.top = tk.Toplevel(parent)
        self.top.title("Ajuste fino do Tesseract")
        self.top.geometry("900x640")
        self.tuner: TesseractFineTuner | None = None
        self.queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        form = ttk.Frame(self.top, padding=8)
        form.pack(side=tk.TOP, fill=tk.X)
        self.gt_var = tk.StringVar(value=str(project.root / "ground_truth"))
        self.out_var = tk.StringVar(value=str(DEFAULT_MODELS))
        self.base_lang = tk.StringVar(value="por")
        self.base_model = tk.StringVar(value="")
        self.name_var = tk.StringVar(value="")
        self.iterations = tk.IntVar(value=2000)
        self.rate = tk.StringVar(value="0.001")
        self.extend = tk.BooleanVar(value=True)
        rows = [
            ("Verdade (ground_truth/)", self.gt_var, self._pick_dir),
            ("Pasta de saída (tessdata)", self.out_var, self._pick_dir),
            ("Modelo base float (tessdata_best)", self.base_model, self._pick_file),
        ]
        for n, (label, var, picker) in enumerate(rows):
            ttk.Label(form, text=label).grid(row=n, column=0, sticky=tk.W, pady=2)
            ttk.Entry(form, textvariable=var, width=70).grid(row=n, column=1, sticky=tk.EW, padx=4)
            ttk.Button(form, text="…", width=3, command=lambda v=var, p=picker: p(v)).grid(
                row=n, column=2
            )
        ttk.Label(form, text="Idioma base").grid(row=3, column=0, sticky=tk.W)
        line = ttk.Frame(form)
        line.grid(row=3, column=1, sticky=tk.W, padx=4)
        ttk.Combobox(
            line,
            textvariable=self.base_lang,
            width=6,
            values=["por", "eng", "deu", "spa", "rus", "fra", "ita", "nld"],
        ).pack(side=tk.LEFT)
        ttk.Label(line, text="  nome do modelo").pack(side=tk.LEFT)
        ttk.Entry(line, textvariable=self.name_var, width=16).pack(side=tk.LEFT, padx=4)
        ttk.Label(line, text="iterações").pack(side=tk.LEFT)
        ttk.Spinbox(
            line, from_=100, to=50000, increment=100, textvariable=self.iterations, width=7
        ).pack(side=tk.LEFT, padx=4)
        ttk.Label(line, text="taxa").pack(side=tk.LEFT)
        ttk.Entry(line, textvariable=self.rate, width=8).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(line, text="estender alfabeto (figurinas)", variable=self.extend).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        form.columnconfigure(1, weight=1)
        buttons = ttk.Frame(self.top, padding=(8, 0))
        buttons.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(buttons, text="Baixar base (tessdata_best)…", command=self.download_base).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(buttons, text="Verificar (preflight)", command=self.run_preflight).pack(
            side=tk.LEFT
        )
        self.train_button = ttk.Button(buttons, text="Treinar", command=self.run_training)
        self.train_button.pack(side=tk.LEFT, padx=6)
        ttk.Button(buttons, text="Cancelar", command=self.cancel).pack(side=tk.LEFT)
        self.progress = ttk.Progressbar(buttons, mode="determinate", length=260)
        self.progress.pack(side=tk.RIGHT)
        self.progress_label = ttk.Label(buttons, text="")
        self.progress_label.pack(side=tk.RIGHT, padx=8)
        self.log = tk.Text(
            self.top, wrap=tk.WORD, font=("Consolas", 9), background="#111827", foreground="#e5e7eb"
        )
        self.log.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.top.after(100, self._poll)
        self._hint()

    def _hint(self) -> None:
        try:
            tools = find_training_tools()
            self._append(f"ferramentas: {tools.lstmtraining}\ntessdata: {tools.tessdata_dir}")
            self._append(
                "Atenção: o instalador do Windows traz modelos inteiros (tessdata_fast); "
                "o ajuste fino exige o modelo float de tessdata_best — indique-o em "
                "«Modelo base float»."
            )
        except TrainingToolsError as exc:
            self._append(f"ERRO: {exc}")
            self.train_button.configure(state=tk.DISABLED)

    def _pick_dir(self, var: tk.StringVar) -> None:
        path = filedialog.askdirectory(initialdir=var.get() or str(REPO_ROOT))
        if path:
            var.set(path)

    def _pick_file(self, var: tk.StringVar) -> None:
        path = filedialog.askopenfilename(filetypes=[("traineddata", "*.traineddata")])
        if path:
            var.set(path)

    def _config(self) -> FineTuneConfig:
        return FineTuneConfig(
            base_lang=self.base_lang.get().strip() or "por",
            base_model=Path(self.base_model.get()) if self.base_model.get().strip() else None,
            model_name=self.name_var.get().strip(),
            max_iterations=int(self.iterations.get()),
            learning_rate=float(self.rate.get() or "0.001"),
            extend_charset=bool(self.extend.get()),
        )

    def _append(self, text: str) -> None:
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)

    def download_base(self) -> None:
        lang = self.base_lang.get().strip() or "por"
        if not messagebox.askyesno(
            "Baixar modelo base",
            f"Baixar tessdata_best/{lang}.traineddata (Apache-2.0, ~10–30 MB) de\n"
            f"github.com/tesseract-ocr/tessdata_best para {DEFAULT_BEST}?",
            parent=self.top,
        ):
            return

        def work() -> None:
            try:
                path = download_base_model(
                    lang, DEFAULT_BEST, log=lambda text: self.queue.put(("log", text))
                )
                self.queue.put(("base", str(path)))
            except Exception as exc:  # noqa: BLE001
                self.queue.put(("log", f"ERRO no download: {exc}"))

        threading.Thread(target=work, daemon=True).start()

    def run_preflight(self) -> None:
        gt_dir = Path(self.gt_var.get())
        if not (gt_dir / "index.jsonl").is_file():
            self._append(
                f"Sem {gt_dir / 'index.jsonl'}: exporte a verdade para treino primeiro "
                "(menu Exportar)."
            )
            return
        config = self._config()

        def work() -> None:
            try:
                info = preflight(gt_dir, config)
                self.queue.put(("log", json.dumps(info, ensure_ascii=False, indent=1)))
            except Exception as exc:  # noqa: BLE001
                self.queue.put(("log", f"ERRO: {exc}"))

        threading.Thread(target=work, daemon=True).start()

    def run_training(self) -> None:
        if self.tuner is not None:
            self._append("Já há um treino em andamento.")
            return
        gt_dir, out_dir = Path(self.gt_var.get()), Path(self.out_var.get())
        if not (gt_dir / "index.jsonl").is_file():
            self._append("Exporte a verdade para treino primeiro (menu Exportar).")
            return
        config = self._config()
        self.train_button.configure(state=tk.DISABLED)
        self.progress.configure(maximum=config.max_iterations, value=0)

        def work() -> None:
            try:
                self.tuner = TesseractFineTuner(
                    gt_dir,
                    out_dir,
                    config,
                    log=lambda line: self.queue.put(("log", line)),
                    progress=lambda info: self.queue.put(("progress", info)),
                )
                report = self.tuner.run()
                self.queue.put(("done", report))
            except Exception as exc:  # noqa: BLE001
                self.queue.put(("done_error", exc))

        threading.Thread(target=work, daemon=True).start()

    def cancel(self) -> None:
        if self.tuner is not None:
            self.tuner.cancel()
            self._append(
                "Cancelado: a ferramenta em execução foi encerrada; o relatório registra a falha."
            )

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "log":
                    self._append(str(payload))
                elif kind == "base":
                    self.base_model.set(str(payload))
                elif kind == "progress":
                    if "iteration" in payload:
                        self.progress.configure(value=payload["iteration"])
                        self.progress_label.configure(
                            text=f"iteração {payload['iteration']} · "
                            f"erro de treino {payload['char_train']:.2f} %"
                        )
                    elif "lstmf" in payload:
                        self.progress_label.configure(
                            text=f"lstmf {payload['lstmf']}/{payload['lstmf_total']}"
                        )
                elif kind == "done":
                    self.tuner = None
                    self.train_button.configure(state=tk.NORMAL)
                    self._append(payload.markdown())
                elif kind == "done_error":
                    self.tuner = None
                    self.train_button.configure(state=tk.NORMAL)
                    self._append(f"ERRO: {payload}")
        except queue.Empty:
            pass
        if self.top.winfo_exists():
            self.top.after(100, self._poll)


# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "project",
        nargs="?",
        type=Path,
        default=DEFAULT_PROJECT,
        help="pasta do projeto de rotulagem (criada se não existir)",
    )
    parser.add_argument("--pdf", type=Path, default=None, help="PDF a adicionar ao abrir")
    parser.add_argument("--reviewer", default="", help="nome gravado em cada decisão")
    args = parser.parse_args(argv)
    project = LabelProject.open_or_create(args.project, reviewer=args.reviewer)
    if args.pdf is not None:
        project.add_document(args.pdf)
        project.save()
    root = tk.Tk()
    if not project.reviewer:
        name = simpledialog.askstring(
            "Revisor", "Seu nome (fica gravado em cada decisão):", parent=root
        )
        project.reviewer = (name or "").strip() or "revisor"
        project.save()
    window = LabelWindow(root, project)
    if args.pdf is not None:
        window._select_document(args.pdf.stem)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
