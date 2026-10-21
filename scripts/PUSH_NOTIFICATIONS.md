# Push setup status

Receiving SDK installed and Android delivery tested. Automatic announcement sending
is implemented in the existing announcements workflow, but remains inactive until
the repository Actions secret ONESIGNAL_REST_API_KEY is set.

OneSignal app: 4d59ba22-2de8-4714-9e23-63b84de1a58c
Origin: https://letsdancecos.github.io
Select Custom Code in Settings > Push & In-App > Web. The code sets the worker
path letsdancecos/app/push/OneSignalSDKWorker.js and scope /letsdancecos/app/push/.
This separate scope preserves the existing PWA worker. No automatic permission
prompt or welcome notification is configured. Events contains opt-in/out controls.

## Activate

In OneSignal Settings > Keys & IDs, create an App API key for this app.
Store it directly in letsdancecos/letsdancecos > Settings > Secrets and variables >
Actions as ONESIGNAL_REST_API_KEY. Never paste it in chat, commit it, or add it to
client code. Do not use an Organization API key. Key creation grants sending access.
Run Sync studio announcements once to confirm the baseline, then publish a new
Studio Announcements post to test the complete chain. Do not republish the old sample.

## Behavior and recovery

The importer attaches a SHA-256 of the RSS GUID (or link fallback) to each post.
The durable scripts/announcement_push_state.json ledger is committed before sending.
Initial posts and posts seen while no secret is configured are silently baselined.
New posts published within 24 hours are queued. Edits do not resend. Removed posts
are canceled; their tombstones remain so reappearance does not resend.
The sender waits up to about 3 minutes for the public app feed to match the import.
If deployment is delayed it fails safely and the next scheduled run retries.
Each alert uses a stable OneSignal idempotency UUID, valid for 30 days. Pending alerts
expire after 24 hours, well within that window. Accepted results are saved even after
partial failure. An empty audience is terminal, not replayed to later subscribers.
Alerts target subscribed Web devices in Total Subscriptions. They use the post title,
open the app, and expire at the push provider after 24 hours.
The scheduled import runs at :17 and :47, subject to GitHub scheduling delays; push
delivery can also be delayed. This is not an emergency notification system.

To pause automatic sending, remove the Actions secret. Keep the ledger intact.
Never reset the ledger or manually replay a sent post. For send failures inspect the
Actions status and OneSignal message history; credentials and API response bodies
are intentionally excluded from script output. Retry the workflow after fixing the
cause; it retains the same idempotency key. To rotate, replace the private secret.

Validation: python3 -m unittest discover -s scripts -p 'test_*.py'

Docs: https://documentation.onesignal.com/docs/en/web-push-custom-code-setup
https://documentation.onesignal.com/docs/en/onesignal-service-worker
https://documentation.onesignal.com/reference/push-notification
