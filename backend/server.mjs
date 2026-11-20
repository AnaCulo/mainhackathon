import { createServer } from 'node:http';
import { createHash, randomUUID, timingSafeEqual } from 'node:crypto';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { intake } from './intake.mjs';
import { integrations } from './integrations.mjs';
import { openStore } from './store.mjs';
import { IntakeError } from './protection.mjs';

const digest = value => createHash('sha256').update(value).digest();

async function readBody(req) {
  if (req.headers['content-type']?.split(';')[0].trim() !== 'application/json') {
    throw new IntakeError(415, 'expected_json');
  }
  const chunks = [];
  let bytes = 0;
  for await (const chunk of req) {
    bytes += chunk.length;
    if (bytes > 65536) throw new IntakeError(413, 'body_too_large');
    chunks.push(chunk);
  }
  try {
    const value = JSON.parse(Buffer.concat(chunks).toString('utf8'));
    if (!value || Array.isArray(value) || typeof value !== 'object') throw new Error();
    return value;
  } catch {
    throw new IntakeError(400, 'invalid_json');
  }
}

function reply(res, status, body) {
  res.writeHead(status, { 'content-type': 'application/json' });
  res.end(JSON.stringify(body));
}

function completion(res, content, stream, model) {
  const base = { id: 'chatcmpl-' + randomUUID(), created: Math.floor(Date.now() / 1000), model };
  if (!stream) {
    return reply(res, 200, { ...base, object: 'chat.completion',
      choices: [{ index: 0, message: { role: 'assistant', content }, finish_reason: 'stop' }] });
  }
  res.writeHead(200, { 'content-type': 'text/event-stream' });
  for (const [delta, finish_reason] of [[{ role: 'assistant', content }, null], [{}, 'stop']]) {
    const chunk = { ...base, object: 'chat.completion.chunk', choices: [{ index: 0, delta, finish_reason }] };
    res.write('data: ' + JSON.stringify(chunk) + '\n\n');
  }
  res.end('data: [DONE]\n\n');
}

export function server(env, store, log = record => console.log(JSON.stringify(record))) {
  if (!env.INTAKE_TOKEN?.trim()) throw new Error('Set INTAKE_TOKEN before starting the server.');
  const agent = intake(integrations(env), store);
  return createServer(async (req, res) => {
    const id = randomUUID();
    const decisions = [];
    const route = ['/reports', '/v1/chat/completions'].includes(req.url) ? req.url : 'unknown';
    let outcome = 'ok';
    res.setHeader('x-request-id', id);
    res.setHeader('cache-control', 'no-store');
    try {
      if (req.method !== 'POST' || route === 'unknown') throw new IntakeError(404, 'not_found');
      if (!timingSafeEqual(digest(req.headers.authorization ?? ''), digest('Bearer ' + env.INTAKE_TOKEN))) {
        throw new IntakeError(401, 'unauthorized');
      }
      const body = await readBody(req);
      if (route === '/reports') {
        if (typeof body.text !== 'string' || !body.text.trim() ||
            Object.keys(body).some(k => !['text', 'evidence'].includes(k)) ||
            ('evidence' in body && typeof body.evidence !== 'string')) throw new IntakeError(400, 'invalid_report');
        const key = req.headers['idempotency-key'] ?? id;
        if (!/^[a-zA-Z0-9_.:-]{1,128}$/.test(key)) throw new IntakeError(400, 'invalid_key');
        res.setHeader('idempotency-key', key);
        const text = body.evidence ? body.text + '\nEvidence:\n' + body.evidence : body.text;
        reply(res, 200, await agent.submit(text, 'text:' + key, decisions));
      } else {
        const content = await agent.chat(body, decisions);
        completion(res, content, body.stream === true, 'whistleblower-intake');
      }
    } catch (error) {
      const failure = error instanceof IntakeError ? error : new IntakeError(500, 'intake_failed');
      outcome = failure.code;
      decisions.push(...failure.decisions);
      reply(res, failure.status, { error: { code: outcome, message: outcome }, decisions, request_id: id });
    } finally {
      log({ request_id: id, route, status: res.statusCode, outcome, decisions });
    }
  });
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const local = process.env.LOCALAPPDATA || process.env.XDG_DATA_HOME || join(homedir(), '.local', 'share');
  process.umask(0o077);
  const store = openStore(process.env.MAPPING_DB || join(local, 'whistleblower-intake', 'cases.sqlite'));
  const port = Number(process.env.PORT || 8000);
  server(process.env, store).listen(port, '127.0.0.1', () => console.log('Intake listening on loopback port ' + port));
}
