"""Load project .env defaults, then read and validate environment configuration."""

import json
import math
import os
from ipaddress import ip_address
from pathlib import Path

from dotenv import load_dotenv


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


def load_config():
    load_dotenv(Path(__file__).resolve().with_name(".env"), override=False)
    config = {}
    for key in ("card_number", "password"):
        name = f"SEU_{key.upper()}"
        value = os.environ.get(name, "")
        if not value.strip():
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
        "required_categories": [
            "人文与科学素养系列讲座_心理健康",
            "人文与科学素养系列讲座_法律",
            "人文与科学素养系列讲座-艺术类",
            "人文与科学素养系列讲座_其他",
            '“SEU咖啡间"系列沙龙活动',
        ],
        "preferred_campus": [],
        "enable_offline": True,
        "enable_online": True,
    }.items():
        config[key] = _read_env(f"SEU_{key.upper()}", default)

    config["timeout_settings"] = {
        key: _read_env(f"SEU_TIMEOUT_{key.upper()}", default)
        for key, default in {
            "page_load": 0.5,
            "element_wait": 3,
            "login_redirect": 2,
            "scan_interval": 0.05,
            "retry_delay": 0.05,
            "action_confirm": 0.2,
        }.items()
    }
    if config["timeout_settings"]["scan_interval"] == 0:
        raise ValueError("SEU_TIMEOUT_SCAN_INTERVAL must be greater than zero")
    return config
