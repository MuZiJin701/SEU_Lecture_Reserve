"""Offline regression checks for the rules ported from the HTTPS project."""

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from app import Settings, run
from browser_client import AuthenticationRequired, RemoteError
from model import SERIES_CATEGORIES, progress
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
                notify=options.pop('notify', self.events.append), **options)

    def saved(self):
        return json.loads((self.path / 'task.json').read_text())

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

    def test_ocr_attempts_are_bounded_and_later_candidate_is_tried(self):
        self.school.rows = [lecture(), lecture('two')]
        answers = iter(['', '', '', '', '1234'])
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
        def fail(_):
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
