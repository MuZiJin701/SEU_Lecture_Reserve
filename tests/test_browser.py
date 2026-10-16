import importlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from playwright.sync_api import TimeoutError

import browser
import captcha_ocr
import main


CONFIG = {
    "card_number": "test-card",
    "password": "test-password",
    "timeout_settings": {"page_load": 0, "login_redirect": 0.25, "element_wait": 0.5},
}


class BrowserTests(unittest.TestCase):
    def test_imports_do_not_load_credentials_or_start_browser(self):
        with patch("config.load_config") as load, patch("browser.setup_browser") as launch, patch(
            "playwright.sync_api.sync_playwright"
        ) as runtime:
            importlib.reload(main)
            importlib.reload(captcha_ocr)
        load.assert_not_called()
        launch.assert_not_called()
        runtime.assert_not_called()
        self.assertIsNone(main.CONFIG)

    def test_timeout_conversion_never_disables_timeout(self):
        self.assertEqual(browser.timeout_ms(0), 1)
        self.assertEqual(browser.timeout_ms(0.05), 50)
        self.assertEqual(browser.timeout_ms(3), 3000)

    def test_standard_chrome_channel_and_logging(self):
        playwright = MagicMock()
        with patch("browser.sys.platform", "linux"):
            browser.setup_browser(playwright)
        options = playwright.chromium.launch.call_args.kwargs
        self.assertEqual(options["channel"], "chrome")
        self.assertFalse(options["headless"])
        self.assertEqual(options["ignore_default_args"], ["--enable-logging"])
        self.assertNotIn("executable_path", options)

    @unittest.skipUnless(sys.platform == "win32", "Windows App Paths discovery")
    def test_windows_discovers_registered_chrome(self):
        playwright = MagicMock()
        with patch("winreg.OpenKey"), patch("winreg.QueryValue", return_value='"C:\\Chrome\\chrome.exe"'), patch(
            "browser.Path.is_file", return_value=True
        ):
            browser.setup_browser(playwright)
        self.assertEqual(
            playwright.chromium.launch.call_args.kwargs["executable_path"],
            "C:\\Chrome\\chrome.exe",
        )

    def test_login_waits_for_target_url_and_sms_budget(self):
        page = MagicMock()
        page.locator.return_value.first.is_visible.side_effect = [False, True, True, True]
        self.assertTrue(browser.login(page, CONFIG))
        page.goto.assert_called_once_with(browser.LECTURE_URL)
        calls = page.locator.return_value.first.fill.call_args_list
        self.assertEqual([call.args[0] for call in calls], ["test-card", "test-password"])
        options = page.wait_for_url.call_args
        pattern = options.args[0]
        self.assertTrue(pattern.match(browser.LECTURE_URL))
        self.assertFalse(pattern.match("https://auth.seu.edu.cn/login"))
        self.assertFalse(pattern.match("https://ehall.seu.edu.cn/error"))
        self.assertEqual(options.kwargs["timeout"], 250)

    def test_login_timeout_is_not_success_and_diagnostics_stay_local(self):
        page = MagicMock()
        page.locator.return_value.first.is_visible.side_effect = [False, True, True, True]
        page.wait_for_url.side_effect = TimeoutError("secret-session-value")
        page.content.return_value = "local diagnostic"
        with patch("browser.Path.write_text") as write, patch("builtins.print") as output:
            self.assertFalse(browser.login(page, CONFIG))
        write.assert_called_once_with("local diagnostic", encoding="utf-8")
        self.assertNotIn("secret-session-value", str(output.call_args_list))

    def test_both_entries_close_browser_when_work_raises(self):
        for module, work in ((main, "main_process"), (captcha_ocr, "collect_captchas")):
            with self.subTest(entry=module.__name__):
                launched = MagicMock()
                with patch.object(module, "load_config", return_value=CONFIG), patch.object(
                    module, "sync_playwright"
                ), patch("browser.setup_browser", return_value=launched), patch(
                    "browser.login", return_value=True
                ), patch.object(module, work, side_effect=RuntimeError("work failed")), patch.dict(
                    sys.modules, {"ddddocr": SimpleNamespace(DdddOcr=MagicMock())}
                ):
                    if module is main:
                        module.main()
                    else:
                        with self.assertRaises(RuntimeError):
                            module.main()
                launched.close.assert_called_once()

    def test_missing_config_prevents_browser_start(self):
        for module in (main, captcha_ocr):
            with self.subTest(entry=module.__name__), patch.object(
                module, "load_config", side_effect=ValueError("SEU_CARD_NUMBER is required")
            ), patch("browser.setup_browser") as launch:
                if module is main:
                    self.assertEqual(module.main(), 1)
                else:
                    with self.assertRaises(ValueError):
                        module.main()
                launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
