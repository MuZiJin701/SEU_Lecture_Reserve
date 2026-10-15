"""Shared Chrome startup and interactive login for both browser entry points."""

import re
import sys
import time
from pathlib import Path

from playwright.sync_api import Error


LECTURE_URL = "https://ehall.seu.edu.cn/gsapp/sys/yddjzxxtjappseu/*default/index.do#/hdyy"


def timeout_ms(seconds):
    # Playwright treats zero as unlimited; config zero must remain a bounded wait.
    return max(1, seconds * 1000)


def setup_browser(playwright):
    options = {
        "channel": "chrome",
        "headless": False,
        "ignore_default_args": ["--enable-logging"],
        "args": ["--disable-gpu", "--window-size=1920,1080"],
    }
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
        print(f"❌ 登录未完成（{type(exc).__name__}），请检查凭据或延长短信认证等待时间")
        try:
            Path("error_page_source.html").write_text(page.content(), encoding="utf-8")
            page.screenshot(path="error_login.png")
            print("💾 已保存本地错误页面和截图，请勿上传认证信息")
        except (Error, OSError):
            print("无法保存登录诊断文件")
        return False
