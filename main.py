"""东南大学素质讲座预约：交互登录、筛选、OCR 与预约。"""

import base64
import re
import time
from datetime import datetime

from playwright.sync_api import Error, TimeoutError, expect, sync_playwright

from browser import logged_in_page, login, timeout_ms
from config import load_config


CONFIG = None
ocr = None
page = None


def is_time_conflict(new_start, new_end):
    """检查与当前页面已预约讲座的时间重叠，保留现有端点规则。"""
    try:
        for element in page.locator(".activity-container").all():
            lecture = parse_lecture(element)
            if lecture and lecture["status"] == "取消预约":
                if new_start <= lecture["end_time"] and new_end >= lecture["start_time"]:
                    return True
        return False
    except Exception as exc:
        print(f"‼ 时间冲突检查异常: {type(exc).__name__}")
        return False


def parse_lecture(element):
    """从讲座卡片 Locator 读取基础信息、起止时间和按钮状态。"""
    try:
        category = element.locator(".hdxq-hdlx .mint-text").first.inner_text().strip()
        title = element.locator(".activity-name .mint-text").first.inner_text().strip()
        location = element.locator("div[title='item.JZDD']").first.inner_text().strip()
        time_text = element.locator(".activity-text .mint-text").nth(1).inner_text()
        matches = re.findall(r"\d{4}/\d{2}/\d{2}/\d{2}:\d{2}:\d{2}", time_text)
        return {
            "category": category,
            "title": title,
            "campus": _extract_campus(location),
            "start_time": datetime.strptime(matches[0], "%Y/%m/%d/%H:%M:%S"),
            "end_time": datetime.strptime(matches[1], "%Y/%m/%d/%H:%M:%S"),
            "status": element.locator("button").first.inner_text().strip(),
        }
    except Exception as exc:
        print(f"❌ 讲座解析失败: {type(exc).__name__}")
        return None


def _extract_campus(location):
    campus_match = re.match(r"^(.+?校区)", location)
    return campus_match.group(1) if campus_match else location


def validate_lecture(lecture):
    """保留标题指定模式和常规筛选规则。"""
    if lecture["status"] != "预约":
        return False
    if CONFIG["preferred_lectures"]:
        return lecture["title"] in CONFIG["preferred_lectures"]
    if lecture["category"] not in CONFIG["required_categories"]:
        return False
    if lecture["campus"] not in CONFIG["preferred_campus"] and "线上" not in lecture["title"]:
        return False
    is_online = "线上" in lecture["title"]
    if (is_online and not CONFIG["enable_online"]) or (
        not is_online and not CONFIG["enable_offline"]
    ):
        return False
    if is_time_conflict(lecture["start_time"], lecture["end_time"]):
        print(f"‼ 时间冲突: {lecture['title']}")
        return False
    return True


def reserve_lecture(lecture):
    """提交验证码后核对目标卡片，重试只点击明确的预约按钮。"""
    # shortcut: re-find by unique title; use a stable lecture ID when available.
    target = page.locator(".activity-container").filter(
        has=page.locator(".activity-name .mint-text").filter(
            has_text=re.compile(r"^\s*" + re.escape(lecture["title"]) + r"\s*$")
        )
    )
    for attempt in range(3):
        try:
            if target.count() != 1:
                print("❌ 目标讲座无法唯一定位，暂缓预约")
                return False
            booked = target.get_by_role("button", name="取消预约", exact=True)
            if booked.is_visible():
                return True
            print(f"🔄 尝试预约: {lecture['title']} (尝试 {attempt + 1}/3)")
            target.get_by_role("button", name="预约", exact=True).click()
            image = page.locator("#vcodeImg")
            expect(image).to_be_visible(timeout=timeout_ms(CONFIG["timeout_settings"]["element_wait"]))
            source = image.get_attribute("src") or ""
            if "base64," not in source:
                raise ValueError("验证码不是预期的 base64 图片")
            captcha_text = ocr.classification(
                base64.b64decode(source.split("base64,", 1)[1], validate=True)
            )
            page.locator("#vcodeInput").fill(captcha_text)
            page.locator("#jqalert_yes_btn").click()
            time.sleep(CONFIG["timeout_settings"]["action_confirm"])
            expect(booked).to_be_visible(
                timeout=timeout_ms(CONFIG["timeout_settings"]["element_wait"])
            )
            print(f"✅ 预约成功！ {lecture['title']}")
            return True
        except (Error, AssertionError, ValueError) as exc:
            print(f"  预约尝试 {attempt + 1} 未确认成功: {type(exc).__name__}")
            try:
                close_button = page.locator(".mint-msgbox-btn").first
                if close_button.is_visible():
                    close_button.click()
            except Error:
                pass
            time.sleep(CONFIG["timeout_settings"]["retry_delay"])
    print(f"❌ 预约未确认成功，已达到最大重试次数: {lecture['title']}")
    return False


