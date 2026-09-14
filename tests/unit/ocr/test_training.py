"""Sol §SOL-12 for the trainer: the fine-tune pipeline runs the right tools
in the right order, splits by partition, refuses what the base cannot
encode, and records base, result, hashes and error rates — exercised with a
fake runner, since the tools are not part of the test environment."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from caissa.ocr.training import (
    FineTuneConfig,
    TesseractFineTuner,
    TrainingTools,
    TrainingToolsError,
    find_training_tools,
)
from caissa.ocr.training.tesseract_finetune import (
    _parse_eval,
    read_unicharset,
    unknown_characters,
)

UNICHARSET = (
    "\n".join(
        [
            "9",
            "NULL 0 NULL 0",
            "Joined 0 0,255,0,255,0,0,0,0,0,0 Joined # Joined [4a 6f 69 6e 65 64 ]",
            "|Broken|0|1 0 0,255,0,255,0,0,0,0,0,0 |Broken|0|1 # Broken",
            "a 3 0,255,0,255,0,0,0,0,0,0 Latin 4 0 4 a",
            "b 3 0,255 Latin 5 0 5 b",
            "1 8 0,255 Common 6 0 6 1",
            ". 10 0,255 Common 7 0 7 .",
            "  0 0,255 Common 8 0 8  ",
        ]
    )
    + "\n"
)


def test_unicharset_reads_glyphs_and_space_but_not_bookkeeping(tmp_path: Path):
    path = tmp_path / "por.lstm-unicharset"
    path.write_text(UNICHARSET, encoding="utf-8")
    charset = read_unicharset(path)
    assert charset == {"a", "b", "1", ".", " "}
    assert unknown_characters("ab 1.", charset) == set()
    assert unknown_characters("áb ♘", charset) == {"á", "♘"}


def test_parse_eval_reads_the_last_rates():
    lines = [
        "Loaded 3 pages",
        "At iteration 0, stage 0, Eval Char error rate=3.9, Word error rate=10.2",
    ]
    assert _parse_eval(lines) == (3.9, 10.2)
    assert _parse_eval(["nothing"]) == (None, None)


def _tools(tmp_path: Path, *, charset_tools: bool = False) -> TrainingTools:
    tessdata = tmp_path / "tessdata"
    tessdata.mkdir()
    (tessdata / "por.traineddata").write_bytes(b"base" * 1000)
    (tessdata / "eng.traineddata").write_bytes(b"eng")
    extra = (
        {
            "unicharset_extractor": "unicharset_extractor",
            "merge_unicharsets": "merge_unicharsets",
            "combine_lang_model": "combine_lang_model",
        }
        if charset_tools
        else {}
    )
    return TrainingTools(
        tesseract="tesseract",
        lstmtraining="lstmtraining",
        combine_tessdata="combine_tessdata",
        lstmeval="lstmeval",
        tessdata_dir=str(tessdata),
        **extra,
    )


def _gt(tmp_path: Path) -> Path:
    gt = tmp_path / "gt"
    gt.mkdir()
    rows = [
        ("l1", "ab 1.", "dev"),
        ("l2", "ba", "dev"),
        ("l3", "b 1", "calib"),
        ("l4", "ab ♘", "dev"),
    ]
    with (gt / "index.jsonl").open("w", encoding="utf-8") as handle:
        for name, text, partition in rows:
            (gt / f"{name}.png").write_bytes(b"PNG")
            (gt / f"{name}.gt.txt").write_text(text + "\n", encoding="utf-8")
            handle.write(json.dumps({"name": name, "partition": partition}) + "\n")
    return gt


class FakeTools:
    """Writes what each tool would write and says what each tool would say."""

    def __init__(self, *, integer_model: bool = False) -> None:
        self.calls: list[list[str]] = []
        self.integer_model = integer_model

    def __call__(self, cmd, on_line, timeout_s=None) -> int:  # noqa: PLR0911, PLR0912 - one branch per tool
        cmd = list(cmd)
        self.calls.append(cmd)
        tool = Path(cmd[0]).name
        if cmd[-1] == "--version":
            on_line(f"{tool} 5.5.0")
            return 0
        if tool == "combine_tessdata":
            prefix = Path(cmd[-1])
            Path(str(prefix) + "lstm").write_bytes(b"x" * 4_000_000)
            Path(str(prefix) + "lstm-unicharset").write_text(UNICHARSET, encoding="utf-8")
            return 0
        if tool == "tesseract":
            image, out = Path(cmd[1]), Path(cmd[2])
            box = image.with_suffix(".box")
            assert box.is_file(), "lstm.train reads the WordStr box next to the image"
            content = box.read_text("utf-8")
            assert content.startswith("WordStr 0 0 ")
            assert "#" in content
            assert out.with_name(out.name + ".gt.txt").is_file()
            out.with_name(out.name + ".lstmf").write_bytes(b"lstmf")
            return 0
        if tool == "lstmtraining":
            if "--stop_training" in cmd:
                Path(cmd[cmd.index("--model_output") + 1]).write_bytes(b"trained-model")
                return 0
            if self.integer_model:
                on_line("Error, por.lstm is an integer (fast) model, cannot continue training")
                return 1
            on_line(
                "At iteration 100/100/100, mean rms=1.2%, delta=0.5%, char train=4.25%, "
                "word train=9.1%, skip ratio=0%"
            )
            on_line("Finished! Selected model with minimal training error rate (BCER) = 4.25")
            Path(cmd[cmd.index("--model_output") + 1] + "_checkpoint").write_bytes(b"ckpt")
            return 0
        if tool == "unicharset_extractor":
            text = Path(cmd[-1]).read_text("utf-8")
            chars = sorted({c for c in text if not c.isspace()})
            Path(cmd[cmd.index("--output_unicharset") + 1]).write_text(
                f"{len(chars) + 1}\nNULL 0 NULL 0\n" + "".join(f"{c} 0 Common 0\n" for c in chars),
                encoding="utf-8",
            )
            return 0
        if tool == "merge_unicharsets":
            base, extra, out = (Path(c) for c in cmd[1:4])
            seen: list[str] = []
            for src in (base, extra):
                for line in src.read_text("utf-8").splitlines()[1:]:
                    if line and line not in seen:
                        seen.append(line)
            out.write_text(f"{len(seen)}\n" + "\n".join(seen) + "\n", encoding="utf-8")
            return 0
        if tool == "combine_lang_model":
            assert (
                Path(cmd[cmd.index("--script_dir") + 1]) / "radical-stroke.txt"
            ).read_bytes() == b"\n"
            for flag in ("--words", "--puncs", "--numbers"):
                assert Path(cmd[cmd.index(flag) + 1]).read_bytes().strip()
            lang = cmd[cmd.index("--lang") + 1]
            target = Path(cmd[cmd.index("--output_dir") + 1]) / lang
            target.mkdir(parents=True, exist_ok=True)
            (target / f"{lang}.traineddata").write_bytes(b"starter")
            return 0
        if tool == "lstmeval":
            base = "--traineddata" in cmd
            on_line(
                f"At iteration 0, stage 0, Eval Char error rate={8.0 if base else 2.5}, "
                f"Word error rate={20.0 if base else 6.0}"
            )
            return 0
        raise AssertionError(f"unexpected tool {cmd}")


def test_fine_tune_runs_the_pipeline_and_reports(tmp_path: Path):
    fake = FakeTools()
    progress: list[dict] = []
    tuner = TesseractFineTuner(
        _gt(tmp_path),
        tmp_path / "out",
        FineTuneConfig(max_iterations=100),
        tools=_tools(tmp_path),
        runner=fake,
        progress=progress.append,
    )
    report = tuner.run()
    assert report.status == "trained", report.failure
    assert report.lines_total == 4
    assert report.lines_unencodable == 1
    assert report.unknown_chars == {"♘": 1}
    assert report.lines_train == 2
    assert report.lines_eval == 1
    assert report.iterations == 100
    assert report.best_train_error == 4.25
    assert (report.cer_before, report.cer_after) == (8.0, 2.5)
    assert Path(report.model_path).name == "caissa_por.traineddata"
    assert len(report.model_sha256) == 64
    assert report.base_sha256
    assert report.versions["lstmtraining"] == "lstmtraining 5.5.0"
    assert report.copied_langs == ["eng", "por"]
    assert (tmp_path / "out" / "eng.traineddata").is_file()
    tools_used = [Path(c[0]).name for c in fake.calls if c[-1] != "--version"]
    assert tools_used == [
        "combine_tessdata",
        "tesseract",
        "tesseract",
        "tesseract",
        "lstmtraining",
        "lstmtraining",
        "lstmeval",
        "lstmeval",
    ]
    train_cmd = next(
        c for c in fake.calls if Path(c[0]).name == "lstmtraining" and "--train_listfile" in c
    )
    assert "--continue_from" in train_cmd
    assert "--eval_listfile" in train_cmd
    lists = (tmp_path / "out" / "work" / "list.train").read_text("utf-8").split()
    assert [Path(p).stem for p in lists] == ["l1", "l2"]
    assert [
        Path(p).stem for p in (tmp_path / "out" / "work" / "list.eval").read_text("utf-8").split()
    ] == ["l3"]
    ledger = json.loads((tmp_path / "out" / "weights.json").read_text("utf-8"))
    assert ledger["artifacts"][0]["name"] == "caissa_por.traineddata"
    assert ledger["artifacts"][0]["sha256"] == report.model_sha256
    assert (
        (tmp_path / "out" / "report.md").read_text("utf-8").startswith("# Ajuste fino — caissa_por")
    )
    assert any("iteration" in p for p in progress)


def test_new_characters_extend_the_alphabet_when_the_tools_exist(tmp_path: Path):
    fake = FakeTools()
    tuner = TesseractFineTuner(
        _gt(tmp_path),
        tmp_path / "out",
        FineTuneConfig(max_iterations=100),
        tools=_tools(tmp_path, charset_tools=True),
        runner=fake,
    )
    report = tuner.run()
    assert report.status == "trained", report.failure
    assert report.charset_extended
    assert report.unknown_chars == {"♘": 1}
    assert report.lines_unencodable == 0, "the ♘ line trains instead of being dropped"
    assert report.lines_train == 3
    assert report.charset_size == 6, "a b 1 . space + ♘"
    tools_used = [Path(c[0]).name for c in fake.calls if c[-1] != "--version"]
    assert tools_used[5:9] == [
        "unicharset_extractor",
        "merge_unicharsets",
        "combine_lang_model",
        "lstmtraining",
    ]
    train_cmd = next(c for c in fake.calls if "--train_listfile" in c)
    assert "--old_traineddata" in train_cmd
    assert train_cmd[train_cmd.index("--traineddata") + 1].endswith("caissa_por.traineddata")
    assert train_cmd[train_cmd.index("--old_traineddata") + 1].endswith("por.traineddata")
    stop_cmd = next(c for c in fake.calls if "--stop_training" in c)
    assert stop_cmd[stop_cmd.index("--traineddata") + 1].endswith("caissa_por.traineddata")
    charset = tmp_path / "out" / "work" / "charset"
    assert "♘" in (charset / "gt.unicharset").read_text("utf-8")
    assert "ab" in (charset / "words.txt").read_text("utf-8").split()
    assert "acrescentados ao alfabeto" in (tmp_path / "out" / "report.md").read_text("utf-8")


def test_extension_can_be_switched_off(tmp_path: Path):
    tuner = TesseractFineTuner(
        _gt(tmp_path),
        tmp_path / "out",
        FineTuneConfig(max_iterations=100, extend_charset=False),
        tools=_tools(tmp_path, charset_tools=True),
        runner=FakeTools(),
    )
    report = tuner.run()
    assert report.status == "trained"
    assert not report.charset_extended
    assert report.lines_unencodable == 1


def test_integer_base_model_is_refused_with_the_download_hint(tmp_path: Path):
    tuner = TesseractFineTuner(
        _gt(tmp_path),
        tmp_path / "out",
        FineTuneConfig(),
        tools=_tools(tmp_path),
        runner=FakeTools(integer_model=True),
    )
    report = tuner.run()
    assert report.status == "failed"
    assert "tessdata_fast" in report.failure
    assert "tessdata_best" in report.failure
    assert (tmp_path / "out" / "report.json").is_file()


def test_missing_base_model_names_the_file(tmp_path: Path):
    tools = _tools(tmp_path)
    tuner = TesseractFineTuner(
        _gt(tmp_path),
        tmp_path / "out",
        FineTuneConfig(base_lang="deu"),
        tools=tools,
        runner=FakeTools(),
    )
    report = tuner.run()
    assert report.status == "failed"
    assert "deu.traineddata" in report.failure


def test_eval_share_is_held_out_when_the_index_has_no_calib(tmp_path: Path):
    gt = tmp_path / "gt"
    gt.mkdir()
    with (gt / "index.jsonl").open("w", encoding="utf-8") as handle:
        for n in range(20):
            (gt / f"n{n}.png").write_bytes(b"PNG")
            (gt / f"n{n}.gt.txt").write_text("ab\n", encoding="utf-8")
            handle.write(json.dumps({"name": f"n{n}", "partition": "dev"}) + "\n")
    tuner = TesseractFineTuner(
        gt,
        tmp_path / "out",
        FineTuneConfig(eval_share=0.25),
        tools=_tools(tmp_path),
        runner=FakeTools(),
    )
    report = tuner.run()
    assert report.status == "trained"
    assert report.lines_eval >= 1
    assert report.lines_train + report.lines_eval == 20


def test_find_training_tools_explains_what_is_missing(monkeypatch, tmp_path: Path):
    from caissa.ocr.training import tesseract_finetune as module

    monkeypatch.setattr(module, "find_tesseract", lambda explicit=None: None)
    with pytest.raises(TrainingToolsError, match="Tesseract não foi encontrado"):
        find_training_tools()
    exe = tmp_path / "tesseract.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(module, "find_tesseract", lambda explicit=None: str(exe))
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    with pytest.raises(TrainingToolsError, match="lstmtraining"):
        find_training_tools()


# --------------------------------------------------------------------------- #
# Negatives and rare-piece oversampling (OCR_UI_ROADMAP passo 4)
# --------------------------------------------------------------------------- #


def _strip(seed: int = 0):
    import numpy as np

    rng = np.random.default_rng(seed)
    strip = np.full((40, 300), 245, dtype=np.uint8)
    for x in range(20, 280, 12):  # "letters": dark boxes on paper
        strip[12:30, x : x + 6] = int(rng.integers(0, 40))
    return strip


def test_every_degradation_pads_with_texture_and_changes_the_strip_deterministically():
    import numpy as np

    from caissa.ocr.training.negatives import NEGATIVE_KINDS, degrade

    strip = _strip()
    for kind in NEGATIVE_KINDS:
        once = degrade(strip, kind, seed=3)
        again = degrade(strip, kind, seed=3)
        assert once.shape[0] == strip.shape[0]
        assert strip.shape[1] * 1.6 <= once.shape[1] <= strip.shape[1] * 2.6, (
            "texture-only margins on both sides, 30–80 % of the width each"
        )
        assert once.dtype == np.uint8
        assert np.array_equal(once, again), kind
        assert not np.array_equal(once, strip), kind
        assert not np.array_equal(once, degrade(strip, kind, seed=4)), kind
    dithered = degrade(strip, "dither", seed=1)
    assert set(np.unique(dithered)) <= {0, 255}, "fax is one bit per pixel"
    with pytest.raises(ValueError, match="cinza"):
        degrade(np.zeros((4, 4, 3), dtype=np.uint8), "noise")


def _real_gt(tmp_path: Path) -> Path:
    from PIL import Image

    gt = tmp_path / "gt"
    gt.mkdir()
    rows = [
        ("p1", "prose one", "dev"),
        ("p2", "prose two", "dev"),
        ("k1", "1.♔e2 ♘f3", "dev"),
        ("q1", "2.♕d1", "dev"),
        ("q2", "3.♕h5", "dev"),
        ("n1", "4.♘c3", "dev"),
        ("n2", "5.♘g1", "dev"),
        ("n3", "6.♘e5", "dev"),
        ("c1", "7.♕xf7", "calib"),
    ]
    with (gt / "index.jsonl").open("w", encoding="utf-8") as handle:
        for n, (name, text, partition) in enumerate(rows):
            Image.fromarray(_strip(n)).save(gt / f"{name}.png")
            (gt / f"{name}.gt.txt").write_text(text + "\n", encoding="utf-8")
            handle.write(json.dumps({"name": name, "partition": partition}) + "\n")
    return gt


def test_negatives_come_from_prose_lines_only_and_cycle_the_kinds(tmp_path: Path):
    from caissa.ocr.training.negatives import make_negatives

    gt = _real_gt(tmp_path)
    index = (gt / "index.jsonl").read_text("utf-8").splitlines()
    names = [json.loads(row)["name"] for row in index]
    made = make_negatives(gt, names, tmp_path / "neg", count=6)
    assert len(made) == 6
    kinds = [n.split("_")[1] for n in made]
    assert kinds == ["photo", "noise", "stains", "dither", "photo", "noise"]
    assert all(n.endswith(("_p1", "_p2")) for n in made), "only lines without figurines"
    for name in made:
        assert (tmp_path / "neg" / f"{name}.png").is_file()
        truth = (tmp_path / "neg" / f"{name}.gt.txt").read_text("utf-8")
        assert truth.startswith("prose")
    assert make_negatives(gt, ["k1", "q1"], tmp_path / "neg2", count=3) == []
    assert make_negatives(gt, names, tmp_path / "neg3", count=0) == []


def test_oversample_repeats_the_rare_piece_up_to_the_share_of_the_median():
    from caissa.ocr.training.negatives import oversample, piece_counts

    texts = {
        "k1": "1.♔e2 ♘f3", "q1": "2.♕d1", "q2": "3.♕h5",
        "n1": "4.♘c3", "n2": "5.♘g1", "n3": "6.♘e5", "p1": "prose",
    }
    assert piece_counts(texts) == {"♔": 1, "♘": 4, "♕": 2}
    extras, added = oversample(texts, share=1.0)  # median = 2
    assert extras == ["k1"]
    assert added == {"♔": 1}
    extras, added = oversample(texts, share=2.0)  # target 4: ♔ +3 (each copy also carries ♘), ♕ +2
    assert extras == ["k1", "k1", "k1", "q1", "q2"]
    assert added == {"♔": 3, "♕": 2}
    assert oversample(texts, share=0) == ([], {})
    assert oversample({"p1": "prose"}, share=1.0) == ([], {})


def test_the_tuner_adds_negatives_and_extra_copies_to_the_training_list(tmp_path: Path):
    fake = FakeTools()
    tuner = TesseractFineTuner(
        _real_gt(tmp_path),
        tmp_path / "out",
        FineTuneConfig(max_iterations=100, negatives=4, oversample_rare=1.0),
        tools=_tools(tmp_path, charset_tools=True),
        runner=fake,
    )
    report = tuner.run()
    assert report.status == "trained", report.failure
    assert report.lines_train == 8
    assert report.lines_negative == 4
    assert report.piece_lines == {"♔": 1, "♕": 2, "♘": 4}
    assert report.oversampled == {"♔": 1}
    listed = (tmp_path / "out" / "work" / "list.train").read_text("utf-8").split()
    lists = [Path(p).stem for p in listed]
    assert len(lists) == 8 + 4 + 1
    assert sum(1 for n in lists if n.startswith("neg_")) == 4
    assert lists.count("k1") == 2, "the rare piece's line is listed twice"
    assert (tmp_path / "out" / "work" / "negatives").is_dir()
    assert report.config["negatives"] == 4
    assert "Negativos: 4" in (tmp_path / "out" / "report.md").read_text("utf-8")
    # Sabotage of the roadmap: negatives=0 leaves the list as it was.
    (tmp_path / "b").mkdir()
    plain = TesseractFineTuner(
        _real_gt(tmp_path / "b"), tmp_path / "out2", FineTuneConfig(max_iterations=100),
        tools=_tools(tmp_path / "b", charset_tools=True), runner=FakeTools(),
    ).run()
    assert plain.lines_negative == 0
    assert plain.oversampled == {}
    assert len((tmp_path / "out2" / "work" / "list.train").read_text("utf-8").split()) == 8
