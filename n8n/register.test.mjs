import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {mkdtempSync,rmSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {createInterface} from 'node:readline';
import {fileURLToPath} from 'node:url';
import {clocks,plusMonths} from './calendar.mjs';
import {Register} from './register.mjs';
import {service} from './service.mjs';

const received='2026-11-20T12:00:00.000Z';
const sample={case_id:'WB-0007',reporter:'REPORTER_01',category:'other',summary:'Two totals differ.',persons:[],received_at:received,brane_status:'ok',decisions:[{policy:'P5',action:'ALLOW',count:1},{policy:'P6',action:'HUMAN',count:1}]};
test('Amsterdam days, DST, leap/month end, weekends and public holidays',()=>{
  const d=clocks(received,null,null,Date.parse('2026-11-28T00:00:00Z'));
  assert.deepEqual([d.ackDue,d.feedbackDue,d.feedbackTarget,d.ackMissed],['2026-11-27','2027-02-27','2027-02-26',true]);
  assert.equal(clocks(received,'2026-11-23T23:15:00Z',null,Date.now()).feedbackDue,'2027-02-24');
  assert.equal(clocks('2026-03-28T23:30:00Z',null,null,Date.now()).ackDue,'2026-04-05');
  assert.equal(clocks('2026-12-18T08:00:00Z',null,null,Date.now()).ackTarget,'2026-12-24');
  assert.equal(plusMonths('2023-11-30',3),'2024-02-29');
  assert.equal(plusMonths('2024-11-30',3),'2025-02-28');
});
test('outbox failure is isolated and recoverable, late dispatch preserves missed history',()=>{
  let now=Date.parse(received);
  const r=new Register(':memory:',{now:()=>now,demo:true});r.accept(sample,sample.case_id);
  r.db.exec("CREATE TRIGGER capture_off BEFORE INSERT ON inbox WHEN new.kind='notify' BEGIN SELECT RAISE(ABORT,'offline'); END;");
  r.tick();
  const state=k=>r.effects(sample.case_id).find(e=>e.kind===k)?.state;
  assert.equal(state('notify'),'failed');assert.equal(state('ack'),'unreachable');
  r.db.exec('DROP TRIGGER capture_off');r.reconcile(sample.case_id,'notify','pending');
  now+=121000;r.tick();assert.equal(state('feedback-demo-reminder'),'sent');
  assert.equal(state('notify'),'sent');assert.equal(r.get(sample.case_id).decision,null);
  const before=JSON.parse(r.get(sample.case_id).clocks);
  assert.equal(before.feedbackDue,'2027-02-27');
  now=Date.parse('2027-03-02T09:00:00Z');r.tick();r.route(sample.case_id);r.tick();
  const late=JSON.parse(r.get(sample.case_id).clocks);
  assert.equal(late.ackMissed,true);assert.equal(late.feedbackMissed,true);assert.equal(late.feedbackDue,'2027-06-02');
  assert.equal(r.db.prepare("SELECT count(*) n FROM inbox WHERE kind='feedback-demo-reminder'").get().n,1);
});
test('uncertain external write is held across restart and duplicate',async()=>{
  const path=join(mkdtempSync(join(tmpdir(),'culo-restart-')),'register.sqlite');
  let r=new Register(path,{table:true});r.accept(sample,sample.case_id);
  const c=r.get(sample.case_id);let calls=0;
  await r.mirror(async()=>{calls++;throw Error('lost response');});r.db.close();
  r=new Register(path,{table:true,demo:true});assert.equal(r.accept(sample,sample.case_id),200);
  await r.mirror(async()=>{calls++;return 'sent';});r.tick();
  assert.equal(calls,1);assert.equal(r.get(sample.case_id).task,c.task);
  assert.equal(r.get(sample.case_id).demo,0);assert.ok(!r.effects(sample.case_id).some(e=>e.kind.includes('demo')));
  assert.equal(r.effects(sample.case_id).find(e=>e.kind==='table').state,'uncertain');
  r.reconcile(sample.case_id,'table','sent');r.db.close();
});
test('expiry leaves the task pending and an authorised handler can open a fresh form',async t=>{
  let now=Date.parse(received);const r=new Register(':memory:',{now:()=>now});r.accept(sample,sample.case_id);
  const password='temporary-handlertest',basic='Basic '+Buffer.from('handler:'+password).toString('base64');
  const s=service(r,{password,secret:'temporary-worker-test',wire:'temporary-intake-test'});
  await new Promise(ok=>s.listen(0,'127.0.0.1',ok));t.after(()=>s.close());
  const url='http://127.0.0.1:'+s.address().port+'/review/WB-0007';
  const html=await (await fetch(url,{headers:{authorization:basic}})).text();
  const f=new URLSearchParams({action:'investigate',reason:'Compare the entries.',clear:'yes'});
  for(const k of ['ticket','expires','task'])f.set(k,html.match(new RegExp('name="'+k+'" value="([^"]+)"'))[1]);
  now+=16*60000;
  assert.equal((await fetch(url,{method:'POST',headers:{authorization:basic},body:f})).status,403);assert.equal(r.get(sample.case_id).decision,null);
  assert.notEqual(await (await fetch(url,{headers:{authorization:basic}})).text(),html);
});

test('a saved case opens a live decision form and keeps the decision after refresh', {timeout:15000}, async t=>{
  const dir=mkdtempSync(join(tmpdir(),'culo-review-'));
  const dbPath=join(dir,'register.sqlite');
  const seed=new Register(dbPath);
  seed.accept({...sample,received_at:new Date().toISOString()},sample.case_id);
  seed.db.close();

  const password='synthetic-handler-login';
  const child=spawn(process.execPath,[
    fileURLToPath(new URL('./service.mjs',import.meta.url)),'review',sample.case_id,
  ],{env:{...process.env,CASE_DIR:dir,DEMO_REGISTER_PORT:'0',HANDLER_REF:'handler',HANDLER_PASSWORD:password},
     stdio:['ignore','pipe','inherit']});
  const closed=once(child,'close');
  const lines=createInterface({input:child.stdout});
  t.after(async()=>{
    child.kill();
    await closed;
    rmSync(dir,{recursive:true,force:true});
  });
  const [url]=await Promise.race([
    once(lines,'line',{signal:t.signal}),
    closed.then(()=>{throw Error('Review server exited before providing the case link');}),
  ]);
  assert.equal(new URL(url).pathname,'/review/'+sample.case_id);
  assert.equal((await fetch(url)).status,401);
  assert.equal((await fetch(new URL('/tick',url),{method:'POST'})).status,404);
  const headers={authorization:'Basic '+Buffer.from('handler:'+password).toString('base64')};
  const getForm=async()=>{
    const response=await fetch(url,{headers});
    assert.equal(response.status,200);
    return response.text();
  };
  const html=await getForm();
  assert.match(html,/Human decision · pending/);
  assert.match(html,/<form method="post">/);
  assert.match(html,/<button>Record decision<\/button>/);
  assert.doesNotMatch(html,/<fieldset disabled/);
  const reason='Compare the original ledger entries.';
  const fields=new URLSearchParams({action:'investigate',reason,clear:'yes'});
  for(const name of ['expires','task','ticket']){
    fields.set(name,html.match(new RegExp('name="'+name+'" value="([^"]+)"'))[1]);
  }
  const post=await fetch(url,{method:'POST',body:fields,headers,redirect:'manual'});
  assert.equal(post.status,303);
  assert.equal(new URL(post.headers.get('location'),url).href,url);
  const refreshed=await getForm();
  assert.match(refreshed,/Human decision · investigate/);
  assert.ok(refreshed.includes(reason));
  assert.match(refreshed,/Approve substantive feedback/);
  const saved=new Register(dbPath);
  try{
    const record=saved.get(sample.case_id);
    assert.deepEqual([record.decision,record.reason,record.approved],['investigate',reason,null]);
  }finally{saved.db.close();}
});

test('held receipt opens one local review task and starts both clocks', () => {
  const id = 'WB-' + 'a'.repeat(32);
  const r = new Register(':memory:', {now: () => Date.parse(received), routes: [id]});
  const held = {case_id:id, reporter:'REPORTER_01', received_at:received, status:'held_for_review',
    hold_reason:'restricted_material', policy:'P3', decisions:[
      {policy:'P3',action:'LOCAL_ONLY',count:null},{policy:'P6',action:'HUMAN_ONLY',count:null}]};
  assert.throws(() => r.accept({...held,summary:'Forbidden field'}, id));
  assert.throws(() => r.accept({...held,hold_reason:'free text'}, id));
  assert.equal(r.accept(held,id),201);
  const task = r.get(id).task;
  r.tick();
  assert.equal(r.accept(held,id),200);
  assert.equal(r.get(id).task,task);
  const dates = JSON.parse(r.get(id).clocks);
  assert.deepEqual([dates.ackDue,dates.feedbackDue],['2026-11-27','2027-02-20']);
  assert.equal(r.effects(id).find(e=>e.kind==='ack').state,'sent');
  assert.match(r.db.prepare("SELECT message FROM inbox WHERE kind='notify'").get().message,/Review original/);
  r.db.close();
});
