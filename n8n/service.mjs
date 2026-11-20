import {createServer} from 'node:http';
import {createHmac,randomBytes,timingSafeEqual} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {existsSync,mkdirSync} from 'node:fs';
import {join} from 'node:path';
import {homedir} from 'node:os';
import {Register} from './register.mjs';
import {digest,reject} from './contract.mjs';

const eq=(a,b)=>timingSafeEqual(Buffer.from(digest(String(a))),Buffer.from(digest(String(b))));
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const page=(title,body)=>`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>${esc(title)}</title><style>
body{margin:0;background:#f6f4ee;color:#172c31;font:18px/1.5 system-ui}main{max-width:860px;margin:36px auto;padding:0 28px}header{color:#096c66;font-weight:700;letter-spacing:.04em}h1{font:42px/1.12 Georgia;margin:20px 0}h2{font:26px Georgia}section{background:white;border-left:4px solid #297d76;padding:14px 22px;margin:16px 0}small{color:#496369}label{display:block;margin:12px 0}textarea{width:95%;padding:8px}button,select{padding:8px 12px;font:inherit}dt{font-weight:bold}dd{margin-left:0}a{color:#136963}table{width:100%;text-align:left}td{padding:5px}code{overflow-wrap:anywhere}</style><main><header>GROUP ČULO &nbsp; / &nbsp; CONFIDENTIAL CASE REVIEW</header><h1>${esc(title)}</h1>${body}</main></html>`;
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
    return `<section><h2>${c.decision?'Approve substantive feedback':'Record a human decision'}</h2><form method="post">
      <input type="hidden" name="expires" value="${expiry}"><input type="hidden" name="task" value="${esc(c.task)}">
      <input type="hidden" name="ticket" value="${sign(c,mode,expiry)}">
      ${c.decision?'<input type="hidden" name="action" value="feedback">':'<label>Action <select required name="action"><option value="">Choose…</option><option>investigate</option><option>close</option><option>escalate</option></select></label>'}
      <label>${c.decision?'Protected mailbox update about steps taken or planned and why':'Reason for this decision'}<textarea required maxlength="1500" name="reason"></textarea></label>
      <label><input required type="checkbox" name="clear" value="yes"> I am authorised and have no conflict on this case.</label>
      <button>${c.decision?'Approve and queue feedback':'Record decision'}</button></form></section>`;
  }
  function review(c){
    const data=JSON.parse(c.payload),d=JSON.parse(c.clocks);
    const items=a=>a.length?a.map(x=>'<li>'+esc(x)+'</li>').join(''):'<li>None supplied</li>';
    const effects=r.effects(c.id).map(e=>'<tr><td>'+esc(e.kind)+'</td><td>'+esc(e.state)+'</td><td>'+esc(e.channel)+'</td><td>'+esc(e.updated)+'</td></tr>').join('');
    return page(c.id,`<p>Assigned to ${esc(c.actor)} · Received ${esc(data.received)}</p><section><h2>Unverified report · ${esc(data.category)}</h2>
      <b>Reported facts</b><ul>${items(data.brief.facts)}</ul><b>Timeline</b><ul>${items(data.brief.timeline)}</ul><b>Evidence</b><ul>${items(data.brief.evidence)}</ul></section>
      <section><h2>Deadlines · Europe/Amsterdam</h2><p>Acknowledgement due ${d.ackDue} · send by ${d.ackTarget} · missed ${d.ackMissed}<br>Feedback due ${d.feedbackDue} · send by ${d.feedbackTarget} · missed ${d.feedbackMissed}</p>
      ${d.calendarReview?'<p>Verify the operational holiday calendar for this year.</p>':''}
      ${c.demo?'<p>Demo reminders only · acknowledgement +1 min, feedback +2 min from '+esc(c.accepted)+'</p>':''}</section>
      <section><h2>Delivery status</h2><table><tr><th>Event</th><th>State</th><th>Channel</th><th>Updated (UTC)</th></tr>${effects}</table></section>
      <section><h2>Human decision · ${esc(c.decision??'pending')}</h2>${c.decision?'<p>'+esc(c.reason)+' · '+esc(c.actor)+' · '+esc(c.decided)+'</p>':''}
      ${c.approved?'<p>Feedback approved '+esc(c.approved)+' · '+esc(c.feedback)+'</p>':''}</section>${form(c)}`);
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
        const links=r.db.prepare('SELECT id FROM cases WHERE actor=? ORDER BY rowid DESC').all(r.actor)
          .map(c=>'<li><a href="/review/'+encodeURIComponent(c.id)+'">'+esc(c.id)+'</a></li>').join('');
        const intake=intakePort?'<a href="http://127.0.0.1:'+Number(intakePort)+'/demo">Submit a synthetic report</a>':'';
        return reply(200,page('Review queue',intake+'<ul>'+links+'</ul>'),'text/html; charset=utf-8');
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
if(process.argv[1] && import.meta.url===pathToFileURL(process.argv[1]).href){
  const e=process.env,dir=e.CASE_DIR??join(e.LOCALAPPDATA??homedir(),'culo-protected-demo');
  const [cmd,id,kind,state]=process.argv.slice(2);
  const reviewOnly=cmd==='review';
  const file=join(dir,'register.sqlite');
  if(reviewOnly && (!e.CASE_DIR || !id || !existsSync(file)))throw Error('Supply CASE_DIR with an existing register.sqlite and a case ID.');
  if(!reviewOnly)mkdirSync(dir,{recursive:true,mode:0o700});
  const sendTable=reviewOnly?undefined:tableAdapter(e);
  const r=new Register(file,{actor:e.HANDLER_REF??'handler',demo:e.DEMO_CLOCK==='1',table:!!sendTable,
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
