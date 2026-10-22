"""Offline regression checks for the rules ported from the HTTPS project."""

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from app import Settings, run
from browser_client import AuthenticationExpired, AuthenticationRequired, BrowserClient, BrowserClosed, RemoteError
from main import show_status
from model import COFFEE_CATEGORY, SERIES_CATEGORIES, SHANGHAI, progress
from state import Task, task_running


def lecture(wid='one', **changes):
    return {'WID': wid, 'HDMC': '测试讲座', 'HDLX_DISPLAY': SERIES_CATEGORIES[0],
            'IS_ONLINE': True, 'JZDD': '线上会议', 'YYZT': '预约', 'SFDK': '0', 'SFWY': '0',
            'KSSJ': '2030-01-01 10:00:00', 'JSSJ': '2030-01-01 11:00:00', **changes}


def attended(count=8):
    return [lecture(f'history-{i}', YYZT='已预约', SFDK='1',
            HDLX_DISPLAY=SERIES_CATEGORIES[i % 4], KSSJ=f'2020-01-{i+1:02} 10:00:00',
            JSSJ=f'2020-01-{i+1:02} 11:00:00') for i in range(count)]


def stop(_):
    raise KeyboardInterrupt


class School:
    def __init__(self):
        self.rows = []
        self.history = []
        self.submitted = []
        self.closed = False
        self.authentications = 0
        self.error = None
        self.unknown = False
        self.rejected = set()

    def authenticate(self):
        self.authentications += 1
        if self.error:
            raise self.error

    def mine(self):
        return self.history

    def activities(self):
        return self.rows

    def preflight(self, wid):
        return wid not in self.rejected

    def captcha(self):
        return b'offline captcha'

    def submit(self, wid, code):
        self.submitted.append(wid)
        if self.unknown:
            raise RemoteError('submission_unconfirmed')
        row = next(row for row in self.rows if row.get('WID') == wid)
        self.history.append({**row, 'YYZT': '已预约'})
        return {'code': 0}

    def close(self):
        self.closed = True


class AppTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)
        self.school = School()
        self.events = []
        self.output = io.StringIO()

    def execute(self, **options):
        settings = options.pop('settings', Settings(state_dir=self.path))
        with redirect_stdout(self.output):
            return run(settings, client=self.school, environ={'SEU_CARD_NUMBER': 'test-card'},
                sleep=options.pop('sleep', stop), recognize=options.pop('recognize', lambda _: '1234'),
                clock=options.pop('clock', lambda: 100),
                notify=options.pop('notify', lambda event, details='': self.events.append(event)), **options)

    def saved(self):
        return json.loads((self.path / 'task.json').read_text())

    def test_ocr_initializes_once_before_login_and_reservation(self):
        calls=[]
        model=Mock()
        model.classification.return_value='1234'
        module=Mock()
        module.DdddOcr.side_effect=lambda **options: calls.append('ocr') or model
        self.school.rows=[lecture()]
        self.school.authenticate=lambda: calls.append('login')
        with patch.dict(sys.modules,{'ddddocr':module}):
            self.assertEqual(self.execute(recognize=None),130)
        self.assertEqual(calls,['ocr','login'])
        module.DdddOcr.assert_called_once_with(show_ad=False)
        model.classification.assert_called_once()
        self.assertEqual(self.school.submitted,['one'])

    def test_read_only_does_not_initialize_ocr(self):
        module=Mock()
        with patch.dict(sys.modules,{'ddddocr':module}):
            self.assertEqual(self.execute(check_only=True,recognize=None),0)
        module.DdddOcr.assert_not_called()
        self.assertFalse((self.path/'task.json').exists())

    def test_opening_empty_scans_reuse_history_for_at_most_ten_seconds(self):
        opening=datetime(2030,1,1,9,tzinfo=SHANGHAI)
        now=[opening.timestamp()]
        self.school.rows=[lecture(YYZT='不可预约',availability_reason='capacity_full',
                                  YYKSSJ=opening.strftime('%Y-%m-%d %H:%M:%S'))]
        self.school.mine=Mock(wraps=self.school.mine)
        self.school.activities=Mock(wraps=self.school.activities)
        waits=[]
        def wait(seconds):
            waits.append(seconds)
            now[0]+=seconds
            if len(waits)==12: raise KeyboardInterrupt
        self.execute(clock=lambda:now[0],sleep=wait)
        self.assertEqual(waits,[1]*12)
        self.assertEqual(self.school.activities.call_count,12)
        self.assertEqual(self.school.mine.call_count,2)
        self.assertEqual(self.school.submitted,[])

    def test_opening_candidate_rechecks_history_before_preflight(self):
        opening=datetime(2030,1,1,9,tzinfo=SHANGHAI)
        for history, expected in (([lecture('other',YYZT='已预约')],'time_conflict'),
                                  ([lecture(YYZT='已预约')],'already_reserved'),
                                  ([lecture('other',YYZT='已预约',SFDK=None)],None)):
            with self.subTest(expected=expected), TemporaryDirectory() as directory:
                self.school=School()
                candidate=lecture(YYKSSJ=opening.strftime('%Y-%m-%d %H:%M:%S'))
                self.school.activities=Mock(side_effect=[
                    [{**candidate,'YYZT':'不可预约','availability_reason':'capacity_full'}],
                    [candidate],[candidate]])
                self.school.mine=Mock(side_effect=[[],history])
                self.school.preflight=Mock()
                now=[opening.timestamp()]
                waits=[]
                def wait(seconds):
                    waits.append(seconds)
                    now[0]+=seconds
                    if len(waits)==2: raise KeyboardInterrupt
                path=Path(directory)
                self.execute(settings=Settings(state_dir=path),clock=lambda:now[0],sleep=wait)
                self.school.preflight.assert_not_called()
                self.assertEqual(self.school.submitted,[])
                self.assertEqual(self.school.mine.call_count,2)
                saved=json.loads((path/'task.json').read_text())
                if expected is None:
                    self.assertEqual(saved['health']['last_error'],'attendance_status_unknown')
                else:
                    self.assertEqual(saved['selection']['activities'][0]['reason'],expected)

    def test_opening_query_error_discards_cached_history(self):
        opening=datetime(2030,1,1,9,tzinfo=SHANGHAI)
        rows=[lecture(YYZT='不可预约',availability_reason='capacity_full',
                      YYKSSJ=opening.strftime('%Y-%m-%d %H:%M:%S'))]
        self.school.activities=Mock(side_effect=[rows,RemoteError('page_not_ready'),rows])
        self.school.mine=Mock(wraps=self.school.mine)
        now=[opening.timestamp()]
        waits=[]
        def wait(seconds):
            waits.append(seconds)
            now[0]+=seconds
            if len(waits)==3: raise KeyboardInterrupt
        self.execute(clock=lambda:now[0],sleep=wait)
        self.assertEqual(waits,[1,1,1])
        self.assertEqual(self.school.mine.call_count,2)

    def test_opening_pending_checks_never_reuse_history_or_scan_candidates(self):
        opening=datetime(2030,1,1,9,tzinfo=SHANGHAI)
        task=Task(self.path,'test-card')
        task.data.update(status='pending',activity='one',selection={'activities':[
            dict(reason='candidate',reservation_start=opening.isoformat())]})
        task.save(); task.close()
        self.school.mine=Mock(wraps=self.school.mine)
        self.school.activities=Mock()
        waits=[]
        def wait(seconds):
            waits.append(seconds)
            if len(waits)==3: raise KeyboardInterrupt
        self.execute(clock=lambda:opening.timestamp(),sleep=wait)
        self.assertEqual(waits,[10,10,10])
        self.assertEqual(self.school.mine.call_count,3)
        self.school.activities.assert_not_called()
        self.assertEqual(self.saved()['status'],'pending')

    def test_browser_closed_stops_without_retry_and_preserves_pending_submission(self):
        for stage in ('mine', 'submit'):
            with self.subTest(stage=stage), TemporaryDirectory() as directory:
                self.school = School()
                self.school.rows = [lecture()]
                self.events.clear()
                settings = Settings(state_dir=Path(directory))
                sleep = Mock()
                with patch.object(self.school, stage, side_effect=BrowserClosed('browser_closed')):
                    self.assertEqual(self.execute(settings=settings, sleep=sleep), 1)
                sleep.assert_not_called()
                self.assertTrue(self.school.closed)
                self.assertFalse(task_running(settings.state_dir))
                saved = json.loads((settings.state_dir / 'task.json').read_text())
                self.assertEqual(saved['health']['phase'], 'failed')
                self.assertEqual(saved['health']['last_error'], 'browser_closed')
                self.assertEqual(self.events, ['task_failed'])
                self.assertIn('event=browser_closed', (settings.state_dir / 'events.log').read_text())
                self.assertEqual(saved['status'], 'pending' if stage == 'submit' else 'scanning')
                if stage == 'submit':
                    self.assertEqual(saved['activity'], 'one')
                    self.assertEqual(self.execute(settings=settings), 130)
                    self.assertEqual(self.school.submitted, [])
                    self.assertEqual(self.events, ['task_failed', 'reservation_unconfirmed'])

    def test_read_only_browser_closed_reports_reason_without_creating_state(self):
        with patch.object(self.school, 'mine', side_effect=BrowserClosed('browser_closed')):
            self.assertEqual(self.execute(check_only=True), 1)
        self.assertIn('event=task_failed stage=my_activities reason=browser_closed', self.output.getvalue())
        self.assertFalse((self.path / 'task.json').exists())
        self.assertEqual(self.events, [])
        self.assertTrue(self.school.closed)

    def test_goal_completes_only_with_eight_attendances_and_three_categories(self):
        self.school.history = attended()
        self.assertEqual(self.execute(), 0)
        self.assertEqual(self.events, ['goal_completed'])
        self.assertEqual(self.saved()['status'], 'done')
        self.school = School()
        self.school.history = attended()
        self.assertEqual(self.execute(), 0)
        self.assertEqual(self.school.authentications, 1)
        self.assertEqual(self.events, ['goal_completed'])
        self.school.history = []
        self.school.rows = [lecture()]
        self.assertEqual(self.execute(), 130)
        self.assertEqual(self.school.submitted, ['one'])
        self.assertEqual(self.saved()['status'], 'scanning')
        self.school.history = attended()
        self.assertEqual(self.execute(), 0)
        self.assertEqual(self.execute(new_task=True), 0)

    def test_one_success_continues_and_restart_does_not_repeat(self):
        self.school.rows = [lecture()]
        self.assertEqual(self.execute(), 130)
        self.assertEqual(self.events, ['reservation_succeeded'])
        self.assertEqual(self.saved()['status'], 'scanning')
        self.execute()
        self.assertEqual(self.school.submitted, ['one'])
        self.assertTrue(self.school.closed)

    def test_pending_is_saved_before_click_and_restart_never_retries(self):
        self.school.rows = [lecture()]
        self.school.unknown = True
        original = self.school.submit
        def submit(wid, code):
            self.assertEqual(self.saved()['status'], 'pending')
            self.assertEqual(self.saved()['activity'], wid)
            return original(wid, code)
        self.school.submit = submit
        self.execute()
        self.assertEqual(self.saved()['status'], 'pending')
        self.execute(clock=lambda: 121)
        self.assertEqual(self.school.submitted, ['one'])
        self.assertIn('reservation_unconfirmed', self.events)
        self.school.history = [{**lecture(), 'YYZT': '已预约'}]
        self.execute(clock=lambda: 121)
        self.assertEqual(self.saved()['status'], 'scanning')
        self.assertEqual(self.school.submitted, ['one'])

    def test_unverified_success_or_authentication_expiry_never_retries_or_books_next(self):
        for reply in ({'code':0}, {'code':1,'msg':'预约成功'},
                      AuthenticationExpired('authentication_expired')):
            with self.subTest(reply=reply), TemporaryDirectory() as directory:
                self.school=School()
                self.school.rows=[lecture('one'),lecture('two')]
                self.school.preflight=Mock(return_value=True)
                self.school.submit=Mock(side_effect=reply) if isinstance(reply,Exception) else Mock(return_value=reply)
                path=Path(directory)
                settings=Settings(state_dir=path)
                self.execute(settings=settings)
                saved=json.loads((path/'task.json').read_text())
                self.assertEqual((saved['status'],saved['activity']),('pending','one'))
                self.execute(settings=settings)
                self.school.submit.assert_called_once_with('one','1234')
                self.school.preflight.assert_called_once_with('one')
                self.assertNotIn('reservation_succeeded',self.events)

    def test_planned_coverage_waits_and_cancellation_is_replaced(self):
        self.school.history = attended(7) + [lecture('planned', YYZT='已预约')]
        self.school.rows = [lecture('replacement', KSSJ='2030-01-02 10:00:00', JSSJ='2030-01-02 11:00:00')]
        self.execute()
        self.assertFalse(self.school.submitted)
        self.assertNotEqual(self.saved()['status'], 'done')
        self.school.history[-1]['YYZT'] = '已取消'
        self.execute()
        self.assertEqual(self.school.submitted, ['replacement'])

    def test_missing_category_precedes_filler_and_keeps_its_place(self):
        self.school.history = attended(6)
        for row in self.school.history:
            row['HDLX_DISPLAY'] = SERIES_CATEGORIES[0]
        self.school.rows = [lecture('filler', HDLX_DISPLAY=SERIES_CATEGORIES[3]),
            lecture('law', HDLX_DISPLAY=SERIES_CATEGORIES[1]),
            lecture('art', HDLX_DISPLAY=SERIES_CATEGORIES[2], KSSJ='2030-01-02 10:00:00', JSSJ='2030-01-02 11:00:00')]
        self.execute()
        self.assertEqual(self.school.submitted, ['law', 'art'])

    def test_title_selection_keeps_all_other_filters(self):
        for changes, settings in (
            ({'HDLX_DISPLAY': '未允许类别'}, {}),
            ({'IS_ONLINE': False, 'JZDD': '无锡校区教室'}, {}),
            ({}, {'online': False}),
            ({'IS_ONLINE': False, 'JZDD': '无锡校区'}, {'offline': False, 'campuses': ('无锡校区',)}),
            ({'KSSJ': 'unknown'}, {}),
        ):
            with self.subTest(changes=changes, settings=settings):
                self.school.rows = [lecture(**changes)]
                self.execute(settings=Settings(state_dir=self.path, titles=('测试讲座',), **settings))
                self.assertFalse(self.school.submitted)

    def test_touching_and_unselected_reservations_still_block_conflicts(self):
        self.school.history = [lecture('old', YYZT='已预约'), lecture('overlap', YYZT='已预约',
            KSSJ='2030-01-01 10:30:00', JSSJ='2030-01-01 11:30:00')]
        self.school.rows = [lecture('touching', KSSJ='2030-01-01 11:30:00', JSSJ='2030-01-01 12:30:00')]
        self.execute()
        self.assertFalse(self.school.submitted)

    def test_equal_activity_times_can_be_reserved(self):
        client = BrowserClient(None, {})
        raw = {'WID': 'equal', 'JZMC': '【线上】测试讲座', 'JZXL_DISPLAY': SERIES_CATEGORIES[2],
               'JZDD': '线上会议', 'JZSJ': '2030-01-01 21:00:00',
               'HDJSSJ': '2030-01-01 21:00:00', 'btn_yy': True, 'SFDK': '0', 'SFWY': '0'}
        with patch.object(client, '_reload', return_value=[raw]):
            self.school.rows = client.activities()
        self.assertEqual(self.execute(), 130)
        self.assertEqual(self.school.submitted, ['equal'])
        self.assertEqual(sum(progress(self.school.history, 100).planned.values()), 1)
        self.assertNotIn('activity_schema_unknown', self.output.getvalue())

    def test_equal_activity_times_still_block_conflicts(self):
        for history_start, history_end, start, end in (
            ('10:30:00', '10:30:00', '10:00:00', '11:00:00'),
            ('10:00:00', '11:00:00', '10:30:00', '10:30:00'),
            ('10:00:00', '11:00:00', '11:00:00', '11:00:00'),
        ):
            with self.subTest(history_start=history_start, start=start):
                self.school.history = [lecture('old', YYZT='已预约',
                    KSSJ='2030-01-01 ' + history_start, JSSJ='2030-01-01 ' + history_end)]
                self.school.rows = [lecture(KSSJ='2030-01-01 ' + start, JSSJ='2030-01-01 ' + end)]
                self.execute()
                self.assertFalse(self.school.submitted)
                self.assertEqual(self.saved()['selection']['activities'][0]['reason'], 'time_conflict')

    def test_invalid_activity_is_skipped_and_alerted_without_blocking_valid_activity(self):
        self.school.rows = [lecture('invalid', JSSJ='2030-01-01 09:00:00'), lecture('valid')]
        self.execute()
        self.assertEqual(self.school.submitted, ['valid'])
        details = self.saved()['selection']['activities']
        self.assertEqual(details[0]['reason'], 'invalid_activity_data')
        self.assertEqual(details[0]['validation_error'], 'interval_invalid')
        self.assertEqual(self.saved()['health']['failure_count'], 0)
        self.assertEqual(self.saved()['health']['last_error'], 'invalid_activity_data')
        self.assertIn('runtime_problem', self.events)
        diagnostics = [json.loads(line) for line in (self.path / 'diagnostics.jsonl').read_text().splitlines()]
        selection = next(item for item in diagnostics if item['event'] == 'selection_changed')
        self.assertEqual(selection['activities'][0]['validation_error'], 'interval_invalid')
        self.assertIn('event=invalid_activity_data', self.output.getvalue())
        self.assertNotIn('测试讲座', self.output.getvalue())
        self.assertNotIn('测试讲座', (self.path / 'events.log').read_text())
        status = io.StringIO()
        with redirect_stdout(status):
            show_status(self.path)
        self.assertIn('"reason": "invalid_activity_data"', status.getvalue())
        self.assertNotIn('activity_details=unknown', status.getvalue())
        self.execute()
        self.assertEqual(self.events.count('runtime_problem'), 1)
        self.assertEqual(self.school.submitted, ['valid'])

    def test_unknown_history_and_conflicting_duplicates_block_submission(self):
        for history in ([lecture('old', YYZT='已预约', SFDK=None)],
                        [lecture('old', YYZT='已预约', HDLX_DISPLAY='非目标公告')],
                        [lecture('old', YYZT='已预约', KSSJ='unknown')],
                        [lecture('old', YYZT='已预约', JSSJ='2030-01-01 09:00:00')],
                        [lecture('old', YYZT='已预约', JSSJ=None)],
                        [lecture('old', YYZT='已预约'), lecture('old', YYZT='已预约', SFDK='1')]):
            with self.subTest(history=history):
                self.school.history = history
                self.school.rows = [lecture()]
                self.execute()
                self.assertFalse(self.school.submitted)

    def test_expired_unconfirmed_attendance_blocks_coffee(self):
        self.school.history = [lecture('old', YYZT='已预约')]
        self.school.rows = [lecture('coffee', HDLX_DISPLAY='“SEU咖啡间"系列沙龙活动')]
        self.execute(clock=lambda: 253000000000)
        self.assertFalse(self.school.submitted)
        self.assertIn('attendance_result_pending', self.output.getvalue())

    def test_legacy_salon_category_can_be_reserved(self):
        self.school.rows = [lecture('coffee', HDLX_DISPLAY='“SEU咖啡间"系列沙龙活动')]
        self.execute()
        self.assertEqual(self.school.submitted, ['coffee'])

    def test_salons_count_toward_total_but_not_required_categories(self):
        rows = attended()
        for row in rows[3:]:
            row['HDLX_DISPLAY'] = COFFEE_CATEGORY
        self.school.history = rows
        self.assertEqual(self.execute(settings=Settings(state_dir=self.path,
                         categories=(SERIES_CATEGORIES[0],))), 0)
        self.assertTrue(progress(rows, 100).done)
        for row in rows:
            row['HDLX_DISPLAY'] = COFFEE_CATEGORY
        current = progress(rows, 100)
        self.assertFalse(current.done)
        self.assertFalse(current.needs(COFFEE_CATEGORY))
        self.assertEqual(len(current.missing), 3)

    def test_salons_participate_in_planning_conflicts_and_pending_attendance(self):
        self.school.history = attended(7)
        self.school.history.append(lecture('salon', YYZT='已预约', HDLX_DISPLAY=COFFEE_CATEGORY))
        self.school.rows = [lecture('extra', HDLX_DISPLAY=COFFEE_CATEGORY)]
        self.execute()
        self.assertEqual(self.saved()['health']['phase'], 'stopped')
        self.assertFalse(self.school.submitted)
        self.school.history[-1]['YYZT'] = '已取消'
        self.execute()
        self.assertEqual(self.school.submitted, ['extra'])
        with self.assertRaisesRegex(ValueError, 'attendance_result_pending'):
            progress([lecture('expired', YYZT='已预约', HDLX_DISPLAY=COFFEE_CATEGORY)], 253000000000)

    def test_salon_reservation_also_blocks_conflicting_required_lecture(self):
        self.school.history = [lecture('salon', YYZT='已预约', HDLX_DISPLAY=COFFEE_CATEGORY)]
        self.school.rows = [lecture('law', HDLX_DISPLAY=SERIES_CATEGORIES[1])]
        self.execute()
        self.assertFalse(self.school.submitted)
        self.assertEqual(self.saved()['selection']['activities'][0]['reason'], 'time_conflict')

    def test_notices_are_test_only_even_when_the_category_is_allowed(self):
        self.school.rows = [lecture('tickets', HDMC='研究生购票优惠公告',
            HDLX_DISPLAY=COFFEE_CATEGORY, IS_ONLINE=None),
            lecture('testing', HDMC='系统测试（请勿预约！！！）', IS_ONLINE=None)]
        self.execute()
        self.assertFalse(self.school.submitted)
        self.assertEqual([row['reason'] for row in self.saved()['selection']['activities']],
                         ['notice_test_only', 'notice_test_only'])
        history = [{**row, 'YYZT': '已预约'} for row in self.school.rows]
        self.assertEqual(sum(progress(history, 100).planned.values()), 0)

    def test_diagnostics_retain_selection_changes_and_safe_attempt_outcomes(self):
        self.school.rows = [lecture()]
        def wrong_captcha(wid, code):
            return {'code': 1, 'msg': '验证码错误 PRIVATE'}
        self.school.submit = wrong_captcha
        self.execute()
        rows = [json.loads(line) for line in (self.path / 'diagnostics.jsonl').read_text().splitlines()]
        self.assertEqual(len([row for row in rows if row['event'] == 'submission_started']), 4)
        self.assertEqual([row['outcome'] for row in rows if row['event'] == 'submission_reply'],
                         ['captcha_wrong'] * 4)
        self.assertIn('captcha_cooldown', [row['event'] for row in rows])
        self.assertNotIn('PRIVATE', json.dumps(rows))
        self.assertEqual(rows[0]['activities'][0]['wid'], 'one')
        before = len([row for row in rows if row['event'] == 'selection_changed'])
        self.school.rows[0]['YYZT'] = '不可预约'
        self.school.rows[0]['availability_reason'] = 'capacity_full'
        self.execute()
        rows = [json.loads(line) for line in (self.path / 'diagnostics.jsonl').read_text().splitlines()]
        self.assertGreater(len([row for row in rows if row['event'] == 'selection_changed']), before)
        self.assertNotIn('测试讲座', self.output.getvalue())

    def test_full_reply_is_recorded_without_leaving_pending_or_retrying(self):
        calls = []
        self.school.rows = [lecture()]
        def full(wid, code):
            calls.append(wid)
            return {'code': 1, 'msg': '名额已满'}
        self.school.submit = full
        self.execute()
        self.assertEqual(calls, ['one'])
        self.assertEqual(self.saved()['status'], 'scanning')
        rows = [json.loads(line) for line in (self.path / 'diagnostics.jsonl').read_text().splitlines()]
        self.assertEqual([row['outcome'] for row in rows if row['event'] == 'submission_reply'], ['unavailable'])

    def test_submission_feedback_is_redacted_and_never_releases_pending(self):
        for feedback, status in (('unrecognized_message', 200), ('no_message', 503), ('PRIVATE', 'PRIVATE')):
            with self.subTest(feedback=feedback), TemporaryDirectory() as directory:
                settings=Settings(state_dir=Path(directory))
                self.school.rows=[lecture()]
                self.school.submit=Mock(return_value={'feedback':feedback,'http_status':status,'msg':'PRIVATE'})
                self.execute(settings=settings)
                self.execute(settings=settings)
                self.school.submit.assert_called_once()
                saved=json.loads((settings.state_dir/'task.json').read_text())
                self.assertEqual(saved['status'],'pending')
                diagnostics=(settings.state_dir/'diagnostics.jsonl').read_text()
                self.assertNotIn('PRIVATE',diagnostics)
                reply=next(json.loads(line) for line in diagnostics.splitlines()
                           if json.loads(line)['event']=='submission_reply')
                self.assertEqual(reply['outcome'],'unconfirmed')
                self.assertEqual(reply['feedback'],feedback if feedback!='PRIVATE' else None)
                self.assertEqual(reply['http_status'],status if status!='PRIVATE' else None)

    def test_ended_unconfirmed_record_blocks_even_when_overlapping_attendance(self):
        self.school.history = [attended(1)[0], lecture('unconfirmed', YYZT='已预约',
            KSSJ='2020-01-01 10:30:00', JSSJ='2020-01-01 11:30:00')]
        self.school.rows = [lecture('new')]
        self.execute(clock=lambda: 1700000000)
        self.assertFalse(self.school.submitted)
        self.assertEqual(self.saved()['health']['last_error'], 'attendance_result_pending')

    def test_ocr_attempts_are_bounded_and_later_candidate_is_tried(self):
        self.school.rows = [lecture(), lecture('two')]
        answers = iter(['中文', '', '', '', '1234'])
        self.execute(recognize=lambda _: next(answers))
        self.assertEqual(self.school.submitted, ['two'])
        self.assertEqual(self.saved()['cooldowns']['one'], 400)

    def test_explicit_preflight_failure_does_not_block_next_candidate(self):
        self.school.rows = [lecture(), lecture('two')]
        self.school.rejected.add('one')
        self.execute()
        self.assertEqual(self.school.submitted, ['two'])

    def test_three_failures_notify_once_and_backoff_persists(self):
        def fail():
            raise RemoteError('page_data_incomplete')
        self.school.mine = fail
        delays = []
        def sleep(seconds):
            delays.append(seconds)
            if len(delays) == 4:
                raise KeyboardInterrupt
        self.execute(sleep=sleep)
        self.assertEqual(delays, [20, 40, 80, 160])
        self.assertEqual(self.events, ['runtime_problem', 'query_failure'])
        self.assertEqual(self.saved()['retry_at'], 260)

    def test_opening_transient_failures_retry_in_one_second_without_mail(self):
        opening=datetime(2030,1,1,9,tzinfo=SHANGHAI)
        for stage, reason in (('mine','page_not_ready'), ('activities','navigation_failed'),
                              ('preflight','preflight_failed')):
            with self.subTest(stage=stage), TemporaryDirectory() as directory:
                path=Path(directory)
                task=Task(path,'test-card')
                task.data['selection']={'activities':[dict(reason='candidate',reservation_start=opening.isoformat())]}
                task.save(); task.close()
                self.school=School()
                self.school.rows=[lecture(YYKSSJ=opening.strftime('%Y-%m-%d %H:%M:%S'))]
                setattr(self.school,stage,Mock(side_effect=RemoteError(reason)))
                now=[opening.timestamp()]
                delays, sent=[], []
                def wait(seconds):
                    self.assertEqual(sent,[])
                    delays.append(seconds)
                    now[0]+=seconds
                    if len(delays)==4: raise KeyboardInterrupt
                self.execute(settings=Settings(state_dir=path),clock=lambda:now[0],sleep=wait,
                             notify=lambda event,details='':sent.append(event))
                self.assertEqual(delays,[1,1,1,1])
                self.assertEqual(sent,['runtime_problem'])
                self.assertEqual(self.school.submitted,[])
                errors=[json.loads(line) for line in (path/'diagnostics.jsonl').read_text().splitlines()
                        if json.loads(line)['event']=='scan_error']
                self.assertEqual([error['retry_seconds'] for error in errors],[1,1,1,1])

    def test_opening_short_retry_expires_and_defers_daily_report(self):
        opening=datetime(2030,1,1,20,tzinfo=SHANGHAI)
        task=Task(self.path,'test-card')
        task.data['selection']={'activities':[dict(reason='candidate',reservation_start=opening.isoformat())]}
        task.save(); task.close()
        self.school.mine=Mock(side_effect=RemoteError('page_not_ready'))
        now=[opening.timestamp()+599]
        delays=[]
        def wait(seconds):
            delays.append(seconds)
            if len(delays)==1:
                self.assertEqual(self.events,[])
                now[0]+=2
            else: raise KeyboardInterrupt
        self.execute(clock=lambda:now[0],sleep=wait)
        self.assertEqual(delays,[1,40])
        self.assertIn('daily_report',self.events)

    def test_opening_preserves_limits_validation_and_pending_backoff(self):
        opening=datetime(2030,1,1,9,tzinfo=SHANGHAI)
        for error, pending, expected in ((RemoteError('rate_limited',45),False,45),
                                         (AuthenticationExpired('authentication_expired'),False,20),
                                         (ValueError('invalid_data'),False,20),
                                         (RemoteError('page_not_ready'),True,20)):
            with self.subTest(error=error,pending=pending), TemporaryDirectory() as directory:
                path=Path(directory)
                task=Task(path,'test-card')
                task.data['selection']={'activities':[dict(reason='candidate',reservation_start=opening.isoformat())]}
                if pending: task.data.update(status='pending',activity='one')
                task.save(); task.close()
                self.school=School()
                self.school.mine=Mock(side_effect=error)
                delays=[]
                def wait(seconds):
                    delays.append(seconds)
                    raise KeyboardInterrupt
                self.execute(settings=Settings(state_dir=path),clock=lambda:opening.timestamp(),sleep=wait)
                self.assertEqual(delays,[expected])

    def test_opening_unknown_submission_checks_soon_without_resubmission(self):
        opening=datetime(2030,1,1,9,tzinfo=SHANGHAI)
        self.school.rows=[lecture(YYKSSJ=opening.strftime('%Y-%m-%d %H:%M:%S'))]
        self.school.unknown=True
        delays=[]
        def wait(seconds):
            delays.append(seconds)
            if len(delays)==2: raise KeyboardInterrupt
        self.execute(clock=lambda:opening.timestamp(),sleep=wait)
        self.assertEqual(delays,[1,10])
        self.assertEqual(self.school.submitted,['one'])
        self.assertEqual(self.saved()['status'],'pending')

    def test_opening_rate_limit_is_not_inflated_by_earlier_short_retries(self):
        opening=datetime(2030,1,1,9,tzinfo=SHANGHAI)
        task=Task(self.path,'test-card')
        task.data['selection']={'activities':[dict(reason='candidate',reservation_start=opening.isoformat())]}
        task.save(); task.close()
        self.school.mine=Mock(side_effect=[RemoteError('page_not_ready') for _ in range(4)]
                              +[RemoteError('rate_limited',45)])
        delays=[]
        def wait(seconds):
            delays.append(seconds)
            if len(delays)==5: raise KeyboardInterrupt
        self.execute(clock=lambda:opening.timestamp(),sleep=wait)
        self.assertEqual(delays,[1,1,1,1,45])

    def test_resuming_opening_retry_preserves_wait_without_sending_daily_mail(self):
        opening=datetime(2030,1,1,20,tzinfo=SHANGHAI)
        task=Task(self.path,'test-card')
        task.data.update(retry_at=opening.timestamp()+1,selection={'activities':[
            dict(reason='candidate',reservation_start=opening.isoformat())]})
        task.save(); task.close()
        self.execute(clock=lambda:opening.timestamp())
        self.assertEqual(self.events,[])
        self.assertEqual(self.saved()['retry_at'],opening.timestamp()+1)
        self.assertEqual(self.school.authentications,0)

    def test_query_alerts_survive_restart_and_limit_flapping(self):
        now = [100]
        sent = []
        def notify(event, details=''):
            sent.append((event, details))
        def fail_three():
            self.school = School()
            calls = [0]
            def mine():
                calls[0] += 1
                if calls[0] > 3:
                    raise KeyboardInterrupt
                raise RemoteError('page_not_ready')
            self.school.mine = mine
            self.execute(clock=lambda: now[0], notify=notify, sleep=lambda _: None)
        fail_three()
        self.assertEqual(self.saved()['alerts'], {'query_failure': 100})
        self.assertIn('连续失败：3 次', sent[1][1])
        self.assertIn('最近业务错误：page_not_ready', sent[1][1])
        self.assertNotIn('下次检查计划：尚未安排', sent[1][1])
        fail_three()
        self.assertEqual([event for event, _ in sent], ['runtime_problem', 'query_failure'])
        self.school = School()
        self.execute(clock=lambda: now[0], notify=notify)
        self.assertEqual(self.saved()['alerts'], {})
        self.assertEqual([event for event, _ in sent], ['runtime_problem', 'query_failure', 'query_recovered'])
        fail_three()
        self.assertEqual(len(sent), 3)
        now[0] += 901
        fail_three()
        self.assertEqual([event for event, _ in sent],
                         ['runtime_problem', 'query_failure', 'query_recovered', 'runtime_problem', 'query_failure'])

    def test_pending_alert_is_not_repeated_on_restart_and_success_has_fresh_progress(self):
        task = Task(self.path, 'test-card')
        task.data.update(status='pending', activity='one')
        task.save()
        task.close()
        sent = []
        def notify(event, details=''):
            sent.append((event, details))
        self.execute(notify=notify)
        self.execute(notify=notify)
        self.assertEqual([event for event, _ in sent], ['reservation_unconfirmed'])
        self.school.history = [lecture(YYZT='已预约')]
        with patch('app.time.monotonic', side_effect=[10, 12.345]):
            self.execute(notify=notify)
        self.assertEqual([event for event, _ in sent], ['reservation_unconfirmed', 'reservation_succeeded'])
        self.assertIn('待参加：1', sent[-1][1])
        self.assertNotIn('测试讲座', sent[-1][1])
        self.assertEqual(self.saved()['alerts'], {})
        health = self.saved()['health']
        self.assertEqual(health['last_mail_event'], 'reservation_succeeded')
        self.assertEqual(health['last_mail_duration_seconds'], 2.345)
        self.execute(notify=None)
        self.assertEqual(self.saved()['health']['last_mail_event'], 'reservation_succeeded')
        self.assertEqual(self.saved()['health']['last_mail_duration_seconds'], 2.345)

    def test_query_alert_suppressed_by_cooldown_is_sent_if_failure_continues(self):
        task = Task(self.path, 'test-card')
        task.data['last_query_alert_at'] = 100
        task.save()
        task.close()
        now = [200]
        def fail():
            raise RemoteError('page_not_ready')
        def wait(seconds):
            if 'query_failure' in self.events:
                raise KeyboardInterrupt
            now[0] += seconds
        self.school.mine = fail
        self.execute(clock=lambda: now[0], sleep=wait)
        self.assertEqual(self.events.count('query_failure'), 1)
        self.assertIn('runtime_problem', self.events)
        self.assertGreaterEqual(self.saved()['last_query_alert_at'] - 100, 900)

    def test_authentication_alert_persists_until_authentication_succeeds(self):
        self.school.error = AuthenticationRequired()
        self.execute()
        self.execute()
        self.assertEqual(self.events, ['authentication_required'])
        self.school.error = None
        self.execute()
        self.assertNotIn('authentication_required', self.saved()['alerts'])
        self.school.error = AuthenticationRequired()
        self.execute()
        self.assertEqual(self.events, ['authentication_required', 'authentication_required'])

    def test_disabled_mail_does_not_consume_alert_and_failed_attempt_is_not_retried(self):
        self.school.error = AuthenticationRequired()
        self.execute(notify=None)
        self.assertEqual(self.saved()['alerts'], {})
        attempts = []
        def fail(event, details=''):
            attempts.append(event)
            raise OSError('PRIVATE')
        self.execute(notify=fail)
        self.execute(notify=fail)
        self.assertEqual(attempts, ['authentication_required'])
        self.assertEqual(self.saved()['health']['last_mail_status'], 'failed')
        self.assertNotIn('PRIVATE', self.output.getvalue())

    def test_invalid_notification_history_stops_before_school_access(self):
        for changes in ({'alerts': []}, {'alerts': {'query_failure': 'PRIVATE'}},
                        {'last_query_alert_at': float('nan')},
                        {'problem_mail_times': {'page_not_ready': 'PRIVATE'}},
                        {'health': {'last_mail_event': 'PRIVATE'}},
                        {'health': {'last_mail_duration_seconds': -1}}):
            with self.subTest(changes=changes), TemporaryDirectory() as directory:
                path = Path(directory)
                task = Task(path, 'test-card')
                task.close()
                data = json.loads((path / 'task.json').read_text())
                data.update(changes)
                (path / 'task.json').write_text(json.dumps(data))
                self.school = School()
                self.assertEqual(self.execute(settings=Settings(state_dir=path)), 1)
                self.assertEqual(self.school.authentications, 0)
                self.assertNotIn('PRIVATE', self.output.getvalue())

    def test_runtime_problem_mail_is_rate_limited_across_restart_and_does_not_retry_failure(self):
        self.school.rows = [lecture()]
        self.school.rejected.add('one')
        sent = []
        def notify(event, details=''):
            sent.append((event, details))
            raise OSError('PRIVATE')
        self.execute(notify=notify)
        self.execute(notify=notify)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][0], 'runtime_problem')
        self.assertIn('preflight_unavailable', sent[0][1])
        self.assertNotIn('测试讲座', sent[0][1])
        self.assertNotIn('PRIVATE', self.output.getvalue())
        self.execute(notify=notify, clock=lambda: 1001)
        self.assertEqual(len(sent), 2)

    def test_runtime_problem_mail_waits_during_opening_scans(self):
        now = [datetime(2030, 1, 1, 9, 17, tzinfo=SHANGHAI).timestamp()]
        opening = datetime.fromtimestamp(now[0], SHANGHAI).strftime('%Y-%m-%d %H:%M:%S')
        self.school.rows = [lecture(YYKSSJ=opening)]
        self.school.rejected.add('one')
        sent = []
        delays = []
        def wait(seconds):
            self.assertEqual(sent, [])
            delays.append(seconds)
            now[0] += seconds
            if len(delays) == 2:
                raise KeyboardInterrupt
        self.execute(clock=lambda: now[0], sleep=wait,
                     notify=lambda event, details='': sent.append((event, details)))
        self.assertEqual(delays, [1, 1])
        self.assertEqual([event for event, _ in sent], ['runtime_problem'])

    def test_query_recovery_notifies_once_per_alerted_streak(self):
        for failure_count in (2, 3):
            with self.subTest(failures=failure_count), TemporaryDirectory() as directory:
                calls = [0]
                events = []
                def activities():
                    calls[0] += 1
                    if calls[0] in range(1, failure_count + 1) or calls[0] in range(failure_count + 3, 2 * failure_count + 3):
                        raise RemoteError('page_not_ready')
                    if calls[0] == 2 * failure_count + 5:
                        raise KeyboardInterrupt
                    return []
                self.school.activities = activities
                self.execute(settings=Settings(state_dir=Path(directory)), notify=lambda event, details='': events.append(event),
                             sleep=lambda _: None)
                self.assertEqual(events, ['runtime_problem', 'query_failure', 'query_recovered']
                                 if failure_count == 3 else ['runtime_problem'])

    def test_failed_recovery_email_is_not_retried(self):
        calls = [0]
        events = []
        def activities():
            calls[0] += 1
            if calls[0] <= 3:
                raise RemoteError('page_not_ready')
            if calls[0] == 6:
                raise KeyboardInterrupt
            return []
        def notify(event, details=''):
            events.append(event)
            if event == 'query_recovered':
                raise OSError('PRIVATE')
        self.school.activities = activities
        self.execute(notify=notify, sleep=lambda _: None)
        self.assertEqual(events, ['runtime_problem', 'query_failure', 'query_recovered'])
        self.assertIn('notification_failed', self.output.getvalue())
        self.assertNotIn('PRIVATE', self.output.getvalue())

    def test_query_recovery_covers_completed_planned_and_pending_tasks(self):
        cases = (
            ('done', attended(), ['goal_completed']),
            ('planned', [dict(row, SFDK='0', KSSJ=f'2030-01-{i+1:02} 10:00:00',
                              JSSJ=f'2030-01-{i+1:02} 11:00:00') for i, row in enumerate(attended())], []),
            ('pending', [], ['reservation_unconfirmed']),
        )
        for mode, history, extra_events in cases:
            with self.subTest(mode=mode), TemporaryDirectory() as directory:
                path = Path(directory)
                if mode == 'pending':
                    task = Task(path, 'test-card')
                    task.data.update(status='pending', activity='one')
                    task.save(); task.close()
                calls = [0]
                events = []
                def mine():
                    calls[0] += 1
                    if calls[0] <= 3:
                        raise RemoteError('page_not_ready')
                    return history
                def sleep(_):
                    if calls[0] >= 4:
                        if mode == 'planned':
                            self.assertEqual(json.loads((path / 'task.json').read_text())['health']['phase'],
                                             'waiting_for_attendance')
                        raise KeyboardInterrupt
                self.school.mine = mine
                self.execute(settings=Settings(state_dir=path), notify=lambda event, details='': events.append(event), sleep=sleep)
                self.assertEqual(events, ['runtime_problem', 'query_failure', 'query_recovered'] + extra_events)
                self.assertFalse(self.school.submitted)

    def test_submission_rate_limit_waits_before_confirmation(self):
        self.school.rows = [lecture()]
        def limited(wid, code):
            raise RemoteError('rate_limited', 600)
        self.school.submit = limited
        delays = []
        def sleep(seconds):
            delays.append(seconds)
            raise KeyboardInterrupt
        self.execute(sleep=sleep)
        self.assertEqual(delays, [600])
        self.assertEqual(self.saved()['status'], 'pending')

    def test_authentication_requirement_stops_without_business_and_emails_once(self):
        self.school.error = AuthenticationRequired()
        self.school.rows = [lecture()]
        self.assertEqual(self.execute(), 1)
        self.assertEqual(self.events, ['authentication_required'])
        self.assertEqual(self.saved()['health']['phase'], 'manual_required')
        self.assertFalse(self.school.submitted)
        self.assertEqual(self.school.authentications, 1)

    def test_notification_failure_cannot_repeat_booking_or_expose_exception(self):
        self.school.rows = [lecture()]
        def fail(_, details=''):
            raise RuntimeError('PRIVATE password')
        self.execute(notify=fail)
        self.execute(notify=fail)
        self.assertEqual(self.school.submitted, ['one'])
        self.assertIn('notification_failed', self.output.getvalue())
        self.assertNotIn('PRIVATE', self.output.getvalue())

    def test_read_only_has_no_checkpoint_submission_or_email(self):
        self.school.history = attended()
        self.assertEqual(self.execute(check_only=True), 0)
        self.assertFalse((self.path / 'task.json').exists())
        self.assertFalse(self.school.submitted)
        self.assertFalse(self.events)

    def test_explicit_offline_and_unknown_titles_cannot_bypass_campus_filter(self):
        client = BrowserClient(None, {})
        for title, expected in (('【线下】线上教育的法律问题', 'campus_not_selected'),
                                ('线上教育讲座', 'invalid_activity_data')):
            with self.subTest(title=title):
                raw = {'WID': 'offline', 'JZMC': title, 'JZXL_DISPLAY': SERIES_CATEGORIES[1],
                       'JZDD': '九龙湖校区教室', 'JZSJ': '2030-01-01 10:00:00',
                       'HDJSSJ': '2030-01-01 11:00:00', 'btn_yy': True}
                with patch.object(client, '_reload', return_value=[raw]):
                    self.school.rows = client.activities()
                self.execute(settings=Settings(state_dir=self.path, campuses=('无锡校区',)))
                self.assertFalse(self.school.submitted)
                self.assertEqual(self.saved()['selection']['activities'][0]['reason'], expected)

    def test_read_only_and_normal_run_skip_the_same_invalid_activity_data(self):
        for changes in ({'HDMC': None}, {'HDLX_DISPLAY': None}, {'HDLX_DISPLAY': ''},
                        {'HDLX_DISPLAY': ' '}, {'HDLX_DISPLAY': 7},
                        {'IS_ONLINE': None}, {'JZDD': None}, {'JZDD': ''},
                        {'KSSJ': 'unknown'}, {'WID': ''}, {'YYZT': 'unknown'},
                        {'JSSJ': '2030-01-01 09:00:00'}, {'JSSJ': None},
                        {'YYZT': '不可预约', 'availability_reason': 'unknown'},
                        {'YYKSSJ': 'unknown'}, {'YYKSSJ': '2030-01-02 12:00:00',
                                                  'YYJSSJ': '2030-01-01 12:00:00'},
                        {'YYKSSJ': '2030-01-01 12:00:00', 'YYJSSJ': '2030-01-01 12:00:00'},
                        {'HDMC': None, 'YYZT': '不可预约'}):
            with self.subTest(changes=changes), TemporaryDirectory() as directory:
                settings = Settings(state_dir=Path(directory))
                self.school = School()
                self.output = io.StringIO()
                self.events.clear()
                self.school.rows = [lecture(**changes)]
                self.assertEqual(self.execute(settings=settings, check_only=True), 0)
                self.assertIn('event=read_only_complete', self.output.getvalue())
                self.assertIn('event=invalid_activity_data', self.output.getvalue())
                self.assertFalse((settings.state_dir / 'task.json').exists())
                self.assertFalse(self.events)
                self.execute(settings=settings)
                saved = json.loads((Path(directory) / 'task.json').read_text())
                self.assertEqual(saved['health']['last_error'], 'invalid_activity_data')
                self.assertEqual(saved['health']['failure_count'], 0)
                self.assertEqual(saved['selection']['activities'][0]['reason'], 'invalid_activity_data')
                self.assertIn('runtime_problem', self.events)
                self.assertFalse(self.school.submitted)

    def test_unselected_categories_do_not_block_valid_activities(self):
        client = BrowserClient(None, {})
        raw = [
            {'JZMC': '系统测试（请勿预约）', 'JZXL_DISPLAY': '非目标公告', 'YYKSSJ': 'invalid'},
            {'JZMC': None, 'JZXL_DISPLAY': SERIES_CATEGORIES[1]},
        ]
        with patch.object(client, '_reload', return_value=raw):
            excluded = client.activities()
        for check_only in (True, False):
            with self.subTest(check_only=check_only), TemporaryDirectory() as directory:
                self.school = School()
                self.school.rows = excluded + [lecture('eligible')]
                settings = Settings(state_dir=Path(directory), categories=(SERIES_CATEGORIES[0],))
                self.assertEqual(self.execute(settings=settings, check_only=check_only),
                                 0 if check_only else 130)
                if check_only:
                    line = next(line for line in self.output.getvalue().splitlines()
                                if line.startswith('activity_details='))
                    details = json.loads(line.partition('=')[2])
                    self.assertFalse((settings.state_dir / 'task.json').exists())
                else:
                    details = json.loads((settings.state_dir / 'task.json').read_text())['selection']['activities']
                self.assertEqual([item['reason'] for item in details[:2]],
                                 ['notice_test_only', 'category_not_allowed'])
                self.assertTrue(all(item['reservation_start'] is None
                                    and item['reservation_end'] is None for item in details[:2]))
                self.assertEqual(details[1]['title'], '')
                self.assertEqual(self.school.submitted, [] if check_only else ['eligible'])

    def test_selected_custom_category_still_requires_valid_activity_data(self):
        self.school.rows = [lecture(HDLX_DISPLAY='自定义类别', IS_ONLINE=None)]
        self.assertEqual(self.execute(settings=Settings(state_dir=self.path,
                         categories=('自定义类别',)), check_only=True), 0)
        self.assertIn('"reason": "invalid_activity_data"', self.output.getvalue())
        self.assertFalse(self.school.submitted)

    def test_selection_records_each_first_reason_and_reservation_window(self):
        self.school.history = [lecture('booked', YYZT='已预约')]
        future = dict(KSSJ='2030-01-02 10:00:00', JSSJ='2030-01-02 11:00:00')
        self.school.rows = [
            lecture('not_started', YYZT='不可预约', availability_reason='reservation_not_started',
                    YYKSSJ='2030-01-01 19:00:00', YYJSSJ='2030-01-02 09:00:00'),
            lecture('full', YYZT='不可预约', availability_reason='capacity_full'),
            lecture('closed', YYZT='不可预约'), lecture('booked'),
            lecture('category', HDLX_DISPLAY='沙龙'),
            lecture('campus', IS_ONLINE=False, JZDD='九龙湖校区教室'),
            lecture('conflict'), lecture('eligible', **future)]
        self.school.rejected = {'eligible'}
        self.execute()
        selection = self.saved()['selection']
        self.assertEqual(selection['updated_at'], 100)
        self.assertEqual([item['reason'] for item in selection['activities']],
            ['reservation_not_started', 'capacity_full', 'not_reservable', 'already_reserved',
             'category_not_allowed', 'campus_not_selected', 'time_conflict', 'candidate'])
        first = selection['activities'][0]
        self.assertEqual(first['reservation_start'], '2030-01-01T19:00:00+08:00')
        self.assertEqual(first['reservation_end'], '2030-01-02T09:00:00+08:00')
        self.assertEqual(self.saved()['health']['candidate_count'], 1)
        self.assertNotIn('测试讲座', self.output.getvalue())
        self.assertNotIn('测试讲座', (self.path / 'events.log').read_text())
        self.assertFalse(self.school.submitted)
        saved = (self.path / 'task.json').read_bytes()
        self.assertEqual(self.execute(check_only=True), 0)
        self.assertEqual((self.path / 'task.json').read_bytes(), saved)
        self.assertIn('reservation_not_started', self.output.getvalue())

    def test_mail_history_survives_restart_and_disabled_notifications(self):
        due = datetime(2026, 10, 18, 20, tzinfo=SHANGHAI).timestamp()
        for fail in (False, True):
            with self.subTest(fail=fail), TemporaryDirectory() as directory:
                settings = Settings(state_dir=Path(directory))
                sent = []
                def notify(event, details=''):
                    sent.append(event)
                    if fail:
                        raise OSError('PRIVATE')
                for notify_again in (notify, notify, None):
                    self.execute(settings=settings, notify=notify_again, clock=lambda: due)
                    health = json.loads((Path(directory) / 'task.json').read_text())['health']
                    self.assertEqual(health['last_mail_at'], due)
                    self.assertEqual(health['last_mail_status'], 'failed' if fail else 'accepted')
                self.assertEqual(sent, ['daily_report'])

    def test_legacy_mail_result_is_restored_without_guessing_lost_results(self):
        self.execute()
        data = self.saved()
        data['health'].pop('last_mail_status')
        data['health'].update(mail_status='accepted', last_mail_at=90)
        (self.path / 'task.json').write_text(json.dumps(data))
        self.execute()
        self.assertEqual(self.saved()['health']['last_mail_status'], 'accepted')
        self.assertEqual(self.saved()['health']['last_mail_at'], 90)
        data['health'].update(mail_status='ready', last_mail_at=0)
        data['last_report_at'] = 90
        (self.path / 'task.json').write_text(json.dumps(data))
        self.execute()
        self.assertEqual(self.saved()['health']['last_mail_status'], 'never')
        self.assertEqual(self.saved()['health']['last_mail_at'], 0)
        data['health'].pop('last_mail_error', None)
        data['health'].update(last_mail_status='failed')
        (self.path / 'task.json').write_text(json.dumps(data))
        self.execute()
        self.assertEqual(self.saved()['health']['last_mail_error'], 'unknown')

    def test_daily_report_counts_progress_and_deduplicates_across_restart(self):
        self.school.history = attended(4) + [lecture('planned', YYZT='已预约')]
        now = [datetime(2026, 10, 18, 20, tzinfo=SHANGHAI).timestamp()]
        reports = []
        def notify(event, details=''):
            reports.append((event, details))
        self.execute(clock=lambda: now[0], notify=notify)
        self.execute(clock=lambda: now[0], notify=notify)
        self.assertEqual([event for event, _ in reports], ['daily_report'])
        self.assertIn('已选听：4 / 8', reports[0][1])
        self.assertIn('待参加：1', reports[0][1])
        self.assertIn('必需类别缺口：无', reports[0][1])
        self.assertIn('最近成功查询：2026-10-18T20:00:00+08:00', reports[0][1])
        self.assertNotIn('测试讲座', reports[0][1])
        now[0] += 86400
        self.execute(clock=lambda: now[0], notify=notify)
        self.assertEqual([event for event, _ in reports], ['daily_report', 'daily_report'])

    def test_daily_report_wakes_at_beijing_twenty_during_backoff(self):
        due = datetime(2026, 10, 18, 20, tzinfo=SHANGHAI).timestamp()
        now = [due - 5]
        def fail():
            raise RemoteError('page_data_incomplete')
        self.school.mine = fail
        reports, delays = [], []
        def notify(event, details=''):
            reports.append((event, details, now[0]))
        def wait(seconds):
            delays.append(seconds)
            if len(delays) == 2:
                raise KeyboardInterrupt
            now[0] += seconds
        self.execute(clock=lambda: now[0], sleep=wait, notify=notify)
        self.assertEqual(delays, [5, 15])
        self.assertEqual([(event, at) for event, _, at in reports],
                         [('runtime_problem', due - 5), ('daily_report', due)])
        self.assertIn('已选听：未知', reports[0][1])
        self.assertIn('尚无成功查询', reports[0][1])
        self.assertIn('page_data_incomplete', reports[0][1])
        self.assertEqual(self.saved()['retry_at'], due + 15)

    def test_daily_report_failure_preserves_pending_and_is_not_retried(self):
        self.school.rows = [lecture()]
        self.school.unknown = True
        now = [datetime(2026, 10, 18, 20, tzinfo=SHANGHAI).timestamp()]
        reports = []
        def notify(event, details=''):
            if event == 'daily_report':
                reports.append(details)
                raise OSError('PRIVATE SMTP credentials')
        self.execute(clock=lambda: now[0], notify=notify)
        self.assertEqual(self.saved()['status'], 'pending')
        now[0] += 21
        self.execute(clock=lambda: now[0], notify=notify)
        self.assertEqual(self.school.submitted, ['one'])
        self.assertEqual(len(reports), 1)
        self.assertIn('预约结果待确认', reports[0])
        self.assertEqual(self.saved()['status'], 'pending')
        self.assertIn('notification_failed', self.output.getvalue())
        self.assertNotIn('PRIVATE', self.output.getvalue())

    def test_daily_reports_are_disabled_without_mail_and_in_read_only_mode(self):
        now = datetime(2026, 10, 18, 20, tzinfo=SHANGHAI).timestamp()
        self.execute(check_only=True, clock=lambda: now)
        self.assertFalse(self.events)
        self.assertFalse((self.path / 'task.json').exists())
        self.execute(clock=lambda: now, notify=None)
        self.assertNotIn('last_report_at', self.saved())
        self.assertNotIn('daily_report', self.output.getvalue())

    def test_invalid_daily_report_checkpoint_stops_before_authentication(self):
        self.execute()
        data = self.saved()
        data['last_report_at'] = 'PRIVATE'
        (self.path / 'task.json').write_text(json.dumps(data))
        self.school = School()
        self.assertEqual(self.execute(), 1)
        self.assertEqual(self.school.authentications, 0)
        self.assertNotIn('PRIVATE', self.output.getvalue())

    def test_active_task_cannot_reset_and_state_is_account_bound(self):
        self.execute()
        self.assertEqual(self.execute(new_task=True), 1)
        with self.assertRaisesRegex(ValueError, 'state_account_mismatch'):
            Task(self.path, 'another-card')

    def test_corrupt_checkpoint_stops_before_authentication(self):
        (self.path / 'task.json').write_text('{bad')
        self.assertEqual(self.execute(), 1)
        self.assertEqual(self.school.authentications, 0)

    def test_process_lock_blocks_second_runner_and_is_released(self):
        task = Task(self.path, 'test-card')
        try:
            self.assertTrue(task_running(self.path))
            self.assertEqual(self.execute(), 1)
            self.assertEqual(self.school.authentications, 0)
        finally:
            task.close()
        self.assertFalse(task_running(self.path))

    def test_overlap_statistics_are_deterministic_and_do_not_change_school_records(self):
        rows = [lecture('a', YYZT='已预约'), lecture('b', YYZT='已预约',
            KSSJ='2030-01-01 10:30:00', JSSJ='2030-01-01 11:30:00'),
            lecture('c', YYZT='已预约', KSSJ='2030-01-01 11:10:00', JSSJ='2030-01-01 12:00:00')]
        before = json.dumps(rows)
        self.assertEqual(sum(progress(rows, 100).planned.values()), 2)
        self.assertEqual(progress(rows, 100), progress(list(reversed(rows)), 100))
        self.assertEqual(json.dumps(rows), before)


if __name__ == '__main__':
    unittest.main()
