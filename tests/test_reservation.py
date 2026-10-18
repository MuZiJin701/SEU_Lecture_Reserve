"""Managed Chromium, synthetic Vue pages and intercepted navigation: no school traffic."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from playwright.sync_api import sync_playwright

from browser import LECTURE_URL, _login_control, setup_browser
from browser_client import BrowserClient, RemoteError, AuthenticationExpired
from model import SERIES_CATEGORIES


HTML = """<!doctype html><meta charset="utf-8">
<div class="hdyy"><nav><a id="mine">我的活动</a></nav>
<button class="button-check" id="all">全部</button><div id="cards"></div></div>
<div id="dialog" hidden><img id="vcodeImg"
src="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMCIgaGVpZ2h0PSIxMCIvPg==">
<input id="vcodeInput"><button id="jqalert_yes_btn">确定</button></div>
<div class="mint-toast-text"></div>
<script>
const fixture = FIXTURE;
const booked = JSON.parse(localStorage.getItem('booked') || '[]');
const state = {tplId:'1', isLoading:false, ifError:false,xtdqsj:new Date(),
  activityList: fixture.rows.map(r=>({...r,btn_yy:!booked.includes(r.WID),YY_WID:booked.includes(r.WID)?'booking':''})),
  myActivityList:[...fixture.history, ...fixture.rows.filter(r=>booked.includes(r.WID)).map(r=>({...r,HD_WID:r.WID,FBZT:'1',SFDK:'0',SFWY:'0'}))],
  buttonList:[{id:'',checked:true}]};
