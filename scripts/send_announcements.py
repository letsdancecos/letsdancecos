"""Durable, idempotent announcement alerts. Credentials only come from Actions secrets."""
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
import urllib.request

from sync_announcements import NoRedirect, fetch_url

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / 'app/announcements.json'
LEDGER = ROOT / 'scripts/announcement_push_state.json'
APP_ID = '4d59ba22-2de8-4714-9e23-63b84de1a58c'
APP_URL = 'https://letsdancecos.github.io/letsdancecos/app/'
LIVE_FEED = APP_URL + 'announcements.json'
MAX_AGE = timedelta(hours=24)


def instant(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError('Timestamp requires timezone')
    return parsed


def save(path, data):
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    temporary.replace(path)


def read_state(path):
    state = json.loads(path.read_text(encoding='utf-8'))
    if state.get('version') != 1 or not isinstance(state.get('posts'), dict):
        raise ValueError('Invalid push ledger; refusing to reset it')
    return state


def prepare(data, state, now, enabled):
    events = {e['id']: e for e in data['events']}
    baseline = not state['initialized']
    for identity, event in events.items():
        if identity in state['posts']:
            continue
        age = now - instant(event['published_at'])
        pending = enabled and not baseline and timedelta(0) <= age <= MAX_AGE
        state['posts'][identity] = {
            'status': 'pending' if pending else 'skipped',
            'reason': 'new' if pending else 'baseline-or-disabled-or-old',
            'first_seen': now.isoformat(),
            'key': str(uuid.uuid5(uuid.UUID(APP_ID), identity)),
        }
    # Keep tombstones permanently so deleted/re-added and edited posts never resend.
    for identity, record in state['posts'].items():
        if record['status'] != 'pending':
            continue
        if identity not in events or now - instant(record['first_seen']) > MAX_AGE:
            record['status'] = 'skipped'
            record['reason'] = 'removed-or-expired'
    state['initialized'] = True
    return state


def payload(event, record):
    return {
        'app_id': APP_ID,
        'included_segments': ['Total Subscriptions'],
        'isAnyWeb': True,
        'headings': {'en': "Let's Dance Studios"},
        'contents': {'en': event['title']},
        'url': APP_URL,
        'name': 'Studio announcement ' + event['id'][:16],
        'idempotency_key': record['key'],
        'ttl': 86400,
    }


def send_request(body, api_key):
    request = urllib.request.Request(
        'https://api.onesignal.com/notifications?c=push',
        data=json.dumps(body).encode(),
        headers={'Authorization': 'Key ' + api_key, 'Content-Type': 'application/json'},
        method='POST',
    )
    # Never follow a redirect carrying the private credential.
    with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
        result = json.loads(response.read(100_000))
    if not isinstance(result, dict) or 'id' not in result:
        raise ValueError('Unexpected OneSignal result')
    if result['id']:
        uuid.UUID(result['id'])
        return 'accepted'
    if result['id'] == '':
        return 'no-recipients'
    raise ValueError('Unexpected OneSignal message ID')


def deliver(data, state, now, sender, persist):
    count = 0
    for event in reversed(data['events']):
        record = state['posts'].get(event['id'])
        if not record or record['status'] != 'pending':
            continue
        if now - instant(record['first_seen']) > MAX_AGE:
            record.update(status='skipped', reason='expired')
        else:
            # A retry after a lost response uses the exact same persisted UUID.
            result = sender(payload(event, record))
            record.update(status=result, completed_at=now.isoformat())
            count += 1
        persist(state)
    return count


def wait_for_deployment(data, fetch=fetch_url, sleep=time.sleep, attempts=18):
    for attempt in range(attempts):
        try:
            if json.loads(fetch(LIVE_FEED)) == data:
                return
        except Exception:
            pass
        if attempt < attempts - 1:
            sleep(10)
    raise RuntimeError('App announcements are not deployed yet; no alerts sent')


def main():
    mode = sys.argv[1]
    data = json.loads(FEED.read_text(encoding='utf-8'))
    state = read_state(LEDGER)
    key = os.environ.get('ONESIGNAL_REST_API_KEY', '').strip()
    now = datetime.now(timezone.utc)
    if mode == 'prepare':
        save(LEDGER, prepare(data, state, now, bool(key)))
        print('Push ledger prepared; sending enabled: ' + str(bool(key)))
    elif mode == 'send':
        if not key:
            print('Push inactive: add ONESIGNAL_REST_API_KEY to GitHub Actions secrets.')
            return
        if not any(r['status'] == 'pending' for r in state['posts'].values()):
            print('No new announcement alerts.')
            return
        wait_for_deployment(data)
        total = deliver(data, state, datetime.now(timezone.utc),
                        lambda body: send_request(body, key), lambda value: save(LEDGER, value))
        print(f'Processed {total} new announcement alerts.')
    else:
        raise ValueError('Expected prepare or send')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Avoid printing response bodies, request headers, or credentials.
        print(f'Announcement push failed ({type(exc).__name__}); pending alerts retained.', file=sys.stderr)
        sys.exit(1)
