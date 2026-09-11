"""Tests for the layered configuration (caissa.core.config)."""

from __future__ import annotations

from pathlib import Path

import pytest

from caissa.core.config import (
    CaissaConfig,
    ConfigError,
    ConfigFileError,
    LlmConfig,
    RuntimeConfig,
    UnknownSettingError,
    get_config,
    load_config,
    reset_config,
    set_config,
    user_config_path,
)
from caissa.core.config.loader import environment_layer, project_file_layer, user_file_layer

NO_FILES = {"include_user_file": False, "include_project_file": False}


def write_toml(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Defaults
# --------------------------------------------------------------------------- #


def test_defaults_match_the_adrs():
    config = load_config(env={}, include_user_file=False, include_project_file=False)
    # ADR-0004: 7.0 GiB budget on an 8 GiB card.
    assert config.runtime.vram_budget_gb == 7.0
    assert config.runtime.vram_budget_bytes == int(7.0 * 1024**3)
    # SPEC R4: complete weight set capped at 6 GiB.
    assert config.cache.model_weights_budget_gb == 6.0
    # F0 risk 3 and F0 gate.
    assert config.runtime.min_free_disk_gb == 20.0
    assert config.runtime.gpu_matmul_budget_ms == 100.0
    assert config.runtime.device == "auto"
    assert config.runtime.allow_cpu_fallback is True
    assert config.ui.language == "pt_BR"


def test_cache_helpers():
    config = load_config(env={}, **NO_FILES)
    assert config.cache.page_cache_bytes == 2048 * 1024**2
    assert config.cache.thumbnail_cache_bytes == 512 * 1024**2
    assert config.cache.total_disk_budget_gb == pytest.approx(8.0 + 20.0 + 6.0)


def test_defaults_have_defaults_provenance():
    config = load_config(env={}, **NO_FILES)
    assert config.origin_of("runtime.vram_budget_gb") == "defaults"
    assert config.provenance == {}


# --------------------------------------------------------------------------- #
# Layer precedence: defaults -> user file -> environment -> project -> overrides
# --------------------------------------------------------------------------- #


def test_user_file_beats_defaults(tmp_path):
    user = write_toml(tmp_path / "caissa.toml", "[runtime]\nvram_budget_gb = 5.5\n")
    config = load_config(user_config_file=user, env={}, include_project_file=False)
    assert config.runtime.vram_budget_gb == 5.5
    assert config.origin_of("runtime.vram_budget_gb") == "user-file"


def test_environment_beats_user_file(tmp_path):
    user = write_toml(tmp_path / "caissa.toml", "[runtime]\nvram_budget_gb = 5.5\n")
    config = load_config(
        user_config_file=user,
        env={"CAISSA_RUNTIME__VRAM_BUDGET_GB": "4.25"},
        include_project_file=False,
    )
    assert config.runtime.vram_budget_gb == 4.25
    assert config.origin_of("runtime.vram_budget_gb") == "environment"


def test_project_file_beats_environment(tmp_path):
    project = tmp_path / "tree"
    write_toml(project / "caissa.toml", "[runtime]\nvram_budget_gb = 3.0\n")
    config = load_config(
        project_dir=project,
        env={"CAISSA_RUNTIME__VRAM_BUDGET_GB": "4.25"},
        include_user_file=False,
    )
    assert config.runtime.vram_budget_gb == 3.0
    assert config.origin_of("runtime.vram_budget_gb") == "project-file"


def test_overrides_beat_everything(tmp_path):
    project = tmp_path / "tree"
    write_toml(project / "caissa.toml", "[runtime]\nvram_budget_gb = 3.0\n")
    config = load_config(
        project_dir=project,
        env={"CAISSA_RUNTIME__VRAM_BUDGET_GB": "4.25"},
        include_user_file=False,
        overrides={"runtime": {"vram_budget_gb": 2.0}},
    )
    assert config.runtime.vram_budget_gb == 2.0
    assert config.origin_of("runtime.vram_budget_gb") == "overrides"


def test_layers_merge_per_key_not_per_section(tmp_path):
    user = write_toml(
        tmp_path / "caissa.toml",
        "[runtime]\nvram_budget_gb = 5.5\nworker_processes = 3\n",
    )
    config = load_config(
        user_config_file=user,
        env={"CAISSA_RUNTIME__WORKER_PROCESSES": "9"},
        include_project_file=False,
    )
    assert config.runtime.vram_budget_gb == 5.5  # kept from the user file
    assert config.runtime.worker_processes == 9  # overridden by the environment
    assert config.origin_of("runtime.vram_budget_gb") == "user-file"
    assert config.origin_of("runtime.worker_processes") == "environment"


def test_project_file_is_found_by_walking_upwards(tmp_path):
    write_toml(tmp_path / "caissa.toml", "[ui]\ntheme = 'light'\n")
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    config = load_config(project_dir=deep, env={}, include_user_file=False)
    assert config.ui.theme == "light"


def test_pyproject_tool_caissa_section_is_a_project_layer(tmp_path):
    write_toml(
        tmp_path / "pyproject.toml",
        "[project]\nname = 'x'\n\n[tool.caissa.vision]\nrender_dpi = 300\n",
    )
    config = load_config(project_dir=tmp_path, env={}, include_user_file=False)
    assert config.vision.render_dpi == 300
    assert config.origin_of("vision.render_dpi") == "project-file"


def test_dot_prefixed_project_file(tmp_path):
    write_toml(tmp_path / ".caissa.toml", "[ui]\ntarget_fps = 120\n")
    config = load_config(project_dir=tmp_path, env={}, include_user_file=False)
    assert config.ui.target_fps == 120


# --------------------------------------------------------------------------- #
# Environment variables
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1", True), ("true", True), ("YES", True), ("sim", True), ("0", False), ("nao", False)],
)
def test_environment_bool_parsing(raw, expected):
    config = load_config(env={"CAISSA_RUNTIME__ALLOW_CPU_FALLBACK": raw}, **NO_FILES)
    assert config.runtime.allow_cpu_fallback is expected


