const ENDPOINT = 'https://api.github.com/repos/letsdancecos/letsdancecos/actions/workflows/announcements.yml/dispatches';
const MAX_BODY = 4096;
const reply = (status, error, details = {}) => Response.json(error ? {error, ...details} : {accepted: true}, {
  status, headers: {'Cache-Control': 'no-store', ...(status === 429 ? {'Retry-After': '60'} : {})},
});

async function equalSecret(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') return false;
  const hash = async value => new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value)));
  const [x, y] = await Promise.all([hash(a), hash(b)]);
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}

async function readBody(request) {
  const reader = request.body?.getReader();
  if (!reader) throw new Error('empty');
  let length = 0;
  const chunks = [];
  for (;;) {
    const {done, value} = await reader.read();
    if (done) break;
    length += value.length;
    if (length > MAX_BODY) { await reader.cancel(); throw new Error('large'); }
    chunks.push(value);
  }
  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  return JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(bytes));
}

export function validPostUrl(value) {
  if (typeof value !== 'string' || value.length > 1000) return false;
  try {
    const url = new URL(value);
    return url.origin === 'https://www.letsdancecos.com' && !url.username && !url.password &&
      !url.search && !url.hash && /^\/post\/[a-zA-Z0-9%_-]+$/.test(url.pathname) && url.href === value;
  } catch { return false; }
}

export async function handle(request, env, dispatch = fetch) {
  const url = new URL(request.url);
  if (url.pathname !== '/wix-published' || url.search) return reply(404, 'Not found');
  if (request.method !== 'POST') return reply(405, 'POST required');
  if (!/^[a-f0-9]{64}$/.test(env.WIX_WEBHOOK_SECRET || '') || !env.GITHUB_DISPATCH_TOKEN || !env.DISPATCH_LIMITER)
    return reply(503, 'Relay not configured');
  if (request.headers.get('content-type')?.split(';')[0].trim() !== 'application/json') return reply(415, 'JSON required');
  let body;
  try { body = await readBody(request); } catch { return reply(400, 'Invalid request'); }
  if (!body || typeof body !== 'object' || Array.isArray(body) || !await equalSecret(body.secret, env.WIX_WEBHOOK_SECRET))
    return reply(401, 'Unauthorized');
  if (!validPostUrl(body.post_url)) return reply(400, 'Invalid post URL');
  // Only fixed labels and HTTP status numbers leave this relay on failure.
  // Never return exception messages, upstream response bodies, headers or keys.
  try {
    if (!(await env.DISPATCH_LIMITER.limit({key: 'studio-announcements'})).success) return reply(429, 'Try later');
  } catch { return reply(502, 'Dispatch failed', {stage: 'rate_limiter'}); }
  try {
    const response = await dispatch(ENDPOINT, {
      // Workers rejects redirect:'error' before sending. Manual also prevents
      // following redirects with the GitHub credential; 3xx is a failed dispatch.
      method: 'POST', redirect: 'manual', signal: AbortSignal.timeout(10000),
      headers: {'Authorization': `Bearer ${env.GITHUB_DISPATCH_TOKEN}`, 'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2026-03-10', 'User-Agent': 'LetsDance-Wix-Relay', 'Content-Type': 'application/json'},
      body: JSON.stringify({ref: 'main', inputs: {wix_post_url: body.post_url}}),
    });
    // Never return upstream bodies, credentials or the incoming payload.
    if (response.status === 204 || response.status === 200) return reply(202);
    const reasons = {400: 'request_rejected', 401: 'credential_rejected', 403: 'permission_or_rate_limit',
      404: 'repository_or_workflow_not_accessible', 422: 'workflow_ref_or_inputs_rejected', 429: 'github_rate_limit'};
    return reply(502, 'Dispatch failed', {stage: 'github', upstream_status: response.status,
      reason: reasons[response.status] || 'unexpected_github_status'});
  } catch { return reply(502, 'Dispatch failed', {stage: 'github_network_or_request'}); }
}

export default {fetch(request, env) { return handle(request, env); }};
