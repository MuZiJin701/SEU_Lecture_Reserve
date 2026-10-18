"""School interaction through page navigation, rendered Vue data and button clicks."""

import base64
import math
import re
import time
from contextlib import ExitStack
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

from playwright.sync_api import Error, TimeoutError

from browser import logged_in_page, login, timeout_ms


class RemoteError(Exception):
    def __init__(self, reason, retry_after=0):
        super().__init__(reason if re.fullmatch(r"[a-z_]{1,80}", reason) else "browser_failure")
        self.retry_after = retry_after


class AuthenticationExpired(RemoteError):
    pass


class AuthenticationRequired(Exception):
    pass


def has_code(payload, expected):
    return type(payload.get("code")) is int and payload["code"] == expected


# Read only data already bound to the visible page; never invoke Vue methods or HTTP APIs.
VIEW = """field => {
    let v = document.querySelector('.hdyy')?.__vue__;
    while (v && !Object.hasOwn(v.$data || {}, 'activityList')) v = v.$parent;
    if (!v) return null;
    const d = v.$data;
    const keys = ['WID', 'HD_WID', 'JZMC', 'JZXL_DISPLAY', 'JZDD', 'JZSJ',
                  'HDJSSJ', 'FBZT', 'SFDK', 'SFWY', 'YY_WID', 'btn_yy'];
    return {tab: String(d.tplId), loading: d.isLoading, error: d.ifError,
        ready: d.xtdqsj instanceof Date && !Number.isNaN(+d.xtdqsj),
        all: (d.buttonList || []).filter(b => b.checked).map(b => b.id),
        rows: Array.isArray(d[field]) ? d[field].map(r => Object.fromEntries(
            keys.filter(k => Object.hasOwn(r, k)).map(k => [k, r[k]]))) : null,
        cards: [...document.querySelectorAll('.activity-container')]
            .filter(e => e.getClientRects().length).length};
}"""

CARD_ID = """e => {
    let v = e.__vue__;
    while (v && !v.$props?.item) v = v.$parent;
    return v?.$props?.item?.HD_WID || v?.$props?.item?.WID || null;
}"""

OUTCOME = """wid => {
    const messages = [...document.querySelectorAll('.mint-msgbox-message, .mint-toast-text')]
        .filter(e => e.getClientRects().length).map(e => e.textContent.trim());
    for (const msg of messages) {
        if (msg.includes('验证码') && ['错误', '不正确', '失效', '过期'].some(w => msg.includes(w)))
            return {code: 1, msg: '验证码错误'};
        if (['已满', '名额已满', '不可预约', '预约已结束', '预约未开始'].includes(msg))
            return {code: 1, msg};
    }
    let v = document.querySelector('.hdyy')?.__vue__;
    while (v && !Object.hasOwn(v.$data || {}, 'activityList')) v = v.$parent;
    if (v?.$data.activityList.some(r => r.WID === wid && r.YY_WID)) return {code: 0};
    return false;
}"""


