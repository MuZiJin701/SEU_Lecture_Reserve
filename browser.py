"""Shared Chrome startup and interactive login for both browser entry points."""

import re
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Error


LECTURE_URL = "https://ehall.seu.edu.cn/gsapp/sys/yddjzxxtjappseu/*default/index.do#/hdyy"
VPN_HOST = "vpn.seu.edu.cn"
RETRYABLE_NETWORK_ERRORS = {"ERR_NAME_NOT_RESOLVED", "ERR_CONNECTION_CLOSED", "ERR_CONNECTION_RESET"}
NETWORK_ERRORS = RETRYABLE_NETWORK_ERRORS | {
    "ERR_ABORTED", "ERR_FAILED", "ERR_TIMED_OUT", "ERR_CONNECTION_TIMED_OUT",
    "ERR_INTERNET_DISCONNECTED", "ERR_ADDRESS_UNREACHABLE", "ERR_CONNECTION_REFUSED",
    "ERR_CERT_AUTHORITY_INVALID", "ERR_CERT_COMMON_NAME_INVALID", "ERR_CERT_DATE_INVALID",
    "ERR_SSL_PROTOCOL_ERROR",
}


def timeout_ms(seconds):
    # Playwright treats zero as unlimited; config zero must remain a bounded wait.
    return max(1, seconds * 1000)


def setup_browser(playwright, vpn_ip=""):
    options = {
        "channel": "chrome",
        "headless": False,
        "ignore_default_args": ["--enable-logging"],
        "args": ["--disable-gpu", "--window-size=1920,1080"],
    }
    if vpn_ip:
        address = f"[{vpn_ip}]" if ":" in vpn_ip else vpn_ip
        options["args"].append(f"--host-resolver-rules=MAP {VPN_HOST} {address}")
    if sys.platform == "win32":
        import winreg

        # App Paths also discovers Chrome installed outside the standard location.
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(
                    hive, r"Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
                ) as key:
                    executable = winreg.QueryValue(key, None).strip('"')
                if Path(executable).is_file():
                    options["executable_path"] = executable
                    break
            except OSError:
                continue
    return playwright.chromium.launch(**options)


@contextmanager
def logged_in_page(playwright, config):
    """Own both browser attempts; recovery is limited to the initial login."""
    for vpn_ip in ("", config.get("vpn_ip", "")):
        browser = setup_browser(playwright, vpn_ip)
        try:
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.set_default_timeout(timeout_ms(config["timeout_settings"]["element_wait"]))
            logging_in = True
            vpn_failed = False

            def request_failed(request):
                nonlocal vpn_failed
                try:
                    host = urlsplit(request.url).hostname
                except ValueError:
                    host = None
                safe_host = host if host in {VPN_HOST, "auth.seu.edu.cn", "ehall.seu.edu.cn"} else "<unknown>"
                error = (request.failure or "").removeprefix("net::")
                error = error if error in NETWORK_ERRORS else "UNKNOWN_NETWORK_ERROR"
                print(f"❌ 网络请求失败 host={safe_host} reason={error}")
                if logging_in and request.is_navigation_request() and request.frame == page.main_frame:
                    vpn_failed = host == VPN_HOST and error in RETRYABLE_NETWORK_ERRORS

            def request_finished(request):
                nonlocal vpn_failed
                if logging_in and request.is_navigation_request() and request.frame == page.main_frame:
                    vpn_failed = False

            page.on("requestfailed", request_failed)
            page.on("requestfinished", request_finished)
            if login(page, config):
                logging_in = False
                yield page
                return
            logging_in = False
            if vpn_ip or not config.get("vpn_ip") or not vpn_failed:
                yield None
                return
            print("🔄 学校 VPN 网络连接失败，将使用备用 IP 重启一次并重新登录，可能再次需要短信认证")
        finally:
            browser.close()


def _login_control(page, selectors):
    page.locator(", ".join(f"{selector}:visible" for selector in selectors)).first.wait_for()
    for selector in selectors:
        control = page.locator(f"{selector}:visible").first
        if control.is_visible():
            return control
    raise Error("登录控件在等待后消失")


def login(page, config):
    """Submit credentials, then allow manual SMS authentication within the timeout."""
    try:
        print("🌐 正在加载登录页面...")
        page.goto(LECTURE_URL)
        time.sleep(config["timeout_settings"]["page_load"])
        if page.locator(".activity-container").first.is_visible():
            return True
        _login_control(page, [
            "#username", "input[name='username']", ".input-username-pc input",
            "input[placeholder*='号']", "input[type='text']",
        ]).fill(config["card_number"])
        _login_control(page, [
            "#password", "input[name='password']", "input[type='password']",
            ".input-password-pc input",
        ]).fill(config["password"])
        _login_control(page, [
            "button[type='submit']", ".login-button-pc", "input[type='submit']",
        ]).click()
        print("✅ 登录信息已提交，请在浏览器中完成可能出现的短信认证...")
        page.wait_for_url(
            re.compile(r"^https://ehall\.seu\.edu\.cn/.*#/hdyy(?:\?.*)?$"),
            timeout=timeout_ms(config["timeout_settings"]["login_redirect"]),
            wait_until="domcontentloaded",
        )
        print("✅ 登录成功！")
        return True
    except Error as exc:
        # Playwright call logs can contain filled credentials; keep diagnostics local.
        print(f"❌ 登录未完成（{type(exc).__name__}），请检查网络与浏览器中的认证状态")
        try:
            Path("error_page_source.html").write_text(page.content(), encoding="utf-8")
            page.screenshot(path="error_login.png")
            print("💾 已保存本地错误页面和截图，请勿上传认证信息")
        except (Error, OSError):
            print("无法保存登录诊断文件")
        return False