const root = {$data:state};
document.querySelector('.hdyy').__vue__ = {$data:{},$parent:root};
let selected = null;
function render() {
  const cards=document.querySelector('#cards');cards.replaceChildren();
  for(const r of state.tplId==='1'?state.activityList:state.myActivityList) {
    const e=document.createElement('div');e.className='activity-container';
    e.__vue__={$props:{},$parent:{$props:{item:r},$parent:root}};
    const label=document.createElement('span');label.textContent=r.JZMC;e.append(label);
    const b=document.createElement('button');b.textContent=r.btn_yy?'预约':'取消预约';
    b.onclick=()=>{if(!r.btn_yy){localStorage.setItem('cancelled','yes');return;}
      selected=r.WID;document.querySelector('#dialog').hidden=false;};
    e.append(b);cards.append(e);
  }
}
document.querySelector('#mine').onclick=()=>{state.tplId='2';render();};
document.querySelector('#all').onclick=()=>{state.buttonList=[{id:'',checked:true}];render();};
document.querySelector('#jqalert_yes_btn').onclick=()=>{
  localStorage.setItem('submissions',String(Number(localStorage.getItem('submissions')||'0')+1));
  document.querySelector('#dialog').hidden=true;
  if(fixture.outcome==='captcha')document.querySelector('.mint-toast-text').textContent='验证码错误';
  if(fixture.outcome==='success') {
    booked.push(selected);localStorage.setItem('booked',JSON.stringify(booked));
    const r=state.activityList.find(r=>r.WID===selected);r.YY_WID='booking';r.btn_yy=false;render();
  }
};
render();
</script>"""


def row(wid='one', **changes):
    return {'WID':wid,'JZMC':'【线上】相同标题讲座','JZXL_DISPLAY':SERIES_CATEGORIES[0],
            'JZDD':'线上会议','JZSJ':'2030-01-01 10:00:00','HDJSSJ':'2030-01-01 11:00:00',
            'btn_yy':True,**changes}


class ReservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright=sync_playwright().start()
        try:
            cls.browser=setup_browser(cls.playwright,headless=True)
        except BaseException:
            cls.playwright.stop()
            raise

    @classmethod
    def tearDownClass(cls):
        try:
            cls.browser.close()
        finally:
            cls.playwright.stop()

    def setUp(self):
        self.context=self.browser.new_context()
        self.addCleanup(self.context.close)
        self.page=self.context.new_page()
        self.page.set_default_timeout(300)
        self.fixture={'rows':[row()], 'history':[], 'outcome':'success'}
        self.requests=[]
        def intercept(route):
            self.requests.append(route.request.method)
            if route.request.resource_type=='document':
                route.fulfill(content_type='text/html',body=HTML.replace('FIXTURE',json.dumps(self.fixture)))
            else:
                route.abort()
        self.context.route('**/*',intercept)
        self.page.goto(LECTURE_URL)
        self.config={'timeout_settings':{'element_wait':0.3,'action_confirm':0}}
        self.client=BrowserClient(self.playwright,self.config)
        self.client.page=self.page

    def test_reads_all_history_and_bound_stable_ids_without_http_client(self):
        self.fixture['history']=[row('booking',HD_WID='activity',SFDK='1',SFWY='0',FBZT='1')]
        history=self.client.mine()
        self.assertEqual(history[0]['HD_WID'],'activity')
        self.assertEqual(history[0]['SFDK'],'1')
        activities=self.client.activities()
        self.assertEqual(activities[0]['WID'],'one')
        self.assertTrue(activities[0]['IS_ONLINE'])
        self.assertEqual(set(self.requests),{'GET'})

    def test_explicit_mode_markers_and_availability_are_preserved(self):
        self.fixture['rows'] = [row('offline', JZMC='【线下】线上教育的法律问题', JZDD='九龙湖校区教室'),
            row('unknown', JZMC='线上教育讲座'),
            row('closed', btn_wkf=True, YYKSSJ='2030-01-01 19:00:00', YYJSSJ='2030-01-02 12:00:00'),
            row('full', btn_rsym=True)]
        self.client._reload()
        self.page.evaluate("""() => {
            const rows=document.querySelector('.hdyy').__vue__.$parent.$data.activityList;
            delete rows[2].btn_yy;
            delete rows[3].btn_yy;
        }""")
        activities = self.client._view('activityList')
        with patch.object(self.client, '_reload', return_value=activities):
            normalized = self.client.activities()
        self.assertIs(normalized[0]['IS_ONLINE'], False)
        self.assertIsNone(normalized[1]['IS_ONLINE'])
        self.assertEqual(normalized[2]['availability_reason'], 'reservation_not_started')
        self.assertEqual(normalized[2]['YYKSSJ'], '2030-01-01 19:00:00')
        self.assertEqual(normalized[2]['YYJSSJ'], '2030-01-02 12:00:00')
        self.assertEqual(normalized[3]['availability_reason'], 'capacity_full')

    def test_duplicate_titles_and_reordered_cards_use_id_and_never_cancel(self):
        self.fixture['rows']=[row('one'),row('two')]
        self.assertTrue(self.client.preflight('two'))
        self.page.evaluate("document.querySelector('#cards').append(document.querySelector('.activity-container'))")
        self.assertTrue(self.client.captcha())
        self.assertEqual(self.client.submit('two','1234'),{'code':0})
        history=self.client.mine()
        self.assertEqual([r['HD_WID'] for r in history],['two'])
        self.assertIsNone(self.page.evaluate("localStorage.getItem('cancelled')"))

    def test_unknown_submission_is_not_retried_by_browser(self):
        self.fixture['outcome']='unknown'
        self.client.preflight('one')
        self.client.captcha()
        self.assertEqual(self.client.submit('one','1234'),{})
        self.assertEqual(self.client.mine(),[])
        self.assertEqual(self.page.evaluate("localStorage.getItem('submissions')"),'1')

    def test_only_explicit_captcha_error_allows_a_fresh_image(self):
        self.fixture['outcome']='captcha'
        self.client.preflight('one')
        self.client.captcha()
        self.assertEqual(self.client.submit('one','1234'),{'code':1,'msg':'验证码错误'})
        self.assertTrue(self.client.captcha())
        self.assertTrue(self.page.locator('#vcodeInput').is_visible())

    def test_invalid_captcha_never_clicks_submit(self):
        self.client.preflight('one')
        self.page.locator('#vcodeImg').evaluate("e=>e.src='data:image/svg+xml,not-base64'")
        with self.assertRaisesRegex(RemoteError,'captcha_invalid'):
            self.client.captcha()
        self.assertIsNone(self.page.evaluate("localStorage.getItem('submissions')"))

    def test_missing_duplicate_and_changed_ids_cannot_target_by_title(self):
        self.fixture['rows']=[row('one'),row('one')]
        with self.assertRaisesRegex(RemoteError,'activity_identity_ambiguous'):
            self.client.preflight('one')
        self.fixture['rows']=[row('other')]
        self.assertFalse(self.client.preflight('one'))

    def test_partial_render_and_unknown_page_are_not_an_empty_schedule(self):
        self.page.evaluate("document.querySelector('#cards').replaceChildren()")
        with self.assertRaisesRegex(RemoteError,'page_data_incomplete'):
            self.client._view('activityList')
        self.page.set_content('<p>登录页面</p>')
        with self.assertRaisesRegex(RemoteError,'page_not_ready'):
            self.client._view('activityList')

    def test_non_all_filter_blocks_history(self):
        self.client.mine()
        self.page.evaluate("document.querySelector('.hdyy').__vue__.$parent.$data.buttonList=[{id:'SFYY',checked:true}]")
        with self.assertRaisesRegex(RemoteError,'history_filter_incomplete'):
            self.client._view('myActivityList')

    def test_session_expiry_is_not_empty_data(self):
        self.client.expired=True
        with self.assertRaises(AuthenticationExpired):
            self.client.mine()

    def test_rate_limit_blocks_navigation_and_respects_retry_after(self):
        self.client._observe(SimpleNamespace(url='https://ehall.seu.edu.cn/gsapp/sys/yddjzxxtjappseu/modules/hdyy/queryActivityList.do',
            status=429,headers={'retry-after':'600'}))
        with patch.object(self.page,'reload') as reload:
            with self.assertRaises(RemoteError) as error:
                self.client.mine()
            self.assertGreater(error.exception.retry_after,590)
            reload.assert_not_called()

    def test_initial_empty_model_waits_for_server_time_before_trusting_records(self):
        self.page.evaluate("document.querySelector('.hdyy').__vue__.$parent.$data.xtdqsj='' ")
        with self.assertRaisesRegex(RemoteError, 'page_not_ready'):
            self.client._view('activityList')

    def test_login_selector_prefers_username_to_unrelated_text(self):
        self.page.set_content('<input type="text" id="search"><input type="text" id="username">')
        _login_control(self.page,['#username',"input[type='text']"]).fill('test-card')
        self.assertEqual(self.page.locator('#username').input_value(),'test-card')
        self.assertEqual(self.page.locator('#search').input_value(),'')

    def test_local_pages_work_in_headed_mode_with_ipv6_backup(self):
        browser=setup_browser(self.playwright,'2001:db8::10',headless=False)
        try:
            context=browser.new_context()
            context.route('**/*',lambda route:route.abort())
            page=context.new_page()
            page.goto('about:blank')
            page.set_content('<p role="status">offline page ready</p>')
            self.assertEqual(page.get_by_role('status').inner_text(),'offline page ready')
        finally:
            browser.close()


if __name__=='__main__':
    unittest.main()
