import {createServer} from 'node:http';
import {createHmac,randomBytes,timingSafeEqual} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {existsSync,mkdirSync,realpathSync} from 'node:fs';
import {join} from 'node:path';
import {homedir} from 'node:os';
import {Register} from './register.mjs';
import {digest,reject} from './contract.mjs';

const eq=(a,b)=>timingSafeEqual(Buffer.from(digest(String(a))),Buffer.from(digest(String(b))));
// ISO timestamps as 2026-11-21 00:32 UTC for people; values stay ISO in the register.
const when=s=>String(s??'').replace(/^(\d{4}-\d\d-\d\d)T(\d\d:\d\d)(:\d\d(\.\d+)?)?Z$/,'$1 $2 UTC');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
// Same design tokens as the intake site (backend/app/static/index.html), light and dark.
const STYLE=`:root{--bg:#eef1f4;--surface:#fff;--surface-2:#f6f8fa;--ink:#121820;--muted:#4f5968;--line:#dde2e8;--line-strong:#c3cad4;
--brand-1:#0c3b33;--brand-2:#17594c;--brand-3:#22796a;--on-brand-muted:#d3ebe5;--accent:#17594c;--accent-hover:#10463c;--accent-ink:#fff;--accent-soft:#e2f0ec;
--ok:#156b3c;--ok-soft:#e1f3e8;--protect:#2f4fc0;--protect-soft:#e6ebfc;--held:#8a4b00;--held-soft:#fcefd9;--stop:#b42318;--stop-soft:#fdeceb;--info:#4f5968;--info-soft:#eaedf1;
--banner:#fff4dc;--banner-ink:#6b3d00;--code:#f3f5f8;--focus:#2563eb;--shadow:0 1px 2px rgba(16,24,40,.06),0 4px 14px rgba(16,24,40,.06);--radius:16px}
@media (prefers-color-scheme:dark){:root{--bg:#0b0e12;--surface:#141920;--surface-2:#19202a;--ink:#eaedf1;--muted:#b0b8c5;--line:#262e39;--line-strong:#36404d;
--brand-1:#0e3530;--brand-2:#155247;--brand-3:#1f7062;--on-brand-muted:#b9ddd4;--accent:#6fd0b8;--accent-hover:#8fdcc8;--accent-ink:#072019;--accent-soft:#15302a;
--ok:#6cd8a1;--ok-soft:#12301f;--protect:#9db1ff;--protect-soft:#1b2347;--held:#f5bb63;--held-soft:#35270e;--stop:#ff978e;--stop-soft:#3b1a18;--info:#b0b8c5;--info-soft:#222a35;
--banner:#2c2209;--banner-ink:#f5d08a;--code:#0f1318;--focus:#7aa7ff;--shadow:0 1px 2px rgba(0,0,0,.5),0 6px 18px rgba(0,0,0,.25)}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);overflow-x:hidden;font:15.5px/1.5 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;-webkit-font-smoothing:antialiased}
:focus-visible{outline:3px solid var(--focus);outline-offset:2px}a{color:var(--accent)}svg{flex:none}
.banner{background:var(--banner);color:var(--banner-ink);font-size:13px;font-weight:600;text-align:center;padding:6px 14px}.banner svg{vertical-align:-3px;margin-right:6px}
header.top{background:linear-gradient(120deg,var(--brand-1),var(--brand-2) 55%,var(--brand-3));color:#fff}
.top-inner{max-width:1040px;margin:0 auto;padding:20px 28px;display:flex;align-items:center;gap:18px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:14px;min-width:0;flex:1 1 360px}.logo{width:48px;height:48px;border-radius:14px;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.28);display:grid;place-items:center;flex:none}
.brand h1{font-size:23px;line-height:1.2;margin:0;letter-spacing:-.015em}.brand p{margin:3px 0 0;color:var(--on-brand-muted);font-size:14px}
.top-chips{display:flex;gap:8px;flex-wrap:wrap}.hchip{display:inline-flex;align-items:center;gap:7px;font-size:13px;font-weight:600;padding:6px 11px;border-radius:999px;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.25);white-space:nowrap}
main{max-width:1040px;margin:0 auto;padding:22px 28px 36px;display:grid;gap:18px}
.crumbs{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}.crumbs a{font-weight:650;text-decoration:none}
.title{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.title h2{margin:0;font-size:18px;letter-spacing:-.01em;overflow-wrap:anywhere}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);min-width:0}
.card-head{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;padding:14px 20px;border-bottom:1px solid var(--line)}
.card-head h3{margin:0;font-size:16.5px;font-weight:700;display:flex;align-items:center;gap:9px}.card-head h3 svg{color:var(--accent)}
.card-body{padding:16px 20px 18px}.card-body>:first-child{margin-top:0}.card-body>:last-child{margin-bottom:0}
.muted{color:var(--muted)}.small{font-size:13.5px}
.chip{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;font-weight:600;line-height:1.2;padding:5px 10px;border-radius:999px;background:var(--info-soft);color:var(--info);white-space:nowrap}
.chip.ok{background:var(--ok-soft);color:var(--ok)}.chip.protect{background:var(--protect-soft);color:var(--protect)}.chip.held{background:var(--held-soft);color:var(--held)}.chip.stop{background:var(--stop-soft);color:var(--stop)}.chip.accent{background:var(--accent-soft);color:var(--accent)}
.facts{margin:0;padding-left:20px}.facts li{margin:4px 0}.group{margin:14px 0 0}.group>b{display:block;font-size:12px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);margin-bottom:4px}
.clocks{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}.clock{background:var(--surface-2);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.clock b{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:6px}.clock dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:2px 12px;font-size:14px}.clock dt{color:var(--muted)}.clock dd{margin:0}
.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap}th{font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:var(--muted);font-weight:700}tr:last-child td{border-bottom:0}
.card-body:has(>.queue),.card-body:has(>.empty){padding:0}.queue{list-style:none;margin:0;padding:0}.queue li{border-bottom:1px solid var(--line)}.queue li:last-child{border-bottom:0}
.queue a.row{display:flex;align-items:center;gap:10px 14px;flex-wrap:wrap;padding:14px 20px;color:var(--ink);text-decoration:none}.queue a.row:hover{background:var(--surface-2)}
.queue code{font-size:14px;font-weight:650;overflow-wrap:anywhere}.queue .when{margin-left:auto}
.callout{border-radius:12px;padding:12px 14px;border:1px solid;border-left-width:4px;background:var(--held-soft);border-color:color-mix(in srgb,var(--held) 45%,transparent)}.callout b{color:var(--held)}
.decided{background:var(--ok-soft);border:1px solid color-mix(in srgb,var(--ok) 35%,transparent);border-radius:12px;padding:10px 14px;margin:0 0 12px}
form{display:grid;gap:14px}label{display:grid;gap:6px;font-weight:600;font-size:14.5px}
select,textarea{font:inherit;color:var(--ink);background:var(--surface);border:1px solid var(--line-strong);border-radius:10px;padding:9px 12px;width:100%}textarea{min-height:110px;resize:vertical}
label.check{display:flex;align-items:flex-start;gap:10px;font-weight:500}label.check input{width:18px;height:18px;margin:2px 0 0;accent-color:var(--accent)}
button,.btn{font:inherit;font-weight:650;background:var(--accent);color:var(--accent-ink);border:1px solid var(--accent);padding:9px 16px;border-radius:10px;cursor:pointer;min-height:42px;justify-self:start;text-decoration:none;display:inline-flex;align-items:center;gap:8px}
button:hover,.btn:hover{background:var(--accent-hover);border-color:var(--accent-hover)}
code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;overflow-wrap:anywhere}
.card-body h4{margin:4px 0 0;font-size:15px}
.empty{padding:26px 20px;text-align:center;color:var(--muted)}
@media (max-width:640px){.top-inner{padding:16px}main{padding:14px 14px 28px;gap:14px}.card-head,.card-body,.queue a.row{padding-left:14px;padding-right:14px}.brand h1{font-size:19px}.queue .when{margin-left:0;flex-basis:100%}}`;
const ICON={
  shield:'<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6l7-3z"/><path d="M9 12l2 2 4-4"/></svg>',
  warn:'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0zM12 9v4M12 17h.01"/></svg>',
  lock:'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>',
  user:'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>',
  doc:'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M8 13h8M8 17h5"/></svg>',
  clock:'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  send:'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4z"/></svg>',
  gavel:'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 11l-6 6v4h4l6-6"/><path d="M16 3l5 5-7 7-5-5z"/></svg>',
  inbox:'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5h13L22 12v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6z"/></svg>'};
