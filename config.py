"""Load project .env defaults, then read and validate environment configuration."""

import json
import math
import os
from ipaddress import ip_address
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from model import GOAL_CATEGORIES, category_name


def _read_env(name, default):
    raw = os.environ.get(name)
    if raw is None:
        return default
    if isinstance(default, list):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError(f"{name} must be a JSON array of non-empty strings") from None
        if not isinstance(value, list) or any(
            not isinstance(item, str) or not item.strip() for item in value
        ):
            raise ValueError(f"{name} must be a JSON array of non-empty strings")
        return value
    if isinstance(default, bool):
        if raw.lower() not in ("true", "false"):
            raise ValueError(f"{name} must be true or false")
        return raw.lower() == "true"
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"{name} must be a finite, non-negative number of seconds") from None
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite, non-negative number of seconds")
    return value


def load_config(*, require_credentials=True):
    load_dotenv(Path(__file__).resolve().with_name(".env"), override=False)
    config: dict[str, Any] = {}
    for key in ("card_number", "password"):
        name = f"SEU_{key.upper()}"
        value = os.environ.get(name, "")
        if require_credentials and not value.strip():
            raise ValueError(f"{name} is required; set it in .env or the environment")
        config[key] = value

    vpn_ip = os.environ.get("SEU_VPN_IP", "").strip()
    try:
        if "%" in vpn_ip:
            raise ValueError
        config["vpn_ip"] = str(ip_address(vpn_ip)) if vpn_ip else ""
    except ValueError:
        raise ValueError("SEU_VPN_IP must be a single IPv4 or IPv6 address, or empty") from None

    for key, default in {
        "preferred_lectures": [],
        "required_categories": list(GOAL_CATEGORIES),
        "preferred_campus": [],
        "enable_offline": True,
        "enable_online": True,
    }.items():
        config[key] = _read_env(f"SEU_{key.upper()}", default)

    config["required_categories"] = [category_name(value) for value in config["required_categories"]]
    if (not config["required_categories"]
            or len(set(config["required_categories"])) != len(config["required_categories"])):
        raise ValueError("SEU_REQUIRED_CATEGORIES must contain distinct categories")
    state_dir = os.environ.get("SEU_STATE_DIR", "state").strip()
    if not state_dir:
        raise ValueError("SEU_STATE_DIR must not be empty")
    config["state_dir"] = Path(__file__).resolve().parent / state_dir
    config["mail"] = {key: os.environ[key] for key in (
        "SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "MAIL_FROM", "MAIL_TO"
    ) if key in os.environ}

    config["timeout_settings"] = {
        key: _read_env(f"SEU_TIMEOUT_{key.upper()}", default)
        for key, default in {
            "page_load": 0.5,
            "element_wait": 3,
            "login_redirect": 30,
            "scan_interval": 10,
            "retry_delay": 0.05,
            "action_confirm": 0.2,
        }.items()
    }
    if config["timeout_settings"]["scan_interval"] == 0:
        raise ValueError("SEU_TIMEOUT_SCAN_INTERVAL must be greater than zero")
    return config
