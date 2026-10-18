import importlib
import io
import sys
import unittest
from contextlib import redirect_stdout
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
    def test_legacy_school_http_redirect_is_upgraded_without_sending_it(self):
        route = MagicMock()
        route.request.url = "http://ehall.seu.edu.cn/app?ticket=SIMULATED&service=http%3A%2F%2Fehall.seu.edu.cn"
        browser.secure_request(route)
        route.fulfill.assert_called_once_with(status=307, headers={"location":
            "https://ehall.seu.edu.cn/app?ticket=SIMULATED&service=http%3A%2F%2Fehall.seu.edu.cn"})
        route.continue_.assert_not_called()
        route.abort.assert_not_called()
        route.reset_mock()
        route.request.url = "http://untrusted.invalid/"
        browser.secure_request(route)
        route.abort.assert_called_once()
        route.fulfill.assert_not_called()

    def test_imports_do_not_load_credentials_or_start_browser(self):
        with patch("config.load_config") as load, patch("browser.setup_browser") as launch, patch(
            "playwright.sync_api.sync_playwright"
        ) as runtime:
            importlib.reload(main)
            importlib.reload(captcha_ocr)
        load.assert_not_called()
        launch.assert_not_called()
        runtime.assert_not_called()

    def test_timeout_conversion_never_disables_timeout(self):
        self.assertEqual(browser.timeout_ms(0), 1)
        self.assertEqual(browser.timeout_ms(0.05), 50)
        self.assertEqual(browser.timeout_ms(3), 3000)

    def test_managed_chromium_supports_both_modes_without_system_chrome(self):
        playwright = MagicMock()
        playwright.chromium.executable_path = __file__
        for headless in (False, True):
            with self.subTest(headless=headless):
                browser.setup_browser(playwright, headless=headless)
                options = playwright.chromium.launch.call_args.kwargs
                self.assertEqual(options["channel"], "chromium")
                self.assertIs(options["headless"], headless)
                self.assertEqual(options["ignore_default_args"], ["--enable-logging"])
                self.assertNotIn("executable_path", options)

    def test_missing_chromium_prints_install_command_without_starting_browser(self):
        playwright = MagicMock()
        playwright.chromium.executable_path = "PRIVATE_BROWSER_PATH"
        output = io.StringIO()
        with patch("browser.Path.is_file", return_value=False), redirect_stdout(output):
            with self.assertRaisesRegex(FileNotFoundError, "chromium_not_installed"):
                browser.setup_browser(playwright)
        playwright.chromium.launch.assert_not_called()
        self.assertIn("uv run playwright install chromium", output.getvalue())
        self.assertNotIn("PRIVATE_BROWSER_PATH", output.getvalue())

    def test_login_waits_for_target_url_with_bounded_budget(self):
        page = MagicMock()
        page.url = "https://auth.seu.edu.cn/dist/#/login"
        page.locator.return_value.first.is_visible.side_effect = [False, False, True, True, True]
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

    def test_login_timeout_is_redacted_without_saving_authentication_data(self):
        page = MagicMock()
        page.url = "https://auth.seu.edu.cn/dist/#/login"
        page.locator.return_value.first.is_visible.side_effect = [False, False, True, True, True]
        page.wait_for_url.side_effect = TimeoutError("secret-session-value")
        page.content.return_value = "local diagnostic"
        with patch("browser.Path.write_text") as write, patch("builtins.print") as output:
            self.assertFalse(browser.login(page, CONFIG))
        write.assert_not_called()
        self.assertNotIn("secret-session-value", str(output.call_args_list))

    def test_captcha_entry_closes_browser_when_work_raises(self):
        for module, work in ((captcha_ocr, "collect_captchas"),):
            with self.subTest(entry=module.__name__):
                launched = MagicMock()
                with patch.object(module, "load_config", return_value=CONFIG), patch.object(
                    module, "sync_playwright"
                ), patch("browser.setup_browser", return_value=launched), patch(
                    "browser.login", return_value=True
                ), patch.object(module, work, side_effect=RuntimeError("work failed")), patch.dict(
                    sys.modules, {"ddddocr": SimpleNamespace(DdddOcr=MagicMock())}
                ):
                    with self.assertRaises(RuntimeError):
                        module.main([])
                launched.close.assert_called_once()

    def test_missing_config_prevents_browser_start(self):
        for module in (main, captcha_ocr):
            with self.subTest(entry=module.__name__), patch.object(
                module, "load_config", side_effect=ValueError("SEU_CARD_NUMBER is required")
            ), patch("browser.setup_browser") as launch:
                if module is main:
                    self.assertEqual(module.main([]), 1)
                else:
                    with self.assertRaises(ValueError):
                        module.main([])
                launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
