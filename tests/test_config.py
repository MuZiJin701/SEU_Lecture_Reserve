import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from config import load_config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.env_path = Path(self.directory.name) / ".env"
        self.config_path = patch("config.__file__", str(self.env_path.with_name("config.py")))
        self.config_path.start()
        self.addCleanup(self.config_path.stop)
        self.environment = patch.dict(
            os.environ,
            {"SEU_CARD_NUMBER": "test-card", "SEU_PASSWORD": "test-password"},
            clear=True,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_loads_env_beside_config(self):
        self.env_path.write_text(
            "SEU_CARD_NUMBER=dotenv-card\n"
            "SEU_PASSWORD='dotenv # password'\n"
            "SEU_PREFERRED_CAMPUS='[\"无锡校区\"]'\n"
            "SEU_ENABLE_OFFLINE=false\n"
            "SEU_TIMEOUT_LOGIN_REDIRECT=60\n",
            encoding="utf-8-sig",
        )
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()
        self.assertEqual(config["card_number"], "dotenv-card")
        self.assertEqual(config["password"], "dotenv # password")
        self.assertEqual(config["preferred_campus"], ["无锡校区"])
        self.assertFalse(config["enable_offline"])
        self.assertEqual(config["timeout_settings"]["login_redirect"], 60)

    def test_process_environment_overrides_env_file(self):
        self.env_path.write_text(
            "SEU_CARD_NUMBER=dotenv-card\n"
            "SEU_PASSWORD=dotenv-password\n"
            "SEU_ENABLE_ONLINE=false\n",
            encoding="utf-8",
        )
        with patch.dict(os.environ, {"SEU_ENABLE_ONLINE": "true"}):
            config = load_config()
        self.assertEqual(config["card_number"], "test-card")
        self.assertEqual(config["password"], "test-password")
        self.assertTrue(config["enable_online"])

    def test_env_example_matches_defaults(self):
        defaults = load_config()
        example = Path(__file__).resolve().parents[1] / ".env.example"
        self.env_path.write_bytes(example.read_bytes())
        self.assertEqual(load_config(), defaults)

    def test_defaults_and_overrides(self):
        config = load_config()
        self.assertEqual(config["preferred_lectures"], [])
        self.assertEqual(len(config["required_categories"]), 5)
        self.assertTrue(config["enable_offline"])
        self.assertEqual(config["timeout_settings"]["scan_interval"], 0.05)
        with patch.dict(os.environ, {
            "SEU_PREFERRED_LECTURES": '["讲座 A", "讲座 B"]',
            "SEU_REQUIRED_CATEGORIES": "[]",
            "SEU_PREFERRED_CAMPUS": '["九龙湖"]',
            "SEU_ENABLE_OFFLINE": "false",
            "SEU_ENABLE_ONLINE": "FALSE",
            "SEU_TIMEOUT_LOGIN_REDIRECT": "60",
            "SEU_TIMEOUT_RETRY_DELAY": "0",
        }):
            config = load_config()
        self.assertEqual(config["preferred_lectures"], ["讲座 A", "讲座 B"])
        self.assertEqual(config["required_categories"], [])
        self.assertEqual(config["preferred_campus"], ["九龙湖"])
        self.assertFalse(config["enable_offline"])
        self.assertFalse(config["enable_online"])
        self.assertEqual(config["timeout_settings"]["login_redirect"], 60)
        self.assertEqual(config["timeout_settings"]["retry_delay"], 0)

    def test_optional_vpn_ip_is_validated_without_echoing_input(self):
        self.assertEqual(load_config()["vpn_ip"], "")
        for value, expected in (("", ""), ("   ", ""), (" 192.0.2.10 ", "192.0.2.10"),
                                ("2001:db8::10", "2001:db8::10")):
            with self.subTest(value=value), patch.dict(os.environ, {"SEU_VPN_IP": value}):
                self.assertEqual(load_config()["vpn_ip"], expected)
        for value in ("vpn.example", "https://192.0.2.10", "192.0.2.10:443", "bad-secret",
                      "::1%scope", "192.0.2.10,MAP * 127.0.0.1"):
            with self.subTest(value=value), patch.dict(os.environ, {"SEU_VPN_IP": value}):
                with self.assertRaises(ValueError) as error:
                    load_config()
                self.assertIn("SEU_VPN_IP", str(error.exception))
                self.assertNotIn(value, str(error.exception))

    def test_credentials_are_required_and_password_is_preserved(self):
        for name in ("SEU_CARD_NUMBER", "SEU_PASSWORD"):
            for value in (None, "", "   "):
                with self.subTest(name=name, value=value), patch.dict(os.environ):
                    if value is None:
                        del os.environ[name]
                    else:
                        os.environ[name] = value
                    with self.assertRaisesRegex(ValueError, name):
                        load_config()
        with patch.dict(os.environ, {"SEU_PASSWORD": "  test-password  "}):
            self.assertEqual(load_config()["password"], "  test-password  ")

    def test_invalid_values_fail_without_echoing_the_input(self):
        cases = {
            "SEU_PREFERRED_LECTURES": ("", "not-json", '"title"', "{}", "[1]", '[""]'),
            "SEU_ENABLE_ONLINE": ("", "yes", "1"),
            "SEU_TIMEOUT_PAGE_LOAD": ("", "invalid", "-1", "nan", "inf"),
            "SEU_TIMEOUT_SCAN_INTERVAL": ("0",),
        }
        for name, values in cases.items():
            for value in values:
                with self.subTest(name=name, value=value), patch.dict(os.environ, {name: value}):
                    with self.assertRaises(ValueError) as error:
                        load_config()
                    self.assertTrue(str(error.exception).startswith(name))
                    self.assertNotIn("test-password", str(error.exception))


if __name__ == "__main__":
    unittest.main()
