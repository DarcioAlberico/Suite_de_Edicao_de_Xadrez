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


def _tools(tmp_path: Path) -> TrainingTools:
    tessdata = tmp_path / "tessdata"
    tessdata.mkdir()
    (tessdata / "por.traineddata").write_bytes(b"base" * 1000)
    (tessdata / "eng.traineddata").write_bytes(b"eng")
    return TrainingTools(
        tesseract="tesseract",
        lstmtraining="lstmtraining",
        combine_tessdata="combine_tessdata",
        lstmeval="lstmeval",
        tessdata_dir=str(tessdata),
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

    def __call__(self, cmd, on_line, timeout_s=None) -> int:  # noqa: PLR0911 - one branch per tool
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
