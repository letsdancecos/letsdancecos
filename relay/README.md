# Immediate Wix announcement trigger

Status: implementation prepared; not deployed, credentialed, connected in Wix, or end-to-end tested.

Wix blog publish → HTTPS POST with a relay secret in the JSON body → Cloudflare Worker
→ authenticated GitHub workflow_dispatch on main → existing RSS import, Pages deployment and OneSignal sender.

The scheduled :17/:47 backup, manual runs, Studio Announcements category selection,
durable alert ledger and OneSignal priority 10 remain unchanged. The webhook is only a
wakeup signal; it cannot supply announcement text, commands, a GitHub repository or a branch.
The workflow waits up to about two minutes (plus fetch time) for the exact published URL
to appear in public RSS, then uses the existing importer. If Wix is slower, the run fails
and the scheduled backup can recover. GitHub queueing and phone delivery still add delay.
All blog posts wake the importer because the site's publish trigger has no category filter;
only posts qualifying under the existing importer can enter the app or send alerts.

## Private setup and approval

1. Review and merge this change before connecting Wix. Approval is required before changing
   the live workflow or activating Wix. No site design or Velo changes are needed.
2. Use a Cloudflare Workers **Free** account, without upgrading or enabling paid services.
   Its documented 100,000 requests/day allowance is ample for ordinary studio publishing.
   Confirm the account is on Free before deployment. No custom domain, KV or database is needed.
3. In GitHub create an expiring **fine-grained** personal access token owned by letsdancecos,
   limited to **letsdancecos/letsdancecos**, with **Actions: read and write**, plus required
   metadata read. Do not grant Contents write. This is a repo-level permission, not a
   per-workflow permission; the relay itself fixes the only workflow it will dispatch.
   Never paste the token in chat, a URL, Wix, a commit or public app code.
4. From this folder, using the Wrangler CLI (version 4.36 or newer):

   ```text
   npx wrangler login
   npx wrangler secret put GITHUB_DISPATCH_TOKEN
   npx wrangler secret put WIX_WEBHOOK_SECRET
   npx wrangler deploy
   ```

   The first secret is the fine-grained GitHub token. The second is a fresh random
   32-byte secret encoded as **64 lowercase hexadecimal characters**, generated privately
   with a password manager or cryptographic random generator. Keep that same value for Wix.
   Secret commands prompt privately. Do not pass values as command-line arguments.
   If first-time secret setup asks to create the Worker, accept only on the Free account.
   Use the deployment's actual workers.dev URL below. Do not change the Wix domain/DNS.
   This chat has not deployed the Worker or verified its Cloudflare runtime.

## Wix actions after relay deployment

Target site: Let's Dance Studios, f4fc174d-acd3-4e57-ae67-9aebc61add05.
[Open Automations](https://manage.wix.com/dashboard/f4fc174d-acd3-4e57-ae67-9aebc61add05/triggers).
The existing inactive “Notify when a blog post is published” automation is unrelated;
leave it unchanged and create a separate automation.

1. Create Automation → Start from Scratch. Name: **Update studio app when a blog post is published**.
2. Trigger: Wix Blog → **New blog post published**. Do not add a delay.
3. Action: **Send HTTP request**; method **POST**.
4. URL: the actual deployed relay origin followed by `/wix-published`. No secret in the URL.
5. Turn **Nest request body under data** OFF. Choose fields, and add:
   - `secret`: the private 64-character relay secret, as a literal value.
   - `post_url`: the trigger's **Post URL** dynamic value (`url`).
6. Preview request body: the top level must contain `secret` and `post_url` only;
   no `data` wrapper. Do not use “All automation data.” No member/contact data is needed.
7. Apply, save as a draft, and review in the builder before activation. Check **Manage Quotas**
   on Automations; this site's billing/allowance for the HTTP action has not been verified.
   Do not buy an upgrade without the owner's approval.
8. Activate only after approval. No whole-site republish is required by this automation flow.

Wix's current HTTP action schema has no authentication-header setting. The GitHub token
stays in Cloudflare secrets; Wix stores only the separate relay secret. Treat that field as
sensitive: site collaborators with automation access and automation request previews/history
may see it. Don't share screenshots or exports containing it. Worker observability is off;
don't enable request/body logging. The Worker does not log payloads or upstream error bodies.
Rotate the relay secret in both places if exposed, and rotate GitHub tokens before expiry.
Never put either value in public client code or synced project reference files.

## Verify after approval

- Without credentials, POST must return 401; GET 405; malformed JSON 400. No GitHub run should start.
- With permission to send a real notification, publish one **new** Studio Announcements post.
  Expect the Wix action to return 202, then a workflow_dispatch run of Sync studio announcements.
  A 202 means GitHub accepted the dispatch; it does not prove the workflow or notification succeeded.
- Check the workflow's RSS wait, importer, public app feed, Pages deployment, ledger and
  OneSignal accepted result, then confirm receipt on both phones. Don't reset the ledger
  or republish an old post to simulate a new one.
- Replay the same publish request: extra runs may occur, but the existing durable ledger
  and OneSignal idempotency key should prevent duplicate alerts. This relay does not claim
  exactly-once dispatch or delivery. Its rate limit is 5/minute per Cloudflare location,
  best effort, not a global quota. A 429 means retry later; the schedule remains backup.
- 502: inspect GitHub credential expiry, Actions permission, merged main workflow and input
  name. 503: secrets or rate-limit binding missing. Do not print tokens while diagnosing.
- To pause the immediate path, deactivate only this new Wix automation; keep the schedule
  and alert ledger intact. Revoke the dispatch token if retiring the relay.

## Validation

```text
node --test relay/worker.test.mjs
python -m unittest discover -s scripts -p 'test_*.py'
```

Tests mock GitHub dispatch and exercise auth, oversized/invalid requests, fixed target,
safe upstream errors, URL restrictions, rate limiting and RSS propagation handling.
No live dispatch, Wix test automation, publication or push was executed during development.

Sources:
- https://support.wix.com/en/article/the-new-automation-builder-sending-data-via-webhook
- https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event
- https://developers.cloudflare.com/workers/configuration/secrets/
- https://developers.cloudflare.com/workers/runtime-apis/bindings/rate-limit/
- https://developers.cloudflare.com/workers/platform/pricing/
