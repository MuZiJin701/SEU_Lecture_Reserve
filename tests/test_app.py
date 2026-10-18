"""Offline regression checks for the rules ported from the HTTPS project."""

import io
import json
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from app import Settings, run
from browser_client import AuthenticationRequired, BrowserClient, BrowserClosed, RemoteError
from model import SERIES_CATEGORIES, SHANGHAI, progress
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
        row = next(row for row in self.rows if row['WID'] == wid)
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

    def test_unknown_history_and_conflicting_duplicates_block_submission(self):
        for history in ([lecture('old', YYZT='已预约', SFDK=None)],
                        [lecture('old', YYZT='已预约', KSSJ='unknown')],
                        [lecture('old', YYZT='已预约'), lecture('old', YYZT='已预约', SFDK='1')]):
            with self.subTest(history=history):
                self.school.history = history
                self.school.rows = [lecture()]
                self.execute()
                self.assertFalse(self.school.submitted)

    def test_expired_unconfirmed_attendance_waits_and_coffee_is_excluded(self):
        self.school.history = [lecture('old', YYZT='已预约')]
        self.school.rows = [lecture('coffee', HDLX_DISPLAY='“SEU咖啡间"系列沙龙活动')]
        self.execute(clock=lambda: 253000000000)
        self.assertFalse(self.school.submitted)
        self.assertIn('attendance_result_pending', self.output.getvalue())
        self.school.history = []
        self.execute()
        self.assertFalse(self.school.submitted)

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
        self.assertEqual(self.events, ['query_failure'])
        self.assertEqual(self.saved()['retry_at'], 260)

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
        self.assertIn('连续失败：3 次', sent[0][1])
        self.assertIn('最近业务错误：page_not_ready', sent[0][1])
        self.assertNotIn('下次检查计划：尚未安排', sent[0][1])
        fail_three()
        self.assertEqual([event for event, _ in sent], ['query_failure'])
        self.school = School()
        self.execute(clock=lambda: now[0], notify=notify)
        self.assertEqual(self.saved()['alerts'], {})
        self.assertEqual([event for event, _ in sent], ['query_failure', 'query_recovered'])
        fail_three()
        self.assertEqual(len(sent), 2)
        now[0] += 901
        fail_three()
        self.assertEqual([event for event, _ in sent], ['query_failure', 'query_recovered', 'query_failure'])

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
            if self.events:
                raise KeyboardInterrupt
            now[0] += seconds
        self.school.mine = fail
        self.execute(clock=lambda: now[0], sleep=wait)
        self.assertEqual(self.events, ['query_failure'])
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
                self.assertEqual(events, ['query_failure', 'query_recovered'] if failure_count == 3 else [])

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
        self.assertEqual(events, ['query_failure', 'query_recovered'])
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
                self.assertEqual(events, ['query_failure', 'query_recovered'] + extra_events)
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
                                ('线上教育讲座', 'activity_schema_unknown')):
            with self.subTest(title=title):
                raw = {'WID': 'offline', 'JZMC': title, 'JZXL_DISPLAY': SERIES_CATEGORIES[1],
                       'JZDD': '九龙湖校区教室', 'JZSJ': '2030-01-01 10:00:00',
                       'HDJSSJ': '2030-01-01 11:00:00', 'btn_yy': True}
                with patch.object(client, '_reload', return_value=[raw]):
                    self.school.rows = client.activities()
                self.execute(settings=Settings(state_dir=self.path, campuses=('无锡校区',)))
                self.assertFalse(self.school.submitted)
                if expected == 'activity_schema_unknown':
                    self.assertEqual(self.saved()['health']['last_error'], expected)
                else:
                    self.assertEqual(self.saved()['selection']['activities'][0]['reason'], expected)

    def test_read_only_and_normal_run_reject_the_same_invalid_activity_data(self):
        for changes in ({'HDMC': None}, {'IS_ONLINE': None}, {'JZDD': None}, {'JZDD': ''},
                        {'KSSJ': 'unknown'}, {'WID': ''}, {'YYZT': 'unknown'},
                        {'YYKSSJ': 'unknown'}, {'YYKSSJ': '2030-01-02 12:00:00',
                                                  'YYJSSJ': '2030-01-01 12:00:00'},
                        {'HDMC': None, 'YYZT': '不可预约'}):
            with self.subTest(changes=changes), TemporaryDirectory() as directory:
                settings = Settings(state_dir=Path(directory))
                self.school.rows = [lecture(**changes)]
                self.assertEqual(self.execute(settings=settings, check_only=True), 1)
                self.assertNotIn('event=read_only_complete', self.output.getvalue())
                self.execute(settings=settings)
                saved = json.loads((Path(directory) / 'task.json').read_text())
                self.assertEqual(saved['health']['last_error'], 'activity_schema_unknown')
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
        self.assertEqual([(event, at) for event, _, at in reports], [('daily_report', due)])
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