class BrowserClient:
    def __init__(self, playwright, config):
        self.playwright = playwright
        self.config = config
        self.page = None
        self.stack = ExitStack()
        self.limit_until = 0.0
        self.expired = False
        self.prepared = None
        self.image_ready = False

    def _observe(self, response):
        target = urlsplit(response.url)
        if (target.hostname != "ehall.seu.edu.cn" or '/modules/hdyy/' not in target.path
                or not target.path.endswith('.do')):
            return
        if response.status == 429:
            delay = 60.0
            value = response.headers.get('retry-after', '')
            try:
                delay = float(value)
            except ValueError:
                try:
                    delay = parsedate_to_datetime(value).timestamp() - time.time()
                except (ValueError, TypeError, OverflowError):
                    pass
            if not math.isfinite(delay):
                delay = 60
            self.limit_until = max(self.limit_until, time.time() + max(1, delay))
        elif response.status in (401, 403):
            self.expired = True

    def _check(self):
        if self.limit_until > time.time():
            raise RemoteError('rate_limited', self.limit_until - time.time())
        if self.expired or (self.page is not None and (
                urlsplit(self.page.url).scheme != 'https'
                or urlsplit(self.page.url).hostname != 'ehall.seu.edu.cn')):
            raise AuthenticationExpired('authentication_expired')

    def authenticate(self):
        if self.page is None:
            self.page = self.stack.enter_context(logged_in_page(self.playwright, self.config))
            if self.page is not None:
                self.page.on('response', self._observe)
        elif not login(self.page, self.config):
            raise AuthenticationRequired
        if self.page is None:
            raise AuthenticationRequired
        self.expired = False
        self._view('activityList')

    def _view(self, field):
        self._check()
        if self.page is None:
            raise RemoteError('page_not_ready')
        tab = '2' if field == 'myActivityList' else '1'
        try:
            handle = self.page.wait_for_function(
                "field => { const s = (" + VIEW + ")(field); return s && "
                "s.ready && s.loading === false && s.tab === (field === 'myActivityList' ? '2' : '1') ? s : false; }",
                arg=field, timeout=timeout_ms(self.config['timeout_settings']['element_wait']),
            )
            snapshot = handle.json_value()
            handle.dispose()
        except Error:
            self._check()
            raise RemoteError('page_not_ready') from None
        self._check()
        if (snapshot['error'] is not False or snapshot['tab'] != tab
                or not isinstance(snapshot['rows'], list)
                or len(snapshot['rows']) != snapshot['cards']):
            raise RemoteError('page_data_incomplete')
        if field == 'myActivityList' and snapshot['all'] != ['']:
            raise RemoteError('history_filter_incomplete')
        return snapshot['rows']

    def _reload(self):
        self._check()
        if self.page is None:
            raise RemoteError('page_not_ready')
        self.prepared = None
        self.image_ready = False
        try:
            self.page.reload(wait_until='domcontentloaded')
        except Error:
            self._check()
            raise RemoteError('navigation_failed') from None
        return self._view('activityList')

    def mine(self):
        self._reload()
        assert self.page is not None
        try:
            self.page.get_by_text('我的活动', exact=True).click()
            # The school's default is All; never use its SFYY filter, which removes attended rows.
            self.page.locator('.button-check:visible').filter(has_text=re.compile(r'^全部$')).click()
        except Error:
            self._check()
            raise RemoteError('history_navigation_failed') from None
        rows = self._view('myActivityList')
        if any(not isinstance(r.get('HD_WID'), str) or not r['HD_WID'] for r in rows):
            raise RemoteError('history_schema_unknown')
        return rows

    def activities(self):
        rows = self._reload()
        return [{**row, 'HDMC': row.get('JZMC'), 'HDLX_DISPLAY': row.get('JZXL_DISPLAY'),
                 'IS_ONLINE': '线上' in row['JZMC'] if isinstance(row.get('JZMC'), str) else None,
                 'YYZT': '预约' if row.get('btn_yy') is True else '不可预约'} for row in rows]

    def _target(self, wid):
        if self.page is None:
            raise RemoteError('page_not_ready')
        matches = [card for card in self.page.locator('.activity-container:visible').all()
                   if card.evaluate(CARD_ID) == wid]
        if len(matches) != 1:
            raise RemoteError('activity_identity_ambiguous')
        return matches[0]

    def preflight(self, wid):
        rows = self.activities()
        assert self.page is not None
        if not any(r.get('WID') == wid and r['YYZT'] == '预约' for r in rows):
            return False
        try:
            self._target(wid).get_by_role('button', name='预约', exact=True).click()
            self.page.locator('#vcodeImg').wait_for(state='visible')
        except Error:
            self._check()
            outcome = self.page.evaluate(OUTCOME, wid)
            if outcome and outcome.get('msg') in ('已满', '名额已满', '不可预约', '预约已结束', '预约未开始'):
                return False
            raise RemoteError('preflight_failed') from None
        self._check()
        self.prepared = wid
        self.image_ready = True
        return True

    def captcha(self):
        if not self.image_ready and (not self.prepared or not self.preflight(self.prepared)):
            raise RemoteError('captcha_unavailable')
        if self.page is None:
            raise RemoteError('page_not_ready')
        try:
            source = self.page.locator('#vcodeImg').get_attribute('src') or ''
            if not source.startswith('data:image/') or ';base64,' not in source or len(source) > 1500000:
                raise ValueError
            binary = base64.b64decode(source.split(';base64,', 1)[1], validate=True)
            if not binary:
                raise ValueError
            self.image_ready = False
            return binary
        except (Error, ValueError):
            self._check()
            raise RemoteError('captcha_invalid') from None

    def submit(self, wid, code):
        self._check()
        if self.page is None:
            raise RemoteError('page_not_ready')
        if self.prepared != wid or not re.fullmatch(r'[A-Za-z0-9]{1,16}', code):
            raise RemoteError('submission_invalid')
        try:
            self._target(wid).get_by_role('button', name='预约', exact=True).wait_for(state='visible')
            self.page.locator('#vcodeInput').fill(code)
            self.page.locator('#jqalert_yes_btn').click()
            time.sleep(self.config['timeout_settings'].get('action_confirm', 0.2))
            handle = self.page.wait_for_function(OUTCOME, arg=wid,
                timeout=timeout_ms(self.config['timeout_settings']['element_wait']))
            result = handle.json_value()
            handle.dispose()
        except TimeoutError:
            result = {}
        except Error:
            self._check()
            raise RemoteError('submission_unconfirmed') from None
        self._check()
        return result

    def close(self):
        self.stack.close()
