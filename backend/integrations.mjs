import { IntakeError, policies, protect, unavailable } from './protection.mjs';

function endpoint(value, localOnly) {
  const url = new URL(value);
  const local = ['127.0.0.1', '[::1]'].includes(url.hostname);
  if ((localOnly && !local) || !(url.protocol === 'https:' || (local && url.protocol === 'http:')) ||
      url.username || url.password || url.hash) throw new Error('Invalid endpoint configuration');
  return url;
}

async function post(url, body, token, extraHeaders = {}) {
  const headers = { 'content-type': 'application/json', ...extraHeaders };
  if (token) headers.authorization = 'Bearer ' + token;
  const response = await fetch(url, {
    method: 'POST', headers, body: JSON.stringify(body), redirect: 'error',
    signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) {
    await response.body?.cancel();
    throw new Error('Upstream request failed');
  }
  return response;
}

export function integrations(env) {
  return {
    async check(text) {
      try {
        const response = await post(endpoint(env.BRANE_CHECK_URL, true), { text, policies }, env.BRANE_TOKEN);
        return protect(text, await response.json());
      } catch (error) {
        if (error instanceof IntakeError) throw error;
        throw unavailable();
      }
    },
    async complete(instruction, data) {
      try {
        if (!env.BRANE_MODEL) throw unavailable();
        const response = await post(endpoint(env.BRANE_CHAT_URL, true), {
          model: env.BRANE_MODEL, stream: false,
          messages: [{ role: 'system', content: instruction }, { role: 'user', content: JSON.stringify(data) }],
        }, env.BRANE_TOKEN);
        const result = await response.json();
        const choice = result.choices?.[0];
        if (choice?.finish_reason !== 'stop') throw unavailable();
        return JSON.parse(choice.message.content);
      } catch {
        throw unavailable();
      }
    },
    async deliver(report) {
      try {
        const response = await post(endpoint(env.N8N_WEBHOOK_URL, false), report, env.N8N_TOKEN,
          { 'idempotency-key': report.case_id });
        await response.body?.cancel();
      } catch {
        throw new IntakeError(502, 'handoff_unconfirmed');
      }
    },
  };
}