const card=(icon,title,body,right='')=>`<section class="card"><div class="card-head"><h3>${ICON[icon]}${title}</h3>${right}</div><div class="card-body">${body}</div></section>`;
const chip=(kind,text)=>`<span class="chip ${kind}">${esc(text)}</span>`;
const page=(title,body,actor='')=>`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="light dark"><title>${esc(title)} · Case handler review</title><style>${STYLE}</style>
<div class="banner" role="note">${ICON.warn}Synthetic demo: every name and event on this page is made up</div>
<header class="top"><div class="top-inner"><div class="brand"><div class="logo">${ICON.shield}</div><div><h1>Case handler review</h1><p>Designated handler only. Report originals stay on this machine; the AI saw tokens only.</p></div></div>
<div class="top-chips"><span class="hchip">${ICON.lock}Local only · 127.0.0.1</span>${actor?`<span class="hchip">${ICON.user}Signed in as ${esc(actor)}</span>`:''}</div></div></header>
<main>${body}</main></html>`;
async function body(req) {
  const chunks=[];let size=0;
  for await(const chunk of req){size+=chunk.length;if(size>196608)reject(413);chunks.push(chunk);}
  return Buffer.concat(chunks).toString('utf8');
}
export function service(r,{wire,secret,password,sendTable,intakePort,reviewOnly=false}){
  const credentials=reviewOnly?[secret,password]:[wire,secret,password];
  if(credentials.some(s=>typeof s!=='string'||s.length<16) || new Set(credentials).size!==credentials.length)throw Error('Configure distinct service credentials of 16 or more characters');
  const basic='Basic '+Buffer.from(r.actor+':'+password).toString('base64');
  const sign=(c,mode,expiry)=>createHmac('sha256',secret).update(JSON.stringify([c.id,c.task,c.actor,mode,expiry])).digest('hex');
  function form(c){
    const mode=c.decision?'feedback':'decision', expiry=String(r.now()+15*60000);
    if(c.approved)return '';
    return `<form method="post">
      <input type="hidden" name="expires" value="${expiry}"><input type="hidden" name="task" value="${esc(c.task)}">
      <input type="hidden" name="ticket" value="${sign(c,mode,expiry)}">
      ${c.decision?'<input type="hidden" name="action" value="feedback"><p class="muted small">Step 2 of 2 · the reporter receives this text through the protected mailbox.</p>':'<p class="muted small">Step 1 of 2 · only you can decide; the AI draft above is unverified.</p><label>Action <select required name="action"><option value="">Choose…</option><option>investigate</option><option>close</option><option>escalate</option></select></label>'}
      <label>${c.decision?'Protected mailbox update about steps taken or planned and why':'Reason for this decision'}<textarea required maxlength="1500" name="reason"></textarea></label>
      <label class="check"><input required type="checkbox" name="clear" value="yes"> I am authorised and have no conflict on this case.</label>
      <button>${c.decision?'Approve and queue feedback':'Record decision'}</button></form>`;
  }
  const stateChip=s=>chip({sent:'ok',delivered:'ok',failed:'stop',uncertain:'held'}[s]??'',s);
  const statusChips=(data,c)=>(data.hold_reason?chip('held','Held · '+data.hold_reason+' ('+data.policy+')'):chip('protect','AI draft · unverified'))
    +(c.approved?chip('ok','Feedback approved'):c.decision?chip('accent','Decided · '+c.decision):chip('','Decision pending'));
  function review(c){
    const data=JSON.parse(c.payload),d=JSON.parse(c.clocks),effects=r.effects(c.id);
    const sent=k=>effects.some(e=>e.kind===k && e.state==='sent');
    const items=a=>a.length?a.map(x=>'<li>'+esc(x)+'</li>').join(''):'<li class="muted">None supplied</li>';
    const details = data.hold_reason
      ? card('doc','Held for local review: '+esc(data.hold_reason)+' ('+esc(data.policy)+')',
          `<div class="callout"><b>No AI draft for this report.</b> The local checks kept it on this machine before any AI service saw it. Read the original yourself.</div>
          <p><a class="btn" href="http://127.0.0.1:${Number(intakePort || 8000)}/demo/held/${encodeURIComponent(c.id)}">Review original on the intake host</a></p>`)
      : card('doc','Unverified report · '+esc(data.category),
          `<p class="muted small">Drafted by the model from screened text only. Names are case tokens; the mapping stays on this machine.</p>
          <div class="group"><b>Reported facts</b><ul class="facts">${items(data.brief.facts)}</ul></div>
          <div class="group"><b>Timeline</b><ul class="facts">${items(data.brief.timeline)}</ul></div>
          <div class="group"><b>Evidence</b><ul class="facts">${items(data.brief.evidence)}</ul></div>`);
    const clock=(name,done,missed,due,target)=>`<div class="clock"><b>${name}${done?chip('ok','Sent'):missed?chip('stop','Missed'):chip('','Open')}</b>
      <dl><dt>Due</dt><dd>${esc(due)}</dd><dt>Send by</dt><dd>${esc(target)}</dd></dl></div>`;
    const rows=effects.map(e=>'<tr><td>'+esc(e.kind)+'</td><td>'+stateChip(e.state)+'</td><td>'+esc(e.channel)+'</td><td>'+esc(when(e.updated))+'</td></tr>').join('');
    return page(c.id,`<div class="crumbs"><a href="/review">← Review queue</a><span class="muted small">Received ${esc(when(data.received))} · assigned to ${esc(c.actor)}</span></div>
      <div class="title"><h2><code>${esc(c.id)}</code></h2>${statusChips(data,c)}</div>${details}
      ${card('clock','Deadlines · Europe/Amsterdam',`<div class="clocks">${clock('Acknowledgement · 7 days',sent('ack'),d.ackMissed,d.ackDue,d.ackTarget)}${clock('Feedback · 3 months',sent('feedback'),d.feedbackMissed,d.feedbackDue,d.feedbackTarget)}</div>
      ${d.calendarReview?'<p class="muted small">Verify the operational holiday calendar for this year.</p>':''}
      ${c.demo?'<p class="muted small">Demo reminders only · acknowledgement +1 min, feedback +2 min from '+esc(when(c.accepted))+'</p>':''}`)}
      ${card('send','Delivery status',rows?`<div class="table-wrap"><table><tr><th>Event</th><th>State</th><th>Channel</th><th>Updated</th></tr>${rows}</table></div>`:'<p class="muted">Nothing queued yet.</p>')}
      ${card('gavel','Human decision · '+esc(c.decision??'pending'),
        (c.decision?'<div class="decided"><b>'+esc(c.decision)+'</b> · '+esc(c.reason)+'<div class="muted small">'+esc(c.actor)+' · '+esc(when(c.decided))+'</div></div>':'')
        +(c.approved?'<div class="decided"><b>Feedback approved</b> · '+esc(c.feedback)+'<div class="muted small">'+esc(when(c.approved))+'</div></div>':'')
        +(c.decision&&!c.approved?'<h4>Approve substantive feedback</h4>':'')+form(c),
        c.decision?'':chip('held','Needs you'))}`,c.actor);
  }
  return createServer(async(req,res)=>{
    const headers={'cache-control':'no-store','x-content-type-options':'nosniff','referrer-policy':'no-referrer','content-security-policy':"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'"};
    const reply=(status,value,type='application/json')=>{res.writeHead(status,{'content-type':type,...headers});res.end(value);};
    try{
      if(req.method==='POST' && ['/accept','/tick'].includes(req.url)){
        if(reviewOnly)reject(404);
        if(!eq(req.headers.authorization,'Bearer '+(req.url==='/tick'?secret:wire)))reject(401);
        if(req.url==='/tick'){r.tick();if(sendTable)await r.mirror(sendTable);return reply(200,'{"ok":true}');}
        if(req.headers['content-type']?.split(';')[0]!=='application/json')reject(415);
        let b;try{b=JSON.parse(await body(req));}catch{reject(400);}
        return reply(r.accept(b,req.headers['idempotency-key']),'{"accepted":true}');
      }
      if(!eq(req.headers.authorization,basic)){res.setHeader('www-authenticate','Basic realm="Designated case handler"');reject(401);}
      if(req.method==='GET' && req.url==='/review'){
        const cases=r.db.prepare('SELECT id,payload,decision,approved FROM cases WHERE actor=? ORDER BY rowid DESC').all(r.actor);
        const links=cases.map(c=>{const data=JSON.parse(c.payload);
          return '<li><a class="row" href="/review/'+encodeURIComponent(c.id)+'"><code>'+esc(c.id)+'</code>'+statusChips(data,c)
            +'<span class="when muted small">Received '+esc(when(data.received))+'</span></a></li>';}).join('');
        const open=cases.filter(c=>!c.decision).length;
        const intake=intakePort?'<a class="btn" href="http://127.0.0.1:'+Number(intakePort)+'/">Submit a synthetic report</a>':'';
        return reply(200,page('Review queue',`<div class="crumbs"><div class="title"><h2>Review queue</h2>${chip(open?'held':'ok',open+' awaiting a decision')}</div>${intake}</div>
          ${card('inbox','Assigned to you',links?'<ul class="queue">'+links+'</ul>':'<p class="empty">No reports yet. New reports appear here as soon as n8n delivers them.</p>')}`,r.actor),'text/html; charset=utf-8');
      }
      const match=/^\/review\/([^/?#]+)$/.exec(req.url),c=match && r.get(decodeURIComponent(match[1]));
      if(!c || c.actor!==r.actor)reject(404);
      if(req.method==='GET')return reply(200,review(c),'text/html; charset=utf-8');
      if(req.method!=='POST' || req.headers['content-type']?.split(';')[0]!=='application/x-www-form-urlencoded')reject(415);
      const fields=new URLSearchParams(await body(req));
      const mode=fields.get('action')==='feedback'?'feedback':'decision',exp=fields.get('expires');
      if(!/^\d{13}$/.test(exp)||Number(exp)<=r.now()||!eq(sign(c,mode,exp),fields.get('ticket')))reject(403);
      r.approve(c.id,fields.get('task'),r.actor,fields.get('action'),fields.get('reason'),fields.get('clear')==='yes');
      res.writeHead(303,{...headers,location:req.url});res.end();
    }catch(e){reply(e.status??503,'{"accepted":false}');}
  });
}
export function tableAdapter(env){
  if(!env.TABLE_ID)return;
  if(!/^[a-zA-Z0-9_-]+$/.test(env.TABLE_ID)||!env.TABLE_API_KEY)throw Error('Set data table credentials');
  const url=new URL('/api/v1/data-tables/'+env.TABLE_ID+'/rows',env.N8N_ORIGIN??'http://127.0.0.1:5678');
  if(url.hostname!=='127.0.0.1')throw Error('Use the local n8n instance');
  return async(id,c)=>{
    const resp=await fetch(url,{method:'POST',redirect:'error',signal:AbortSignal.timeout(5000),
      headers:{'content-type':'application/json','X-N8N-API-KEY':env.TABLE_API_KEY},
      body:JSON.stringify({data:[{case_id:id,received_at:JSON.parse(c.payload).received}]})});
    if(resp.ok)return 'sent';
    return [400,401,403,404,422].includes(resp.status)?'failed':'uncertain';
  };
}
// Compare real paths: on Windows the drive letter's case or a short (8.3) name can differ
// between argv and import.meta.url, and a mismatch would silently skip starting the register.
const same=(a,b)=>{try{const x=realpathSync.native(a),y=realpathSync.native(b);return process.platform==='win32'?x.toLowerCase()===y.toLowerCase():x===y;}catch{return false;}};
if(process.argv[1] && same(fileURLToPath(import.meta.url),process.argv[1])){
  const e=process.env,dir=e.CASE_DIR??join(e.LOCALAPPDATA??homedir(),'culo-protected-demo');
  const [cmd,id,kind,state]=process.argv.slice(2);
  const reviewOnly=cmd==='review';
  const file=join(dir,'register.sqlite');
  if(reviewOnly && (!e.CASE_DIR || !id || !existsSync(file)))throw Error('Supply CASE_DIR with an existing register.sqlite and a case ID.');
  if(!reviewOnly)mkdirSync(dir,{recursive:true,mode:0o700});
  const sendTable=reviewOnly?undefined:tableAdapter(e);
  const r=new Register(file,{actor:e.HANDLER_REF??'handler',demo:e.DEMO_CLOCK==='1',table:!!sendTable,presenterMailbox:e.DEMO_INTAKE==='1',
    reviewBase:'http://127.0.0.1:'+Number(e.DEMO_REGISTER_PORT??8788),
    routes:reviewOnly?[]:(e.SYNTHETIC_MAILBOX_CASES??'').split(',').filter(Boolean)});
  if(cmd==='route')r.route(id);
  else if(cmd==='reconcile')r.reconcile(id,kind,state);
  else if(cmd==='inbox')console.table(r.db.prepare('SELECT * FROM inbox WHERE id=?').all(id));
  else if(reviewOnly){
    if(r.get(id)?.actor!==r.actor)throw Error('This case is unavailable for the configured handler.');
    const server=service(r,{reviewOnly:true,password:e.HANDLER_PASSWORD,secret:randomBytes(32).toString('hex')});
    server.listen(Number(e.DEMO_REGISTER_PORT??0),'127.0.0.1',()=>{
      console.log('http://127.0.0.1:'+server.address().port+'/review/'+encodeURIComponent(id));
    });
  }
  else if(cmd)throw Error('Unknown command');
  else service(r,{wire:e.N8N_TOKEN,secret:e.WORKER_TOKEN,password:e.HANDLER_PASSWORD,sendTable,
    intakePort:e.DEMO_INTAKE==='1'?e.DEMO_INTAKE_PORT:null}).listen(Number(e.DEMO_REGISTER_PORT??8788),'127.0.0.1');
}
