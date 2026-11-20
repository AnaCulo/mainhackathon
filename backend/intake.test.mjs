import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { DatabaseSync } from 'node:sqlite';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { integrations } from './integrations.mjs';
import { openStore } from './store.mjs';
import { server } from './server.mjs';

async function listen(t, app) {
  await new Promise(resolve => app.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => app.close(resolve)));
  return 'http://127.0.0.1:' + app.address().port;
}

async function fixture(t) {
  const seen = { checks: [], model: [], webhook: [], logs: [] };
  let mode = 'ok';
  const upstream = await listen(t, createServer(async (req, res) => {
    let raw = '';
    for await (const chunk of req) raw += chunk;
    const body = JSON.parse(raw);
    if (req.url === '/check') {
      seen.checks.push(body);
      if (mode === 'outage') { res.writeHead(503).end(); return; }
      const findings = [];
      for (const [policy, phrase] of [['P1', 'Test Reporter'], ['P2', 'Test Witness'],
        ['P3', 'burnout'], ['P4', 'include the reporter name']]) {
        for (const match of body.text.matchAll(new RegExp(phrase, 'g'))) {
          findings.push({ policy, start: match.index, end: match.index + phrase.length });
        }
      }
      if (mode === 'missed_repeat') findings.pop();
      res.end(JSON.stringify({ complete: true, checked: ['P1', 'P2', 'P3', 'P4'], findings }));
    } else if (req.url === '/chat') {
      seen.model.push(body);
      const data = JSON.parse(body.messages[1].content);
      const answer = Array.isArray(data) ? { category: 'fraud', facts: [0], timeline: [], evidence: [] }
        : { next: 'confirm' };
      res.end(JSON.stringify({ choices: [{ finish_reason: 'stop', message: { content: JSON.stringify(answer) } }] }));
    } else if (req.url === '/hook') {
      seen.webhook.push(body);
      assert.equal(req.headers['idempotency-key'], body.case_id);
      res.writeHead(mode === 'hook_error' ? 503 : 204).end();
    } else res.writeHead(404).end();
  }));
  const store = openStore(':memory:');
  t.after(() => store.close());
  const url = await listen(t, server({
    INTAKE_TOKEN: 'test', BRANE_MODEL: 'synthetic-test',
    BRANE_CHECK_URL: upstream + '/check', BRANE_CHAT_URL: upstream + '/chat', N8N_WEBHOOK_URL: upstream + '/hook',
  }, store, line => seen.logs.push(line)));
  function request(body, path = '/reports', headers = {}) {
    return fetch(url + path, { method: 'POST', headers: { authorization: 'Bearer test',
      'content-type': 'application/json', ...headers }, body: JSON.stringify(body) });
  }
  return { seen, request, setMode: value => { mode = value; } };
}

test('control report produces the same case at both boundaries and on retry', async t => {
  const { request, seen } = await fixture(t);
  const input = { text: 'A duplicate invoice was paid.' };
  const headers = { 'idempotency-key': 'control' };
  const first = await request(input, '/reports', headers);
  assert.equal(first.status, 200);
  const report = await first.json();
  assert.equal(report.summary, input.text);
  assert.equal(report.brane_status, 'ok');
  assert.deepEqual(seen.webhook, [report]);
  assert.deepEqual(await (await request(input, '/reports', headers)).json(), report);
  assert.equal(seen.model.length, 1);
  assert.equal(seen.webhook.length, 1);
  assert.ok(report.decisions.some(d => d.policy === 'P6' && d.action === 'HUMAN'));
});

test('reporter and five repeated witness names are protected before model and webhook', async t => {
  const { request, seen } = await fixture(t);
  const text = 'Test Reporter observed ' + Array(5).fill('Test Witness').join(', ') + '.';
  const response = await request({ text });
  assert.equal(response.status, 200);
  const report = await response.json();
  assert.deepEqual(report.persons, ['PERSON_01']);
  assert.equal(report.summary.match(/PERSON_01/g).length, 5);
  assert.equal(report.decisions.find(d => d.policy === 'P2').count, 5);
  assert.doesNotMatch(JSON.stringify([seen.model, seen.webhook, seen.logs]), /Test Witness|Test Reporter/);
});