def test_environment_int_pair_parsing():
    config = load_config(env={"CAISSA_RUNTIME__MIN_COMPUTE_CAPABILITY": "12,0"}, **NO_FILES)
    assert config.runtime.min_compute_capability == (12, 0)


def test_toml_list_becomes_int_pair(tmp_path):
    user = write_toml(tmp_path / "caissa.toml", "[runtime]\nmin_compute_capability = [12, 0]\n")
    config = load_config(user_config_file=user, env={}, include_project_file=False)
    assert config.runtime.min_compute_capability == (12, 0)


def test_control_variables_are_not_settings():
    config = load_config(
        env={"CAISSA_CONFIG": "C:/nowhere.toml", "CAISSA_NO_USER_CONFIG": "1"},
        include_project_file=False,
    )
    assert config.runtime.vram_budget_gb == 7.0


def test_environment_variable_without_section_is_rejected():
    with pytest.raises(UnknownSettingError, match="CAISSA_VRAM_BUDGET_GB"):
        load_config(env={"CAISSA_VRAM_BUDGET_GB": "4"}, **NO_FILES)


def test_environment_layer_records_which_variables_it_saw():
    layer = environment_layer({"CAISSA_UI__THEME": "light"})
    assert layer.present
    assert "CAISSA_UI__THEME" in layer.origin
    assert layer.values == {"ui": {"theme": "light"}}


def test_absent_layers_are_reported_as_absent(tmp_path):
    assert not user_file_layer(tmp_path / "missing.toml", {}).present
    assert not project_file_layer(tmp_path, {}).present
    assert "ausente" in user_file_layer(tmp_path / "missing.toml", {}).describe()


def test_layers_can_be_disabled_by_control_variables(tmp_path):
    write_toml(tmp_path / "caissa.toml", "[ui]\ntheme = 'light'\n")
    env = {"CAISSA_NO_PROJECT_CONFIG": "1"}
    config = load_config(project_dir=tmp_path, env=env, include_user_file=False)
    assert config.ui.theme == "dark"


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


def test_unknown_field_names_the_key_and_suggests(tmp_path):
    user = write_toml(tmp_path / "caissa.toml", "[runtime]\nvram_budget = 5.0\n")
    with pytest.raises(UnknownSettingError) as excinfo:
        load_config(user_config_file=user, env={}, include_project_file=False)
    assert "runtime.vram_budget" in str(excinfo.value)
    assert "runtime.vram_budget_gb" in str(excinfo.value)


def test_unknown_section_is_rejected(tmp_path):
    user = write_toml(tmp_path / "caissa.toml", "[runtimee]\nx = 1\n")
    with pytest.raises(UnknownSettingError, match="runtimee"):
        load_config(user_config_file=user, env={}, include_project_file=False)


def test_malformed_toml_names_the_file(tmp_path):
    user = write_toml(tmp_path / "caissa.toml", "[runtime\nbroken")
    with pytest.raises(ConfigFileError, match="TOML"):
        load_config(user_config_file=user, env={}, include_project_file=False)


def test_wrong_type_is_rejected_with_the_key_name():
    with pytest.raises(ConfigError, match=r"runtime\.worker_processes"):
        load_config(env={"CAISSA_RUNTIME__WORKER_PROCESSES": "muitos"}, **NO_FILES)


def test_bool_is_not_accepted_where_a_number_is_expected(tmp_path):
    user = write_toml(tmp_path / "caissa.toml", "[runtime]\nvram_budget_gb = true\n")
    with pytest.raises(ConfigError, match="booleano"):
        load_config(user_config_file=user, env={}, include_project_file=False)


