from __future__ import annotations

from typing import Any

_ENV_OPTIONS: list[tuple[str, str, str, str]] = [
    ("upscaling", "DLSS upgrade", "PROTON_DLSS_UPGRADE", "1"),
    ("upscaling", "FSR3 upgrade", "PROTON_FSR3_UPGRADE", "1"),
    ("upscaling", "FSR4 upgrade", "PROTON_FSR4_UPGRADE", "1"),
    ("upscaling", "FSR4 RDNA3", "PROTON_FSR4_RDNA3_UPGRADE", "1"),
    ("upscaling", "XeSS upgrade", "PROTON_XESS_UPGRADE", "1"),
    ("compatibility", "Enable NVAPI", "PROTON_ENABLE_NVAPI", "1"),
    ("compatibility", "Enable Wayland", "PROTON_ENABLE_WAYLAND", "1"),
    ("compatibility", "Enable HDR", "PROTON_ENABLE_HDR", "1"),
    ("compatibility", "Enable WoW64", "PROTON_USE_WOW64", "1"),
    ("tools", "MangoHUD", "MANGOHUD", "1"),
    ("debug", "Enable logging", "PROTON_LOG", "1"),
    ("debug", "Disable lsteamclient", "PROTON_DISABLE_LSTEAMCLIENT", "1"),
    ("debug", "Skip runtime update", "UMU_RUNTIME_UPDATE", "0"),
]

KNOWN_ENV_VARS: set[str] = {env_var for _, _, env_var, _ in _ENV_OPTIONS}


import re as _re


def normalize_dll_overrides(text: str) -> str:
    """Strip whitespace from *text* and return DLL override names as a comma-joined string."""
    parts = [p for p in _re.split(r'[\s,]+', text) if p]
    return ','.join(parts)


def normalize_args(text: str) -> str:
    """Convert comma-separated arguments in *text* to a space-separated string."""
    return _re.sub(r'\s*,\s*', ' ', text).strip()


def normalize_env_text(text: str) -> str:
    """Extract ``KEY=VALUE`` pairs from free-form *text* and return them comma-separated."""
    pairs = _re.findall(r'\S+=\S*', text)
    return ', '.join(pairs)


def custom_env_text(env_vars: dict[str, str]) -> str:
    """Return a comma-separated string of env vars from *env_vars* not in ``KNOWN_ENV_VARS``."""
    return ', '.join(
        f"{k}={v}" for k, v in env_vars.items()
        if k not in KNOWN_ENV_VARS
    )


def collect_env_vars(
    env_checkboxes: dict[str, Any],
    custom_env: str,
) -> dict[str, str]:
    """Merge checked *env_checkboxes* and parsed *custom_env* text into a single env-var dict."""
    env: dict[str, str] = {}

    for *_, env_var, val_on in _ENV_OPTIONS:
        cb = env_checkboxes.get(env_var)
        if cb and cb.isChecked():
            env[env_var] = val_on

    custom = custom_env.strip()
    if custom:
        for pair in _re.findall(r'\S+=\S*', custom):
            if '=' not in pair:
                continue
            k, v = pair.split('=', 1)
            k = k.strip()
            if k:
                env[k] = v.strip()

    return env


def populate_env_vars(
    env_vars: dict[str, str],
    env_checkboxes: dict[str, Any],
    custom_env_edit: Any = None,
) -> None:
    """Set UI checkboxes and *custom_env_edit* text from the given *env_vars* dict."""
    toggle_map: dict[str, str] = {env_var: val_on for *_, env_var, val_on in _ENV_OPTIONS}
    custom_pairs: list[str] = []

    for key, val in env_vars.items():
        if key in toggle_map:
            cb = env_checkboxes.get(key)
            if cb:
                cb.setChecked(val == toggle_map[key])
        elif key not in KNOWN_ENV_VARS:
            custom_pairs.append(f"{key}={val}")

    if custom_pairs and custom_env_edit is not None:
        custom_env_edit.setText(', '.join(custom_pairs))
