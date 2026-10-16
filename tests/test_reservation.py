"""Offline browser checks: only about:blank and in-memory HTML are used."""

import io
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from unittest.mock import Mock, patch

from playwright.sync_api import Error, sync_playwright

import main
from browser import _login_control, setup_browser


def card(title="讲座 A", status="预约", category="类别 A", location="无锡校区 教室"):
    return f"""
    <div class="activity-container">
      <div class="hdxq-hdlx"><span class="mint-text">{category}</span></div>
      <div class="activity-name"><span class="mint-text">{title}</span></div>
      <div title="item.JZDD">{location}</div>
      <div class="activity-text"><span class="mint-text">地点</span>
        <span class="mint-text">2026/10/20/10:00:00 - 2026/10/20/11:00:00</span>
      </div>
      <button onclick="document.querySelector('#dialog').hidden=false">{status}</button>
    </div>"""


class ReservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = setup_browser(cls.playwright)
        except Exception:
            cls.playwright.stop()
            raise

    @classmethod
    def tearDownClass(cls):
        try:
            cls.browser.close()
        finally:
            cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.page.goto("about:blank")
        self.page.route("**/*", lambda route: route.abort())
        self.page.set_default_timeout(200)
        self.config = {
            "preferred_lectures": [],
            "required_categories": ["类别 A"],
            "preferred_campus": ["无锡校区"],
            "enable_online": True,
            "enable_offline": True,
            "timeout_settings": {"element_wait": 0.2, "action_confirm": 0, "retry_delay": 0},
        }
        self.ocr = Mock()
        self.ocr.classification.return_value = "ABCD"
        for name, value in (("page", self.page), ("CONFIG", self.config), ("ocr", self.ocr)):
            setting = patch.object(main, name, value)
            setting.start()
            self.addCleanup(setting.stop)

    def test_vpn_ipv6_override_keeps_local_chrome_pages_working(self):
        chrome = setup_browser(self.playwright, "2001:db8::10")
        try:
            page = chrome.new_page()
            page.route("**/*", lambda route: route.abort())
            page.goto("about:blank")
            page.set_content('<p role="status">offline page ready</p>')
            self.assertEqual(page.get_by_role("status").inner_text(), "offline page ready")
        finally:
            chrome.close()

    def test_scan_errors_do_not_print_playwright_call_logs(self):
        output = io.StringIO()
        with redirect_stdout(output), patch.object(
            self.page, "locator", side_effect=Error("?ticket=private-ticket")
        ):
            self.assertFalse(main.is_time_conflict(datetime(2026, 10, 20), datetime(2026, 10, 21)))
        element = Mock()
        element.locator.side_effect = Error("?ticket=private-ticket")
        with redirect_stdout(output):
            self.assertIsNone(main.parse_lecture(element))
        self.assertNotIn("private-ticket", output.getvalue())
        self.assertIn("Error", output.getvalue())

    def render(self, confirm_script="", cards=None):
        self.page.set_content(
            (cards if cards is not None else card())
            + """<p>其他操作成功</p><div id="dialog" hidden>
            <img id="vcodeImg" src="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMCIgaGVpZ2h0PSIxMCIvPg==">
            <input id="vcodeInput"><button id="jqalert_yes_btn">确认</button>
            <button class="mint-msgbox-btn" onclick="this.parentElement.hidden=true">关闭</button>
            </div><script>document.querySelector('#jqalert_yes_btn').onclick = () => {"""
            + confirm_script + "};</script>"
        )
        return main.parse_lecture(self.page.locator(".activity-container").first)

    def test_parse_filter_and_conflicts(self):
        lecture = self.render(cards=card() + card("已预约讲座", "取消预约"))
        self.assertEqual(lecture["campus"], "无锡校区")
        self.assertEqual(lecture["start_time"], datetime(2026, 10, 20, 10))
        self.assertFalse(main.validate_lecture(lecture))
        self.config["preferred_lectures"] = ["讲座 A"]
        self.config["enable_offline"] = False
        self.assertTrue(main.validate_lecture(lecture))
        self.config["preferred_lectures"] = ["其他标题"]
        self.assertFalse(main.validate_lecture(lecture))

    def test_login_selector_priority_ignores_other_text_fields(self):
        self.page.set_content(
            '<input type="text" id="search"><input type="text" id="username">'
        )
        _login_control(self.page, ["#username", "input[type='text']"]).fill("test-card")
        self.assertEqual(self.page.locator("#username").input_value(), "test-card")
        self.assertEqual(self.page.locator("#search").input_value(), "")

    def test_online_and_offline_switches(self):
        lecture = self.render()
        self.assertTrue(main.validate_lecture(lecture))
        self.config["enable_offline"] = False
        self.assertFalse(main.validate_lecture(lecture))
        lecture["title"] = "线上讲座"
        lecture["campus"] = "线上会议"
        self.assertTrue(main.validate_lecture(lecture))
        self.config["enable_online"] = False
        self.assertFalse(main.validate_lecture(lecture))

    def test_success_requires_target_state_and_waits_for_delayed_update(self):
        lecture = self.render("""
            setTimeout(() => {
                const button = document.querySelector('.activity-container button');
                button.textContent = '取消预约';
                button.onclick = () => { window.cancelled = true; };
                document.querySelector('#dialog').hidden = true;
            }, 40);
        """)
        self.assertTrue(main.reserve_lecture(lecture))
        self.ocr.classification.assert_called_once()
        self.assertEqual(self.page.locator("#vcodeInput").input_value(), "ABCD")
        self.assertIsNone(self.page.evaluate("window.cancelled"))

    def test_unrelated_success_text_and_blank_url_do_not_count(self):
        lecture = self.render()
        self.assertFalse(main.reserve_lecture(lecture))
        self.assertEqual(self.ocr.classification.call_count, 3)

    def test_retry_does_not_click_cancel_after_late_success(self):
        lecture = self.render("window.submitted = true;")
        original_sleep = main.time.sleep
        sleeps = 0

        def late_result(seconds):
            nonlocal sleeps
            sleeps += 1
            if sleeps == 2:
                self.page.evaluate("""() => {
                    const button = document.querySelector('.activity-container button');
                    button.textContent = '取消预约';
                    button.onclick = () => { window.cancelled = true; };
                }""")
            original_sleep(seconds)

        with patch("main.time.sleep", side_effect=late_result):
            self.assertTrue(main.reserve_lecture(lecture))
        self.ocr.classification.assert_called_once()
        self.assertIsNone(self.page.evaluate("window.cancelled"))

    def test_reordered_cards_do_not_change_target(self):
        lecture = self.render(cards=card() + card("讲座 B"))
        self.page.evaluate("""() => {
            const a = document.querySelector('.activity-container');
            a.parentElement.appendChild(a);
            a.querySelector('button').textContent = '取消预约';
        }""")
        self.assertTrue(main.reserve_lecture(lecture))
        self.ocr.classification.assert_not_called()

    def test_duplicate_titles_are_not_submitted(self):
        lecture = self.render(cards=card() + card())
        self.assertFalse(main.reserve_lecture(lecture))
        self.ocr.classification.assert_not_called()

    def test_invalid_captcha_is_not_submitted(self):
        lecture = self.render()
        self.page.locator("#vcodeImg").evaluate("img => img.src = 'data:image/svg+xml,invalid'")
        self.assertFalse(main.reserve_lecture(lecture))
        self.ocr.classification.assert_not_called()


if __name__ == "__main__":
    unittest.main()