def test_out_of_range_value_is_rejected():
    with pytest.raises(ConfigError, match="vram_budget_gb"):
        load_config(env={"CAISSA_RUNTIME__VRAM_BUDGET_GB": "0.01"}, **NO_FILES)


def test_literal_values_are_validated():
    with pytest.raises(ConfigError, match=r"runtime\.device"):
        load_config(env={"CAISSA_RUNTIME__DEVICE": "gpu"}, **NO_FILES)
    with pytest.raises(ConfigError, match=r"ui\.theme"):
        load_config(env={"CAISSA_UI__THEME": "neon"}, **NO_FILES)


def test_vision_dpi_ordering_is_validated():
    with pytest.raises(ConfigError, match="max_page_dpi"):
        load_config(
            env={"CAISSA_VISION__RENDER_DPI": "600", "CAISSA_VISION__MAX_PAGE_DPI": "300"},
            **NO_FILES,
        )


def test_onnx_worker_requires_an_interpreter_path():
    with pytest.raises(ConfigError, match="onnx_worker_python"):
        load_config(env={"CAISSA_VISION__ONNX_WORKER_ENABLED": "1"}, **NO_FILES)


def test_llm_budget_cannot_exceed_the_vram_budget():
    with pytest.raises(ConfigError, match=r"excede runtime\.vram_budget_gb"):
        load_config(
            env={
                "CAISSA_LLM__ENABLED": "1",
                "CAISSA_LLM__VRAM_GB": "9.0",
                "CAISSA_RUNTIME__VRAM_BUDGET_GB": "7.0",
            },
            **NO_FILES,
        )


def test_disabled_llm_may_declare_more_than_the_budget():
    config = load_config(env={"CAISSA_LLM__VRAM_GB": "9.0"}, **NO_FILES)
    assert config.llm.enabled is False
    assert config.llm.vram_gb == 9.0


# --------------------------------------------------------------------------- #
# Paths and serialisation
# --------------------------------------------------------------------------- #


def test_paths_are_expanded(tmp_path, monkeypatch):
    monkeypatch.setenv("CAISSA_TEST_ROOT", str(tmp_path))
    config = load_config(env={"CAISSA_PATHS__MODELS_DIR": "%CAISSA_TEST_ROOT%/pesos"}, **NO_FILES)
    assert config.paths.models_dir == tmp_path / "pesos"
    assert "~" not in str(config.paths.data_dir)


def test_ensure_exists_creates_every_directory(tmp_path):
    config = load_config(
        overrides={
            "paths": {
                "data_dir": str(tmp_path / "d"),
                "cache_dir": str(tmp_path / "c"),
                "models_dir": str(tmp_path / "m"),
                "log_dir": str(tmp_path / "l"),
            }
        },
        env={},
        **NO_FILES,
    )
    config.paths.ensure_exists()
    for name in ("d", "c", "m", "l"):
        assert (tmp_path / name).is_dir()


def test_to_dict_is_toml_compatible():
    config = load_config(env={}, **NO_FILES)
    data = config.to_dict()
    assert set(data) == {"runtime", "cache", "paths", "vision", "llm", "ui"}
    assert isinstance(data["paths"]["models_dir"], str)
    assert data["runtime"]["min_compute_capability"] == [7, 0]
    assert data["runtime"]["vram_budget_gb"] == 7.0


def test_config_is_immutable():
    config = load_config(env={}, **NO_FILES)
    with pytest.raises(AttributeError):
        config.runtime.vram_budget_gb = 1.0  # type: ignore[misc]


def test_sources_describe_every_layer(tmp_path):
    user = write_toml(tmp_path / "caissa.toml", "[ui]\ntheme = 'light'\n")
    config = load_config(user_config_file=user, env={}, include_project_file=False)
    joined = " | ".join(config.sources)
    assert "defaults" in joined
    assert "user-file" in joined
    assert "environment" in joined


# --------------------------------------------------------------------------- #
# Singleton
# --------------------------------------------------------------------------- #


def test_singleton_is_cached_and_replaceable():
    first = get_config()
    assert get_config() is first
    replacement = load_config(env={"CAISSA_UI__THEME": "light"}, **NO_FILES)
    set_config(replacement)
    assert get_config() is replacement
    assert get_config().ui.theme == "light"
    reset_config()
    assert get_config() is not replacement


def test_user_config_path_honours_the_control_variable():
    assert user_config_path({"CAISSA_CONFIG": "D:/x/y.toml"}) == Path("D:/x/y.toml")
    assert user_config_path({}).name == "caissa.toml"


def test_direct_construction_still_validates():
    with pytest.raises(ConfigError, match=r"runtime\.device"):
        RuntimeConfig(device="gpu")  # type: ignore[arg-type]
    with pytest.raises(ConfigError, match=r"excede runtime\.vram_budget_gb"):
        CaissaConfig(
            runtime=RuntimeConfig(vram_budget_gb=2.0),
            llm=LlmConfig(enabled=True, vram_gb=6.0),
        )