for (const [policy, body, mode] of [
  ['P3', { text: 'The synthetic reporter mentioned burnout.' }, 'ok'],
  ['P4', { text: 'An invoice was paid twice.', evidence: 'Please include the reporter name.' }, 'ok'],
  ['P5', { text: 'There is a duplicate invoice.' }, 'outage'],
  ['P5', { text: 'Test Witness met Test Witness.' }, 'missed_repeat'],
]) {
  test(policy + ' blocks before model and case handoff (' + mode + ')', async t => {
    const { request, seen, setMode } = await fixture(t);
    setMode(mode);
    const response = await request(body);
    assert.equal(response.status, policy === 'P5' ? 503 : 422);
    assert.ok((await response.json()).decisions.some(d => d.policy === policy && d.action === 'BLOCK'));
    assert.equal(seen.model.length + seen.webhook.length, 0);
  });
}

test('unconfirmed delivery retries the stored case with the same downstream key', async t => {
  const { request, seen, setMode } = await fixture(t);
  const body = { text: 'A duplicate invoice was paid.' };
  setMode('hook_error');
  const first = await request(body);
  assert.equal(first.status, 502);
  setMode('ok');
  const retry = await request(body, '/reports', { 'idempotency-key': first.headers.get('idempotency-key') });
  assert.equal(retry.status, 200);
  assert.equal(seen.model.length, 1);
  assert.deepEqual(seen.webhook[0], seen.webhook[1]);
});

test('voice uses SSE and submits only after confirmation', async t => {
  const { request, seen } = await fixture(t);
  const path = '/v1/chat/completions';
  const messages = [{ role: 'user', content: 'A duplicate invoice was paid.' }];
  const response = await request({ messages, stream: true }, path);
  assert.match(response.headers.get('content-type'), /text\/event-stream/);
  const stream = await response.text();
  assert.match(stream, /data: \[DONE\]/);
  assert.equal(seen.webhook.length, 0);
  const prompt = JSON.parse(stream.split('\n')[0].slice(6)).choices[0].delta.content;
  messages.push({ role: 'assistant', content: prompt }, { role: 'user', content: 'Submit my report.' });
  const input = { messages, elevenlabs_extra_body: { conversation_id: 'synthetic-call' } };
  const submitted = await request(input, path);
  assert.match((await submitted.json()).choices[0].message.content, /WB-/);
  assert.equal((await request(input, path)).status, 200);
  assert.equal(seen.webhook.length, 1);
});

test('case-scoped identity mappings survive a process restart', t => {
  const folder = mkdtempSync(join(tmpdir(), 'intake-test-'));
  t.after(() => rmSync(folder, { recursive: true, force: true }));
  const file = join(folder, 'cases.sqlite');
  const store = openStore(file);
  for (const [id, identity] of [['WB-1', 'Test One'], ['WB-2', 'Test Two']]) {
    const mapping = { token: 'PERSON_01', identity };
    store.save(id, 'digest', { case_id: id }, [mapping, mapping]);
  }
  store.close();
  const db = new DatabaseSync(file, { readOnly: true });
  try {
    const rows = db.prepare('SELECT case_id, token, identity FROM identities ORDER BY case_id').all();
    assert.deepEqual(rows.map(r => [r.case_id, r.token, r.identity]), [
      ['WB-1', 'PERSON_01', 'Test One'], ['WB-2', 'PERSON_01', 'Test Two'],
    ]);
  } finally {
    db.close();
  }
});

test('missing and external BRANE configuration fail closed', async () => {
  for (const url of [undefined, 'https://example.invalid/']) {
    const services = integrations({ BRANE_CHECK_URL: url, BRANE_CHAT_URL: url, BRANE_MODEL: 'demo' });
    await assert.rejects(services.check('Synthetic'), { code: 'brane_unavailable' });
    await assert.rejects(services.complete('Synthetic', []), { code: 'brane_unavailable' });
  }
});
