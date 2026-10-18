"""Playwright CLI: browser actions with recoverable lecture-goal state."""

import argparse
import json
import math
import re
import signal
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from app import SELECTION_REASONS, Settings, run
from browser_client import BrowserClient
from config import load_config
from mail import MAIL_ERROR_REASONS, Mailer, mail_failure_reason
from model import SHANGHAI
from state import read_json, task_running


def show_status(directory: Path) -> None:
    try:
        saved = read_json(directory / 'task.json')
    except FileNotFoundError:
        saved = {}
    if not isinstance(saved, dict):
        raise ValueError('invalid_state')
    status = saved.get('status', 'not_started')
    if status not in ('not_started', 'scanning', 'pending', 'done'):
        raise ValueError('invalid_state')
    if saved.get('version') == 1 and status == 'done':
        status = 'legacy_completed'
    print('status=' + status)
    running = task_running(directory)
    print('process_running=' + str(running).lower())
    snapshot = saved.get('health')
    phases = {'starting', 'authentication', 'my_activities', 'activities', 'preflight', 'captcha',
              'submitting', 'confirming', 'waiting', 'waiting_for_attendance', 'manual_required',
              'backoff', 'done', 'stopped', 'failed'}
    timestamps = ('updated_at', 'last_query_at', 'last_error_at', 'next_check_at', 'last_mail_at')
    if (not isinstance(snapshot, dict) or not isinstance(snapshot.get('phase'), str)
            or snapshot['phase'] not in phases
            or snapshot.get('mail_status') not in ('disabled', 'ready', 'sending', 'accepted', 'failed')
            or snapshot.get('last_mail_status', 'never') not in ('never', 'sending', 'accepted', 'failed')
            or not isinstance(snapshot.get('last_mail_error', 'none'), str)
            or snapshot.get('last_mail_error', 'none') not in MAIL_ERROR_REASONS
            or not isinstance(snapshot.get('last_error'), str)
            or not re.fullmatch('[a-z_]{1,80}', snapshot['last_error'])
            or any(type(snapshot.get(key)) not in (int, float) or not math.isfinite(snapshot[key])
                   or not 0 <= snapshot[key] <= 253402214400 for key in timestamps)
            or type(snapshot.get('failure_count')) is not int or snapshot['failure_count'] < 0
            or any(snapshot.get(key) is not None and (type(snapshot[key]) is not int or snapshot[key] < 0)
                   for key in ('activity_count', 'candidate_count'))):
        print('phase=unknown')
        return
    print('phase=' + (snapshot['phase'] if running else 'stopped'))
    if not running:
        print('last_phase=' + snapshot['phase'])
    for key in timestamps:
        value = snapshot[key]
        print(key + '=' + (datetime.fromtimestamp(value, SHANGHAI).isoformat(timespec='seconds') if value else 'never'))
    for key, label in (('updated_at', 'snapshot_age_seconds'), ('last_query_at', 'last_query_age_seconds')):
        print(label + '=' + (str(max(0, round(time.time() - snapshot[key]))) if snapshot[key] else 'unknown'))
    for key in ('last_error', 'failure_count', 'mail_status', 'activity_count', 'candidate_count'):
        print(key + '=' + (str(snapshot[key]) if snapshot.get(key) is not None else 'unknown'))
    print('last_mail_status=' + snapshot.get('last_mail_status',
          snapshot['mail_status'] if snapshot['mail_status'] in ('sending', 'accepted', 'failed') else 'never'))
    print('last_mail_error=' + snapshot.get('last_mail_error',
          'unknown' if snapshot.get('last_mail_status', snapshot['mail_status']) == 'failed' else 'none'))
    selection = saved.get('selection')
    if selection is None:
        return
    if (not isinstance(selection, dict) or type(selection.get('updated_at')) not in (int, float)
            or not math.isfinite(selection['updated_at']) or not 0 <= selection['updated_at'] <= 253402214400
            or not isinstance(selection.get('activities'), list)
            or any(not isinstance(item, dict) or not isinstance(item.get('title'), str)
                   or not isinstance(item.get('reason'), str) or item['reason'] not in SELECTION_REASONS
                   or any(item.get(key) is not None and (not isinstance(item[key], str)
                          or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+08:00', item[key]))
                          for key in ('reservation_start', 'reservation_end'))
                   for item in selection['activities'])):
        print('activity_details=unknown')
        return
    print('selection_updated_at=' + datetime.fromtimestamp(selection['updated_at'], SHANGHAI).isoformat(timespec='seconds'))
    details = [{key: item.get(key) for key in ('title', 'reason', 'reservation_start', 'reservation_end')}
               for item in selection['activities']]
    print('activity_details=' + json.dumps(details, ensure_ascii=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Playwright SEU lecture goal: 8 attended and 3 required categories")
    parser.add_argument('--headless', action='store_true', help='run without a browser window (default: headed)')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='login and read both lists without reservations or mail')
    mode.add_argument('--status', action='store_true', help='show local status without starting a browser')
    mode.add_argument('--test-mail', action='store_true', help='send one test email without school login')
    mode.add_argument('--new-task', action='store_true', help='recheck an already completed goal')
    args = parser.parse_args(argv)
    def stop(signum, frame):
        raise KeyboardInterrupt
    previous = signal.signal(signal.SIGTERM, stop)
    try:
        config = load_config(require_credentials=not (args.status or args.test_mail))
        config['headless'] = args.headless
        if args.status:
            show_status(config['state_dir'])
            return 0
        print('SEU Lecture Reserve Playwright | by MuZiJin701\n'
              'https://github.com/MuZiJin701/SEU_Lecture_Reserve', flush=True)
        if args.test_mail:
            if not Mailer.configured(config['mail']):
                print('event=mail_disabled', flush=True)
                return 1
            try:
                mailer = Mailer(config['mail'])
            except ValueError:
                print('event=mail_configuration_invalid', flush=True)
                return 1
            try:
                mailer('test_notification')
            except Exception as exc:
                print('event=notification_failed reason=' + mail_failure_reason(exc), flush=True)
                return 1
            print('event=test_mail_accepted', flush=True)
            return 0
        settings = Settings(state_dir=config['state_dir'], titles=tuple(config['preferred_lectures']),
            categories=tuple(config['required_categories']), campuses=tuple(config['preferred_campus']),
            online=config['enable_online'], offline=config['enable_offline'],
            scan_interval=config['timeout_settings']['scan_interval'])
        environ = {**config['mail'], 'SEU_CARD_NUMBER': config['card_number']}
        with sync_playwright() as playwright:
            return run(settings, client=BrowserClient(playwright, config), environ=environ,
                       check_only=args.check, new_task=args.new_task)
    except (KeyboardInterrupt, EOFError):
        return 130
    except (ValueError, OSError, TypeError, AttributeError):
        print('event=configuration_or_state_invalid', flush=True)
        return 1
    except Exception:
        print('event=browser_runtime_failed', flush=True)
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == '__main__':
    raise SystemExit(main())
