// Disposable instance only. The check/model doubles accept only this exact synthetic report.
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {randomUUID} from 'node:crypto';
import {performance} from 'node:perf_hooks';
import {server} from '../legacy/node-adapter/server.mjs';
import {openStore} from '../legacy/node-adapter/store.mjs';
import {Register} from './register.mjs';
import {join} from 'node:path';
import {writeFileSync} from 'node:fs';
import {setTimeout as delay} from 'node:timers/promises';
const e=process.env;
assert.equal(e.N8N_WEBHOOK_URL,'http://127.0.0.1:5689/webhook/protected-case');
const r=new Register(join(e.CASE_DIR,'register.sqlite'));
const auth='Basic '+Buffer.from(e.HANDLER_REF+':'+e.HANDLER_PASSWORD).toString('base64');
const text='Two invoice totals differ. The discrepancy appeared on Monday. The ledger has both entries.';
const intakeToken=randomUUID();
let available=true,modelCalls=0,handoffs=0;
const check=createServer(async(req,res)=>{
  let body='';for await(const b of req)body+=b;
  const data=JSON.parse(body);
  if(req.url==='/check' && available && data.text===text)res.end(JSON.stringify({complete:true,checked:['P1','P2','P3','P4'],findings:[]}));
  else if(req.url==='/chat' && available){
    modelCalls++;
    res.end(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify({category:'other',facts:[0],timeline:[1],evidence:[2]})}}]}));
  }else{res.writeHead(503);res.end();}
});
const listen=async srv=>{await new Promise(ok=>srv.listen(0,'127.0.0.1',ok));return 'http://127.0.0.1:'+srv.address().port;};
const checkBase=await listen(check);
const relay=createServer(async(req,res)=>{
  handoffs++;
  let body='';for await(const part of req)body+=part;
  const headers=Object.fromEntries(['content-type','authorization','idempotency-key'].map(k=>[k,req.headers[k]]));
  const result=await fetch(e.N8N_WEBHOOK_URL,{method:'POST',headers,body});res.writeHead(result.status);res.end(await result.text());
});
const backend=server({...e,N8N_WEBHOOK_URL:await listen(relay),INTAKE_TOKEN:intakeToken,BRANE_CHECK_URL:checkBase+'/check',BRANE_CHAT_URL:checkBase+'/chat',BRANE_MODEL:'fixture-only'},openStore(':memory:'),()=>{});
const api=await listen(backend);
const submit=()=>fetch(api+'/reports',{method:'POST',headers:{authorization:'Bearer '+intakeToken,'content-type':'application/json'},body:JSON.stringify({text})});
const post=(b,key=b.case_id,bearer=e.N8N_TOKEN)=>fetch(e.N8N_WEBHOOK_URL,{method:'POST',headers:{...(bearer?{authorization:'Bearer '+bearer}:{}),'content-type':'application/json','idempotency-key':key},body:JSON.stringify(b)});
const review=id=>'http://127.0.0.1:8788/review/'+encodeURIComponent(id);
const read=async id=>{const resp=await fetch(review(id),{headers:{authorization:auth}});assert.equal(resp.status,200);return resp.text();};
const fields=html=>Object.fromEntries(['task','ticket','expires'].map(k=>[k,html.match(new RegExp('name="'+k+'" value="([^"]+)"'))[1]]));
const act=(id,form,action,reason='Check the two source entries.',token=auth,clear='yes')=>fetch(review(id),{method:'POST',redirect:'manual',headers:{authorization:token},body:new URLSearchParams({...form,action,reason,clear})});
const tick=async()=>{const res=await fetch('http://127.0.0.1:8788/tick',{method:'POST',headers:{authorization:'Bearer '+e.WORKER_TOKEN}});assert.equal(res.status,200);};
const count=()=>r.db.prepare('SELECT count(*) n FROM cases').get().n;
try{
  const start=performance.now(),out=await submit();assert.equal(out.status,200);
  const b=await out.json(),id=b.case_id,html=await read(id);
  for(const fact of text.split(/(?<=\.) /))assert.ok(html.includes(fact));
  assert.ok(html.includes('Human decision · pending'));const elapsed=Math.round(performance.now()-start);
  // The operator explicitly associates this case with a fresh synthetic mailbox.
  r.route(id);await tick();
  assert.equal(r.effects(id).find(x=>x.kind==='ack').state,'sent');
  const before=count(),same=await Promise.all(Array.from({length:8},()=>post(b)));
  assert.ok(same.every(x=>x.status===200));assert.equal(count(),before);
  assert.equal((await post({...b,summary:'Other summary',brief:undefined})).status,409);
  const fresh={...b,case_id:'WB-'+randomUUID()};
  for(const [body,key,bearer] of [[fresh,fresh.case_id,''],[fresh,fresh.case_id,'wrong'],[fresh,'other'],[{...fresh,brane_status:'failed'},fresh.case_id],[{...fresh,extra:'invalid'},fresh.case_id]]){
    const resp=await post(body,key,bearer);assert.ok(resp.status>=400 && resp.status<500);
  }
  assert.equal(count(),before);
  const malformed=await fetch(e.N8N_WEBHOOK_URL,{method:'POST',headers:{authorization:'Bearer '+e.N8N_TOKEN,'content-type':'application/json'},body:'{"broken": synthetic_marker}'});
  assert.ok(malformed.status>=400 && malformed.status<500);
  assert.ok(!(await malformed.text()).includes('synthetic_marker'));
  assert.equal(count(),before);
  const lost={...b,case_id:'WB-'+randomUUID()};
  const first=await post(lost);await first.body.cancel();assert.equal((await post(lost)).status,200);
  const pending=await read(lost.case_id);await tick();assert.equal(r.effects(lost.case_id).find(x=>x.kind==='ack').state,'unreachable');
  for(const action of ['close','escalate']){
    const sample=action==='close'?lost:{...b,case_id:'WB-'+randomUUID()};
    if(action==='escalate'){
      const race=await Promise.all(Array.from({length:8},()=>post(sample)));
      assert.deepEqual(race.map(x=>x.status).sort(),[200,200,200,200,200,200,200,201]);
      await tick();assert.equal(r.db.prepare("SELECT count(*) n FROM inbox WHERE id=? AND kind='notify'").get(sample.case_id).n,1);
    }
    const f=fields(action==='close'?pending:await read(sample.case_id));
    assert.equal((await act(sample.case_id,f,action,'Independent review','Basic d3Jvbmc6d3Jvbmc=')).status,401);
    assert.equal((await act(sample.case_id,f,action,'Independent review',auth,'')).status,403);
    assert.equal((await act(id,f,action)).status,403);
    assert.equal((await act(sample.case_id,f,action)).status,303);
    assert.equal((await act(sample.case_id,f,action)).status,409);
  }
  available=false;
  const prior=[modelCalls,handoffs,count()];assert.equal((await submit()).status,503);
  assert.deepEqual([modelCalls,handoffs,count()],prior);
  let demo={id,reviewUrl:review(id),text,elapsed,received_at:b.received_at,category:b.category,brane_status:b.brane_status,decisions:b.decisions};
  writeFileSync(join(e.CASE_DIR,'walkthrough.json'),JSON.stringify(demo));
  if(!process.argv.includes('--hold')){
    const f=fields(await read(id));assert.equal((await act(id,f,'investigate')).status,303);
    assert.ok(!r.effects(id).some(x=>x.kind==='feedback'));
    assert.equal((await act(id,fields(await read(id)),'feedback','We will compare the ledger entries because their totals differ.')).status,303);
    await tick();assert.equal(r.effects(id).find(x=>x.kind==='feedback').state,'sent');
  }
  for(let i=0;i<10 && r.effects(id).find(x=>x.kind==='table')?.state==='pending';i++){await tick();await delay(100);}
  const rows=await fetch(e.N8N_ORIGIN+'/api/v1/data-tables/'+e.TABLE_ID+'/rows',{headers:{'X-N8N-API-KEY':e.TABLE_API_KEY}});
  assert.equal(rows.status,200);assert.equal((await rows.json()).data.filter(x=>x.case_id===id).length,1);
  assert.equal(r.db.prepare("SELECT count(*) n FROM inbox WHERE id=? AND kind IN ('ack','notify')").get(id).n,2);
  console.log(JSON.stringify({...demo,concurrentReplays:8,unavailable:{status:503,additionalModelCalls:0,additionalHandoffs:0},tableRowsForCase:1}));
}finally{backend.close();check.close();relay.close();r.db.close();}

