"""交互登录后采集验证码样本；导入时不启动浏览器。"""

import argparse
import base64
import time
from pathlib import Path

from playwright.sync_api import Error, sync_playwright

from browser import logged_in_page
from config import load_config


def collect_captchas(page):
    page.get_by_role("button", name="预约", exact=True).first.click()
    image = page.locator("#vcodeImg")
    image.wait_for(state="visible")
    output = Path("image_dataset")
    output.mkdir(exist_ok=True)
    for index in range(1001):
        try:
            source = image.get_attribute("src") or ""
            if "base64," not in source:
                print(f"第 {index + 1} 次未获取到验证码")
                continue
            data = base64.b64decode(source.split("base64,", 1)[1], validate=True)
            path = output / f"captcha_{index + 324}.jpg"
            path.write_bytes(data)
            print(f"Saved: {path}")
            image.click()
            time.sleep(1)
        except Exception as exc:
            print(f"采集错误: {type(exc).__name__}")
    print("验证码采集完成！")


def main(argv=None):
    parser = argparse.ArgumentParser(description='Collect captcha samples through the browser')
    parser.add_argument('--headless', action='store_true', help='run without a browser window (default: headed)')
    args = parser.parse_args(argv)
    config = load_config()
    config['headless'] = args.headless
    try:
        with sync_playwright() as playwright:
            with logged_in_page(playwright, config) as page:
                if page is not None:
                    collect_captchas(page)
                else:
                    return 1
    except Error as exc:
        print(f"❌ 浏览器操作未完成（{type(exc).__name__}），请检查安全网络诊断与浏览器状态")
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n👋 用户中断采集")
