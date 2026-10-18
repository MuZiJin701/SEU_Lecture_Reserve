import io
import json
import ssl
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import main
from app import Settings, run
from mail import Mailer
from test_app import School, lecture, stop


class MailCliTests(unittest.TestCase):
    def test_browser_mode_is_selected_only_by_cli_for_both_entrypoints(self):
        import captcha_ocr
        for module in (main, captcha_ocr):
            for platform in ('win32', 'linux', 'darwin'):
                for argv, expected in (([], False), (['--headless'], True)):
                    with self.subTest(entry=module.__name__, platform=platform, argv=argv), TemporaryDirectory() as directory:
                        config = {'state_dir': Path(directory), 'mail': {}, 'preferred_lectures': [],
                            'required_categories': [], 'preferred_campus': [], 'enable_online': True,
                            'enable_offline': True, 'timeout_settings': {'scan_interval': 10},
                            'card_number': 'test-card', 'headless': not expected}
                        with patch('sys.platform', platform), patch.dict('os.environ', {'SEU_HEADLESS': str(not expected)}), patch.object(module, 'load_config', return_value=config), patch.object(module, 'sync_playwright'), redirect_stdout(io.StringIO()):
                            if module is main:
                                with patch('main.BrowserClient') as browser, patch('main.run', return_value=0):
                                    self.assertEqual(module.main(argv), 0)
                                    self.assertIs(browser.call_args.args[1]['headless'], expected)
                            else:
                                with patch('captcha_ocr.logged_in_page') as opened, patch('captcha_ocr.collect_captchas'):
                                    module.main(argv)
                                    self.assertIs(opened.call_args.args[1]['headless'], expected)

    def test_gmail_defaults_use_tls_and_event_only_message(self):
        with patch('mail.smtplib.SMTP_SSL') as smtp:
            mailer=Mailer({'SMTP_USERNAME':'sender@gmail.com','SMTP_PASSWORD':'PRIVATE'})
            mailer('reservation_succeeded')
        args=smtp.call_args
        self.assertEqual(args.args,('smtp.gmail.com',465))
        self.assertEqual(args.kwargs['context'].verify_mode,ssl.CERT_REQUIRED)
        self.assertTrue(args.kwargs['context'].check_hostname)
        message=smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
        self.assertEqual(message['To'],'sender@gmail.com')
        self.assertIn('reservation_succeeded',message.get_content())
        self.assertNotIn('PRIVATE',str(message))

    def test_disabled_mail_books_without_opening_smtp(self):
        with TemporaryDirectory() as directory, patch('mail.smtplib.SMTP_SSL') as smtp, redirect_stdout(io.StringIO()):
            school=School();school.rows=[lecture()]
            self.assertEqual(run(Settings(state_dir=Path(directory)),client=school,
                environ={'SEU_CARD_NUMBER':'test-card','SMTP_PORT':'465'},
                recognize=lambda _:'1234',sleep=stop),130)
            self.assertEqual(school.submitted,['one'])
            smtp.assert_not_called()

    def test_custom_recipient_receives_readable_report_through_own_sender(self):
        with patch('mail.smtplib.SMTP_SSL') as smtp:
            Mailer({'SMTP_HOST':'smtp.example.org', 'SMTP_USERNAME':'sender@example.org',
                    'SMTP_PASSWORD':'PRIVATE', 'MAIL_TO':'recipient@example.net'})(
                        'daily_report', '已选听：4 / 8\n待参加：1')
        connection = smtp.return_value.__enter__.return_value
        connection.login.assert_called_once_with('sender@example.org', 'PRIVATE')
        message = connection.send_message.call_args.args[0]
        self.assertEqual(message['From'], 'sender@example.org')
        self.assertEqual(message['To'], 'recipient@example.net')
        self.assertIn('每日进度汇报', message['Subject'])
        self.assertIn('已选听：4 / 8', message.get_content())
        self.assertIn('北京时间', message.get_content())
        self.assertNotIn('PRIVATE', str(message))

    def test_invalid_mail_stops_before_school_login(self):
        with TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            school=School()
            result=run(Settings(state_dir=Path(directory)),client=school,
                environ={'SEU_CARD_NUMBER':'test-card','SMTP_USERNAME':'someone@example.org'})
            self.assertEqual(result,1)
            self.assertEqual(school.authentications,0)

    def test_mail_and_status_do_not_start_browser_or_require_school_credentials(self):
        with TemporaryDirectory() as directory:
            config={'state_dir':Path(directory),'mail':{'SMTP_USERNAME':'sender@gmail.com','SMTP_PASSWORD':'PRIVATE'}}
            with patch('main.load_config',return_value=config) as load, patch('main.sync_playwright') as runtime, patch('main.Mailer') as mailer, redirect_stdout(io.StringIO()):
                self.assertEqual(main.main(['--test-mail']),0)
                load.assert_called_once_with(require_credentials=False)
                mailer.return_value.assert_called_once_with('test_notification')
                runtime.assert_not_called()
            config['mail']={}
            with patch('main.load_config',return_value=config), patch('main.sync_playwright') as runtime, redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main.main(['--status']),0)
                self.assertIn('status=not_started',output.getvalue())
                runtime.assert_not_called()

    def test_test_mail_failure_is_redacted_and_does_not_create_state(self):
        with TemporaryDirectory() as directory:
            config={'state_dir':Path(directory),'mail':{'SMTP_USERNAME':'sender@gmail.com','SMTP_PASSWORD':'PRIVATE'}}
            with patch('main.load_config',return_value=config), patch('main.sync_playwright') as runtime, patch('main.Mailer',return_value=MagicMock(side_effect=OSError('PRIVATE'))), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main.main(['--test-mail']),1)
                self.assertIn('notification_failed',output.getvalue())
                self.assertNotIn('PRIVATE',output.getvalue())
                self.assertFalse((Path(directory)/'task.json').exists())
                runtime.assert_not_called()

    def test_status_shows_private_selection_and_retained_mail_history(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)
            school = School()
            school.rows = [lecture(YYZT='不可预约', availability_reason='reservation_not_started',
                                   YYKSSJ='2030-01-01 19:00:00', YYJSSJ='2030-01-02 12:00:00')]
            with redirect_stdout(io.StringIO()):
                run(Settings(state_dir=path), client=school, environ={'SEU_CARD_NUMBER': 'test-card'},
                    sleep=stop, clock=lambda: 100)
            saved = json.loads((path / 'task.json').read_text())
            saved['health'].update(last_mail_at=90, last_mail_status='accepted', mail_status='accepted')
            saved['selection']['activities'][0]['extra'] = 'PRIVATE'
            (path / 'task.json').write_text(json.dumps(saved))
            with redirect_stdout(io.StringIO()) as output:
                main.show_status(path)
            self.assertIn('process_running=false', output.getvalue())
            self.assertIn('last_mail_status=accepted', output.getvalue())
            self.assertNotIn('last_mail_at=never', output.getvalue())
            self.assertIn('reservation_not_started', output.getvalue())
            self.assertIn('2030-01-01T19:00:00+08:00', output.getvalue())
            self.assertNotIn('PRIVATE', output.getvalue())
            saved['selection']['activities'][0]['reason'] = ['PRIVATE']
            (path / 'task.json').write_text(json.dumps(saved))
            with redirect_stdout(io.StringIO()) as output:
                main.show_status(path)
            self.assertIn('activity_details=unknown', output.getvalue())
            self.assertNotIn('PRIVATE', output.getvalue())


if __name__=='__main__':
    unittest.main()
