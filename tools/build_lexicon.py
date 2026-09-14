"""Build the packaged word lists of ``caissa.ocr.data.lexicon`` (Sol §SOL-9).

Two kinds of input, both recorded in ``MANIFEST.json`` with origin, licence,
word count and SHA-256:

* **Authored lists** (``authored/*.txt``, next to this script): the function
  words of each language, the chess and editorial vocabulary, and the names
  of players, authors, cities, publishers and events.  Written for this
  project; licence is the project's.
* **Licensed Hunspell dictionaries** found on this machine, with a licence
  that allows redistribution in an AGPL work: SCOWL ``en_US`` (MIT-style),
  Vero ``pt_BR`` (LGPLv3 / MPL), RLA-ES ``es_ES`` (GPLv3 / LGPLv3 / MPL 1.1).
  The stems keep their affix flags (``<code>.dic.gz``) and the affix rules
  travel with them (``<code>.aff.gz``); :mod:`caissa.ocr.hunspell` applies
  the rules in reverse at lookup time, so inflected forms are words without
  shipping millions of expanded forms.  A dictionary that is not on the
  machine is simply not built, and the manifest says so; the authored list
  for that language remains.

Run from the repository root::

    python tools/build_lexicon.py

and commit the resulting files.  Nothing is downloaded.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "src" / "caissa" / "ocr" / "data" / "lexicon"
AUTHORED = Path(__file__).resolve().parent / "lexicon_authored"

#: (language code, dictionary file, licence, origin) of the Hunspell sources.
HUNSPELL = [
    ("eng", r"C:\Program Files\LibreOffice\share\extensions\dict-en\en_US.dic",
     "SCOWL (MIT-style, Kevin Atkinson et al.; see README_en_US.txt)",
     "en_US Hunspell dictionary derived from SCOWL, LibreOffice dict-en"),
    ("por", r"C:\Program Files\LibreOffice\share\extensions\dict-pt-BR\pt_BR.dic",
     "LGPLv3 / MPL (Projeto Vero, Raimundo Santos Moura)",
     "pt_BR Hunspell dictionary, LibreOffice dict-pt-BR"),
    ("spa", r"C:\Program Files\LibreOffice\share\extensions\dict-es\es_ES.dic",
     "GPLv3 / LGPLv3 / MPL 1.1 (RLA-ES)",
     "es_ES Hunspell dictionary, LibreOffice dict-es"),
    # OCR_UI_ROADMAP passo 6 (2026-09-14): no Russian dictionary ships with the
    # LibreOffice on this machine, so this one was fetched once from the
    # LibreOffice dictionaries repository (ru_RU/, master) into models/hunspell/
    # and its licence read before anything else: BSD-3-Clause, Alexander I.
    # Lebedev, 1997-2008 (README_ru_RU.txt, copied into the package as
    # LICENSE_ru_RU.txt because the BSD notice must travel with the files).
    ("rus", str(REPO_ROOT / "models" / "hunspell" / "ru_RU" / "ru_RU.dic"),
     "BSD-3-Clause (Alexander I. Lebedev, 1997-2008; see LICENSE_ru_RU.txt)",
     "ru_RU Hunspell dictionary, LibreOffice dictionaries repository (ru_RU/)"),
]


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dic_lines(path: Path) -> list[str]:
    """The ``.dic`` entries as ``stem/FLAGS`` (morphology fields dropped)."""
    out: list[str] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        first = True
        for line in handle:
            line = line.strip().lstrip("\ufeff")
            if first:
                first = False
                if line.isdigit():
                    continue
            if not line or line.startswith("#"):
                continue
            entry = line.split("\t", 1)[0].strip()
            stem = entry.split("/", 1)[0]
            if stem and not any(ch.isdigit() for ch in stem):
                out.append(entry)
    return sorted(set(out))


def aff_lines(path: Path) -> list[str]:
    """Only what the reader needs: the flag mode and the affix rules."""
    out: list[str] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            head = line.split(" ", 1)[0].strip()
            if head in ("FLAG", "SFX", "PFX"):
                out.append(line.rstrip("\n"))
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "version": 2,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "files": {},
        "notes": [
            "Listas autorais (*.txt): palavras funcionais, vocabulário enxadrístico e editorial, "
            "nomes de jogadores, autores, cidades, editoras e eventos. Origem: este projeto; "
            "licença: AGPL-3.0-or-later.",
            "Dicionários Hunspell (*.dic.gz + *.aff.gz): radicais com flags e regras de afixo, aplicadas em sentido inverso na consulta (caissa.ocr.hunspell), de "
            "fontes com licença que permite redistribuição em obra AGPL; origem e licença por "
            "arquivo abaixo.",
            "As listas do tronco ChessVisionOFF (acervo/idioma/nomes) não são empacotadas: a "
            "origem de idioma.txt e nomes.txt não está declarada (PROCEDENCIA.md). Continuam "
            "opcionais via CAISSA_LEXICON_DIR, com hash registrado por execução.",
        ],
    }
    files: dict[str, object] = manifest["files"]  # type: ignore[assignment]

    for path in sorted(AUTHORED.glob("*.txt")):
        target = OUT / path.name
        target.write_bytes(path.read_bytes())
        words = [ln for ln in path.read_text("utf-8").splitlines()
                 if ln.strip() and not ln.startswith("#")]
        lang = path.stem if path.stem != "names" else ""
        files[path.name] = {
            "lang": lang, "words": len(words), "sha256": sha256_of(target),
            "source": "autoral (este projeto)", "license": "AGPL-3.0-or-later",
        }

    readme = REPO_ROOT / "models" / "hunspell" / "ru_RU" / "README_ru_RU.txt"
    if readme.is_file():
        (OUT / "LICENSE_ru_RU.txt").write_bytes(readme.read_bytes())
        files["LICENSE_ru_RU.txt"] = {
            "lang": "rus", "sha256": sha256_of(OUT / "LICENSE_ru_RU.txt"),
            "source": "README_ru_RU.txt do dicionário", "license": "BSD-3-Clause (aviso obrigatório)",
        }

    for lang, source, licence, origin in HUNSPELL:
        src = Path(source)
        name = f"{lang}.dic.gz"
        if not src.is_file() or not src.with_suffix(".aff").is_file():
            print(f"  - {name}: fonte ausente ({src}); não construído")
            continue
        entries = dic_lines(src)
        rules = aff_lines(src.with_suffix(".aff"))
        dic_target = OUT / f"{lang}.dic.gz"
        aff_target = OUT / f"{lang}.aff.gz"
        with gzip.open(dic_target, "wt", encoding="utf-8", compresslevel=9) as handle:
            handle.write("\n".join(entries) + "\n")
        with gzip.open(aff_target, "wt", encoding="utf-8", compresslevel=9) as handle:
            handle.write("\n".join(rules) + "\n")
        for target, kind, count in ((dic_target, "stems", len(entries)),
                                    (aff_target, "affix rules", len(rules))):
            origin_path = src if kind == "stems" else src.with_suffix(".aff")
            files[target.name] = {
                "lang": lang, ("words" if kind == "stems" else "rules"): count,
                "sha256": sha256_of(target), "source": origin,
                "source_path": str(origin_path), "source_sha256": sha256_of(origin_path),
                "license": licence,
            }
        print(f"  + {lang}: {len(entries)} radicais, {len(rules)} regras de {src.name}")

    (OUT / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(files)} arquivos -> {OUT / 'MANIFEST.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
