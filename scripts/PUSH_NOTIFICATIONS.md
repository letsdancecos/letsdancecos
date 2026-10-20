# Push setup status

Receiving SDK installed; automated announcement sending is not configured yet.

OneSignal app: 4d59ba22-2de8-4714-9e23-63b84de1a58c
Origin: https://letsdancecos.github.io
Select Custom Code in Settings > Push & In-App > Web. The code sets the worker
path letsdancecos/app/push/OneSignalSDKWorker.js and scope /letsdancecos/app/push/.
This separate scope preserves the existing PWA worker. No automatic permission
prompt or welcome notification is configured. Events contains opt-in/out controls.

Next: verify a phone subscription and deliver a test notification to that device.
Configure a private GitHub Actions secret for sending; never commit the REST API key
or put it in chat/client code. Implement stable post-ID deduplication and initialize
the ledger from current posts so existing announcements are not sent as new alerts.
Only send after the announcement data has deployed. Updates/deletions must not resend.

Docs: https://documentation.onesignal.com/docs/en/web-push-custom-code-setup
https://documentation.onesignal.com/docs/en/onesignal-service-worker