def lecture_scanner():
    """刷新页面，解析并排序符合现有筛选条件的讲座。"""
    page.reload()
    try:
        page.locator(".activity-container").first.wait_for(state="visible")
    except TimeoutError:
        return []
    valid_lectures = []
    for element in page.locator(".activity-container").all():
        lecture = parse_lecture(element)
        if lecture and validate_lecture(lecture):
            valid_lectures.append(lecture)
    return sorted(valid_lectures, key=_sort_priority)


def _sort_priority(lecture):
    """保留现有类别、线上优先及开始时间排序。"""
    required_priority = 0 if lecture["category"] in CONFIG["required_categories"] else 1
    is_online = "线上" in lecture["title"]
    campus_priority = 0 if (is_online or lecture["campus"] == CONFIG["preferred_campus"]) else 1
    return required_priority, campus_priority, lecture["start_time"]


def main_process():
    """持续扫描，确认预约一场后退出。"""
    no_lecture_reported = False
    scan_count = 0
    while True:
        try:
            scan_count += 1
            print(f"\r🔍 扫描次数: {scan_count}", end="")
            lectures = lecture_scanner()
            if lectures:
                print(f"\n✅ 发现 {len(lectures)} 个符合条件的讲座")
                for lecture in lectures[:3]:
                    print(f"  {lecture['title']}")
                if reserve_lecture(lectures[0]):
                    print("🎉 预约流程完成，程序退出")
                    break
                print("🔄 未确认预约成功，继续扫描...")
                time.sleep(CONFIG["timeout_settings"]["retry_delay"])
            elif not no_lecture_reported:
                print("\n⏳ 未发现新讲座，持续扫描中")
                no_lecture_reported = True
            time.sleep(CONFIG["timeout_settings"]["scan_interval"])
        except Exception as exc:
            no_lecture_reported = False
            print(f"\n‼ 发生异常: {type(exc).__name__}")
            try:
                page.reload()
                time.sleep(CONFIG["timeout_settings"]["page_load"])
            except Error:
                print("❌ 页面刷新失败，尝试重新登录")
                if not login(page, CONFIG):
                    break


def main():
    global CONFIG, ocr, page

    try:
        CONFIG = load_config()
        import ddddocr

        print("东南大学讲座预约｜维护者：MuZiJin701")
        print("项目主页：https://github.com/MuZiJin701/SEU_Lecture_Reserve")
        ocr = ddddocr.DdddOcr(show_ad=False)
        with sync_playwright() as playwright:
            with logged_in_page(playwright, CONFIG) as page:
                if page is not None:
                    print("🚀 启动讲座扫描流程...")
                    main_process()
                else:
                    print("❌ 登录失败，程序退出")
                    return 1
            print("🚗 浏览器已关闭")
    except KeyboardInterrupt:
        print("\n👋 用户中断程序")
    except ValueError as exc:
        print(f"\n❌ 配置错误: {exc}")
        return 1
    except Exception as exc:
        print(f"\n❌ 程序异常: {type(exc).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
