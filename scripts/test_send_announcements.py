import copy
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from send_announcements import prepare, deliver, payload, wait_for_deployment, send_request

NOW = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)


def feed(identity='post-one', hours=0):
    return {'events': [{'id': identity, 'title': 'Studio news',
                        'published_at': (NOW - timedelta(hours=hours)).isoformat()}]}


def ledger(initialized=True):
    return {'version': 1, 'initialized': initialized, 'posts': {}}


class PushTests(unittest.TestCase):
    def test_first_run_and_disabled_runs_are_silent(self):
        for initialized, enabled in ((False, True), (False, False), (True, False)):
            state = prepare(feed(), ledger(initialized), NOW, enabled)
            self.assertTrue(state['initialized'])
            self.assertEqual(state['posts']['post-one']['status'], 'skipped')

    def test_old_post_does_not_alert(self):
        state = prepare(feed(hours=25), ledger(), NOW, True)
        self.assertEqual(state['posts']['post-one']['status'], 'skipped')

    def test_new_post_once_and_edits_do_not_resend(self):
        data = feed()
        state = prepare(data, ledger(), NOW, True)
        sent = []
        def sender(body):
            sent.append(body)
            return 'accepted'
        self.assertEqual(deliver(data, state, NOW, sender, lambda s: None), 1)
        data['events'][0]['title'] = 'Edited studio news'
        state = prepare(data, state, NOW, True)
        self.assertEqual(deliver(data, state, NOW, sender, lambda s: None), 0)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]['included_segments'], ['Total Subscriptions'])
        self.assertTrue(sent[0]['isAnyWeb'])
        self.assertNotIn('Authorization', str(sent[0]))

    def test_removal_and_return_do_not_alert(self):
        state = prepare(feed(), ledger(), NOW, True)
        prepare({'events': []}, state, NOW, True)
        prepare(feed(), state, NOW, True)
        self.assertEqual(state['posts']['post-one']['status'], 'skipped')

    def test_failed_send_retains_same_key_for_retry(self):
        data = feed()
        state = prepare(data, ledger(), NOW, True)
        key = payload(data['events'][0], state['posts']['post-one'])['idempotency_key']
        with self.assertRaises(TimeoutError):
            deliver(data, state, NOW, lambda b: (_ for _ in ()).throw(TimeoutError()), lambda s: None)
        self.assertEqual(state['posts']['post-one']['status'], 'pending')
        self.assertEqual(payload(data['events'][0], state['posts']['post-one'])['idempotency_key'], key)
        # Even a crash after API acceptance but before git commit retains this UUID.
        recreated = prepare(data, ledger(), NOW, True)
        self.assertEqual(recreated['posts']['post-one']['key'], key)

    def test_partial_success_saved_before_failure(self):
        data = {'events': feed('second')['events'] + feed('first')['events']}
        state = prepare(data, ledger(), NOW, True)
        snapshots = []
        def sender(body):
            if snapshots:
                raise TimeoutError()
            return 'accepted'
        with self.assertRaises(TimeoutError):
            deliver(data, state, NOW, sender, lambda s: snapshots.append(copy.deepcopy(s)))
        self.assertEqual(snapshots[0]['posts']['first']['status'], 'accepted')
        self.assertEqual(snapshots[0]['posts']['second']['status'], 'pending')

    def test_expiry_prevents_replay_outside_idempotency_window(self):
        data = feed()
        state = prepare(data, ledger(), NOW, True)
        deliver(data, state, NOW + timedelta(days=31),
                lambda b: self.fail('Expired alert sent'), lambda s: None)
        self.assertEqual(state['posts']['post-one']['status'], 'skipped')

    def test_empty_audience_is_terminal(self):
        data = feed()
        state = prepare(data, ledger(), NOW, True)
        deliver(data, state, NOW, lambda b: 'no-recipients', lambda s: None)
        self.assertEqual(deliver(data, state, NOW, lambda b: self.fail('Replayed'), lambda s: None), 0)

    def test_deployment_must_match(self):
        import json
        calls = []
        with self.assertRaises(RuntimeError):
            wait_for_deployment(feed(), lambda url: b'{"events": []}', calls.append, attempts=2)
        self.assertEqual(calls, [10])
        wait_for_deployment(feed(), lambda url: json.dumps(feed()).encode(), attempts=1)

    def test_sender_contract_and_no_secret_in_payload(self):
        import json
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'{"id":"4d59ba22-2de8-4714-9e23-63b84de1a58c"}'
        with patch('send_announcements.urllib.request.build_opener') as opener:
            opener.return_value.open.return_value = response
            body = payload(feed()['events'][0], {'key': 'test-key'})
            self.assertEqual(send_request(body, 'private-test-value'), 'accepted')
            req = opener.return_value.open.call_args.args[0]
            self.assertEqual(req.get_header('Authorization'), 'Key private-test-value')
            self.assertNotIn('private-test-value', req.data.decode())
            self.assertEqual(json.loads(req.data)['idempotency_key'], 'test-key')


if __name__ == '__main__':
    unittest.main()
