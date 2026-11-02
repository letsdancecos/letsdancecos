import {test} from 'node:test';
import assert from 'node:assert/strict';
import {handle, validPostUrl} from './worker.mjs';

const secret = 'a'.repeat(64);
const post_url = 'https://www.letsdancecos.com/post/test-announcement';
const env = () => ({WIX_WEBHOOK_SECRET: secret, GITHUB_DISPATCH_TOKEN: 'private-test-token',
  DISPATCH_LIMITER: {limit: async () => ({success: true})}});
const request = (body = {secret, post_url}, options = {}) => new Request('https://relay.example/wix-published', {
  method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body), ...options,
});

test('authenticated publish dispatches only fixed workflow/main with URL input', async () => {
  let calls = 0;
  const result = await handle(request({secret, post_url, ref: 'evil', repository: 'evil/evil'}), env(), async (url, options) => {
    calls++;
    assert.equal(url, 'https://api.github.com/repos/letsdancecos/letsdancecos/actions/workflows/announcements.yml/dispatches');
    assert.deepEqual(JSON.parse(options.body), {ref: 'main', inputs: {wix_post_url: post_url}});
    assert.equal(options.redirect, 'error');
    assert.equal(options.headers.Authorization, 'Bearer private-test-token');
    return new Response(null, {status: 204});
  });
  assert.equal(calls, 1);
  assert.equal(result.status, 202);
  assert.deepEqual(await result.json(), {accepted: true});
});

test('invalid callers never contact GitHub', async () => {
  const cases = [request({post_url}), request({secret: 'wrong', post_url}), request(null),
    request({secret, post_url: 'https://evil.example/post/test'}), request({secret, post_url, padding: 'x'.repeat(5000)}),
    request({}, {body: '{bad'}), request({}, {headers: {'Content-Type': 'text/plain'}}),
    new Request('https://relay.example/wix-published'),
    new Request('https://relay.example/wix-published?secret=anything', {method: 'POST'})];
  for (const req of cases) {
    const res = await handle(req, env(), () => { assert.fail('Unexpected dispatch'); });
    assert.ok(res.status >= 400);
  }
});

test('missing secrets and rate limit fail closed', async () => {
  assert.equal((await handle(request(), {})).status, 503);
  const limited = env();
  limited.DISPATCH_LIMITER.limit = async () => ({success: false});
  assert.equal((await handle(request(), limited, () => assert.fail())).status, 429);
});

test('upstream failure and network failure expose no secret or response body', async () => {
  for (const upstream of [async () => new Response('sensitive upstream text', {status: 403}), async () => {throw new Error(secret); }]) {
    const res = await handle(request(), env(), upstream);
    assert.equal(res.status, 502);
    assert.equal(await res.text(), '{"error":"Dispatch failed"}');
  }
});

test('URL validation rejects credentials, queries, fragments, redirects and other hosts', () => {
  assert.ok(validPostUrl(post_url));
  for (const value of ['http://www.letsdancecos.com/post/test', 'https://user@www.letsdancecos.com/post/test',
    post_url + '?x=1', post_url + '#a', 'https://www.letsdancecos.com/post/../admin',
    'https://www.letsdancecos.com.evil/post/test']) assert.equal(validPostUrl(value), false);
});
