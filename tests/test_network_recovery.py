"""Exercise shared login recovery with a controlled browser boundary, never the network."""

import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from playwright.sync_api import Error, TimeoutError

import browser
import captcha_ocr
import main


class NetworkRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "card_number": "test-card", "password": "test-password", "vpn_ip": "192.0.2.10",
            "timeout_settings": {"page_load": 0, "login_redirect": 0.1, "element_wait": 0.1},
        }
        self.output = io.StringIO()
        for context in (redirect_stdout(self.output), patch("browser.sys.platform", "linux"),
                        patch("browser.Path.write_text")):
            context.__enter__()
            self.addCleanup(context.__exit__, None, None, None)

    def make_browser(self, failure=None, **request_options):
        launched = MagicMock()
        page = launched.new_page.return_value
        page.locator.return_value.first.is_visible.return_value = True
        events = {}
        page.on.side_effect = events.__setitem__
        if failure:
            def navigate(url):
                self.fail_request(page, events, failure, **request_options)
                raise Error("private-password Cookie=private-cookie ?ticket=private-ticket")
            page.goto.side_effect = navigate
        return launched, page, events

    def fail_request(self, page, events, failure, host="vpn.seu.edu.cn", main_frame=True,
                     navigation=True):
        request = SimpleNamespace(
            url=f"https://{host}/private-path?ticket=private-ticket",
            failure=failure, frame=page.main_frame if main_frame else object(),
            is_navigation_request=lambda: navigation,
        )
        events["requestfailed"](request)

    def test_initial_network_failure_restarts_once_and_closes_both_browsers(self):
        first, _, _ = self.make_browser("net::ERR_NAME_NOT_RESOLVED")
        second, page, _ = self.make_browser()
        runtime = MagicMock()
        def launch(**options):
            if not runtime.chromium.launch.call_count == 1:
                first.close.assert_called_once()
                return second
            return first
        runtime.chromium.launch.side_effect = launch
        with browser.logged_in_page(runtime, self.config) as obtained:
            self.assertIs(obtained, page)
            second.close.assert_not_called()
        second.close.assert_called_once()
        launches = runtime.chromium.launch.call_args_list
        self.assertEqual(len(launches), 2)
        self.assertFalse(any("host-resolver-rules" in arg for arg in launches[0].kwargs["args"]))
        self.assertIn("--host-resolver-rules=MAP vpn.seu.edu.cn 192.0.2.10", launches[1].kwargs["args"])
        output = self.output.getvalue()
        self.assertIn("vpn.seu.edu.cn", output)
        self.assertIn("ERR_NAME_NOT_RESOLVED", output)
        for private in ("private-password", "private-cookie", "private-ticket", "private-path"):
            self.assertNotIn(private, output)

    def test_both_entries_start_work_only_after_backup_login(self):
        for module, work in ((main, "main_process"), (captcha_ocr, "collect_captchas")):
            with self.subTest(entry=module.__name__):
                first, _, _ = self.make_browser("net::ERR_CONNECTION_CLOSED")
                second, page, _ = self.make_browser()
                runtime = MagicMock()
                runtime.chromium.launch.side_effect = [first, second]
                manager = MagicMock()
                manager.__enter__.return_value = runtime
                with patch.object(module, "sync_playwright", return_value=manager), patch.object(
                    module, "load_config", return_value=self.config
                ), patch.object(module, work) as worker, patch.dict(
                    "sys.modules", {"ddddocr": SimpleNamespace(DdddOcr=MagicMock())}
                ):
                    self.assertIsNone(module.main())
                self.assertEqual(runtime.chromium.launch.call_count, 2)
                worker.assert_called_once_with(*(() if module is main else (page,)))
                if module is main:
                    self.assertIs(main.page, page)
                first.close.assert_called_once()
                second.close.assert_called_once()

    def test_allowed_failures_stop_after_one_backup_attempt(self):
        for error in ("ERR_NAME_NOT_RESOLVED", "ERR_CONNECTION_CLOSED", "ERR_CONNECTION_RESET"):
            with self.subTest(error=error):
                first, _, _ = self.make_browser("net::" + error)
                second, _, _ = self.make_browser("net::" + error)
                runtime = MagicMock()
                runtime.chromium.launch.side_effect = [first, second]
                with browser.logged_in_page(runtime, self.config) as page:
                    self.assertIsNone(page)
                self.assertEqual(runtime.chromium.launch.call_count, 2)
                first.close.assert_called_once()
                second.close.assert_called_once()

    def test_success_or_missing_backup_never_restarts(self):
        for failure, address in ((None, "192.0.2.10"), (None, ""),
                                 ("net::ERR_CONNECTION_CLOSED", "")):
            with self.subTest(failure=failure, address=address):
                launched, original, _ = self.make_browser(failure)
                runtime = MagicMock()
                runtime.chromium.launch.return_value = launched
                with browser.logged_in_page(runtime, {**self.config, "vpn_ip": address}) as page:
                    self.assertIs(page, None if failure else original)
                runtime.chromium.launch.assert_called_once()
                launched.close.assert_called_once()

    def test_unrelated_requests_and_authentication_errors_do_not_enable_recovery(self):
        cases = (
            ("net::ERR_CONNECTION_CLOSED", {"host": "auth.seu.edu.cn"}),
            ("net::ERR_CONNECTION_CLOSED", {"host": "vpn.seu.edu.cn.attacker.invalid"}),
            ("net::ERR_CONNECTION_CLOSED", {"main_frame": False}),
            ("net::ERR_CONNECTION_CLOSED", {"navigation": False}),
            ("net::ERR_CERT_AUTHORITY_INVALID", {}),
            ("net::ERR_TIMED_OUT", {}),
            ("private-password ?ticket=private-ticket", {}),
        )
        for failure, options in cases:
            with self.subTest(failure=failure, options=options):
                launched, _, _ = self.make_browser(failure, **options)
                runtime = MagicMock()
                runtime.chromium.launch.return_value = launched
                with browser.logged_in_page(runtime, self.config) as page:
                    self.assertIsNone(page)
                runtime.chromium.launch.assert_called_once()
        for private in ("attacker.invalid", "private-password", "private-ticket"):
            self.assertNotIn(private, self.output.getvalue())

    def test_recovered_navigation_does_not_trigger_backup_on_authentication_timeout(self):
        launched, page, events = self.make_browser()
        def navigate(url):
            self.fail_request(page, events, "net::ERR_CONNECTION_CLOSED")
            events["requestfinished"](SimpleNamespace(
                frame=page.main_frame, is_navigation_request=lambda: True,
            ))
        page.goto.side_effect = navigate
        page.locator.return_value.first.is_visible.side_effect = [False, True, True, True]
        page.wait_for_url.side_effect = TimeoutError("private-password")
        runtime = MagicMock()
        runtime.chromium.launch.return_value = launched
        with browser.logged_in_page(runtime, self.config) as obtained:
            self.assertIsNone(obtained)
        runtime.chromium.launch.assert_called_once()

    def test_success_and_later_work_failures_cannot_restart_browser(self):
        launched, page, events = self.make_browser()
        runtime = MagicMock()
        runtime.chromium.launch.return_value = launched
        def navigate(url):
            self.fail_request(page, events, "net::ERR_CONNECTION_CLOSED")
        page.goto.side_effect = navigate
        with self.assertRaises(KeyboardInterrupt):
            with browser.logged_in_page(runtime, self.config) as obtained:
                self.assertIs(obtained, page)
                page.goto.side_effect = Error("private-password")
                self.fail_request(page, events, "net::ERR_CONNECTION_RESET")
                self.assertFalse(browser.login(page, self.config))
                raise KeyboardInterrupt
        runtime.chromium.launch.assert_called_once()
        launched.close.assert_called_once()

    def test_failed_business_request_is_reported_without_restart(self):
        launched, page, events = self.make_browser()
        runtime = MagicMock()
        runtime.chromium.launch.return_value = launched
        with browser.logged_in_page(runtime, self.config):
            self.fail_request(page, events, "net::ERR_CONNECTION_RESET",
                              host="ehall.seu.edu.cn", navigation=False)
        self.assertIn("host=ehall.seu.edu.cn reason=ERR_CONNECTION_RESET", self.output.getvalue())
        self.assertNotIn("private-ticket", self.output.getvalue())
        runtime.chromium.launch.assert_called_once()

    def test_both_entries_redact_playwright_errors_during_work(self):
        for module, work in ((main, "main_process"), (captcha_ocr, "collect_captchas")):
            with self.subTest(entry=module.__name__):
                launched, _, _ = self.make_browser()
                runtime = MagicMock()
                runtime.chromium.launch.return_value = launched
                manager = MagicMock()
                manager.__enter__.return_value = runtime
                with patch.object(module, "sync_playwright", return_value=manager), patch.object(
                    module, "load_config", return_value=self.config
                ), patch.object(module, work, side_effect=Error("?ticket=private-ticket")), patch.dict(
                    "sys.modules", {"ddddocr": SimpleNamespace(DdddOcr=MagicMock())}
                ):
                    self.assertEqual(module.main(), 1)
                launched.close.assert_called_once()
        self.assertNotIn("private-ticket", self.output.getvalue())

    def test_page_creation_and_backup_launch_failures_clean_up(self):
        launched, _, _ = self.make_browser()
        launched.new_page.side_effect = RuntimeError("page creation failed")
        runtime = MagicMock()
        runtime.chromium.launch.return_value = launched
        with self.assertRaises(RuntimeError):
            with browser.logged_in_page(runtime, self.config):
                self.fail("Work must not start")
        launched.close.assert_called_once()
        first, _, _ = self.make_browser("net::ERR_CONNECTION_CLOSED")
        runtime.chromium.launch.side_effect = [first, RuntimeError("backup launch failed")]
        with self.assertRaises(RuntimeError):
            with browser.logged_in_page(runtime, self.config):
                self.fail("Work must not start")
        first.close.assert_called_once()

    def test_ipv6_backup_preserves_domain_and_certificate_settings(self):
        first, _, _ = self.make_browser("net::ERR_CONNECTION_CLOSED")
        second, _, _ = self.make_browser()
        runtime = MagicMock()
        runtime.chromium.launch.side_effect = [first, second]
        with browser.logged_in_page(runtime, {**self.config, "vpn_ip": "2001:db8::10"}):
            pass
        options = runtime.chromium.launch.call_args.kwargs
        self.assertIn("--host-resolver-rules=MAP vpn.seu.edu.cn [2001:db8::10]", options["args"])
        self.assertNotIn("--ignore-certificate-errors", options["args"])
        self.assertNotIn("--no-proxy-server", options["args"])


if __name__ == "__main__":
    unittest.main()
