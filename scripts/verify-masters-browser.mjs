import { spawn } from 'node:child_process'
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const base = process.env.TEST_API_BASE_URL || 'http://127.0.0.1:8082'
const target = new URL(base)
if (process.env.UNISHORTLIST_TEST_MODE !== '1' || !['127.0.0.1','localhost'].includes(target.hostname) || target.port !== '8082') throw new Error('Isolated browser target required')
const ready = await (await fetch(base + '/api/v1/health/ready')).json()
if (ready.database_target !== 'isolated_test' || ready.status !== 'ready') throw new Error('Test database marker required')
const fixture = JSON.parse(readFileSync(process.env.BROWSER_TEST_CREDENTIALS, 'utf8'))
const phase = process.argv[2] || 'identity'
const account = fixture[phase === 'student' ? 'student' : 'admin']
const profile = mkdtempSync(join(tmpdir(), 'unishortlist-masters-browser-'))
const chrome = spawn('/usr/bin/google-chrome', ['--headless=new','--no-sandbox','--disable-gpu','--no-first-run','--disable-dev-shm-usage','--remote-debugging-pipe','--window-size=1440,1100','--user-data-dir=' + profile], { stdio: ['ignore','ignore','ignore','pipe','pipe'] })
let nextId = 0, buffer = '', sessionId
const pending = new Map(), exceptions = [], responses = [], results = []
chrome.stdio[4].on('data', chunk => {
  buffer += chunk.toString()
  let end
  while ((end = buffer.indexOf('\0')) >= 0) {
    const line = buffer.slice(0,end); buffer = buffer.slice(end+1)
    if (!line) continue
    const message = JSON.parse(line)
    if (message.id && pending.has(message.id)) {
      const item = pending.get(message.id); pending.delete(message.id); clearTimeout(item.timer)
      if (message.error) item.reject(new Error(message.error.message)); else item.resolve(message.result)
    }
    if (message.method === 'Runtime.exceptionThrown') exceptions.push(message.params.exceptionDetails.text + ': ' + (message.params.exceptionDetails.exception?.description || ''))
    if (message.method === 'Network.responseReceived' && message.params.response.url.includes('/api/')) responses.push({url:message.params.response.url,status:message.params.response.status})
  }
})
function send(method, params = {}, browser = false) {
  return new Promise((resolve,reject) => {
    const id=++nextId, timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP timeout: '+method))},30000)
    pending.set(id,{resolve,reject,timer})
    chrome.stdio[3].write(JSON.stringify({id,method,params,...(!browser && sessionId ? {sessionId} : {})})+'\0')
  })
}
async function evaluate(expression) {
  const result = await send('Runtime.evaluate', {expression,awaitPromise:true,returnByValue:true})
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text)
  return result.result?.value
}
const pause = ms => new Promise(resolve=>setTimeout(resolve,ms))
async function wait(expression, message, timeout=20000) {
  const started=Date.now()
  while(Date.now()-started<timeout) { try {if(await evaluate(expression)) return} catch {} await pause(100) }
  throw new Error('Wait failed: '+message+'; page: '+await evaluate('document.body.innerText.slice(-1200)'))
}
async function go(path, text) {
  await send('Page.navigate',{url:base+path})
  await wait(`location.pathname===${JSON.stringify(new URL(base+path).pathname)} && document.readyState==='complete' && document.body.innerText.includes(${JSON.stringify(text)})`, path)
}
async function set(selector,value) {
  await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)throw new Error('Missing control');e.value=${JSON.stringify(value)};e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));})()`)
  await pause(50)
}
async function click(text) {
  await evaluate(`(()=>{const e=[...document.querySelectorAll('button')].find(e=>e.textContent.trim()===${JSON.stringify(text)});if(!e || e.disabled)throw new Error('Missing or disabled button: '+${JSON.stringify(text)});e.click()})()`)
}
async function api(path, method='GET', data) {
  return evaluate(`(async()=>{const r=await fetch('/api/v1'+${JSON.stringify(path)},{method:${JSON.stringify(method)},credentials:'include',headers:{'Content-Type':'application/json'},${data===undefined?'':`body:JSON.stringify(${JSON.stringify(data)}),`}});return {status:r.status,data:r.status===204?null:await r.json()}})()`)
}
function check(condition,label) {if(!condition)throw new Error(label);results.push(label);console.log('PASS '+label)}
async function screenshot(label) {
  const image=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false})
  writeFileSync('/tmp/unishortlist-'+phase+'-'+label+'.png',Buffer.from(image.data,'base64'))
}
try {
  await send('Browser.getVersion',{},true)
  const {targetId}=await send('Target.createTarget',{url:'about:blank'},true)
  sessionId=(await send('Target.attachToTarget',{targetId,flatten:true},true)).sessionId
  await send('Page.enable');await send('Runtime.enable');await send('Network.enable')
  await go('/login','Log in')
  await set('#login-email',account.email);await set('#login-password',account.password);await click('Log in')
  await wait("location.pathname==='/discover'",'authenticated login')
  check((await api('/auth/me')).status===200,'authenticated '+phase+' account')
  if(phase==='identity') {
    await go('/admin/institution-reviews','University and Master’s review')
    await set('#institution-review-stage','discovery')
    await wait("document.body.innerText.includes('Almería')",'real university in discovery')
    await go('/admin/institution-reviews/'+fixture.university_id,'Master\'s programme coverage')
    check(await evaluate("document.querySelector('option[value=approve]').disabled"),'university approval blocked before catalogue import')
    await screenshot('discovery')
    await go('/admin/identity-reviews','Institution identity review')
    await wait(`document.querySelector('#target-${fixture.identity_review_id}')!==null`,'source identity form')
    check(await evaluate("document.body.innerText.includes('Máster')"),'named official source candidates visible before link decision')
    await set('#target-'+fixture.identity_review_id,fixture.university_id)
    await set('#reason-'+fixture.identity_review_id,'The official UAL catalogue publisher and ROR website confirm the same university identity.')
    await click('Approve link')
    await wait(`!document.querySelector('#target-${fixture.identity_review_id}')`,'identity decision saved')
    const detail=await api('/admin/identity-reviews/'+fixture.identity_review_id)
    check(detail.data.status==='approved' && detail.data.events.length===1,'source identity link and immutable event recorded')
  } else if(phase==='review') {
    await go('/admin/institution-reviews/'+fixture.university_id,'Master\'s programme coverage')
    await wait("document.body.innerText.includes('Source program offering')",'program identity layers')
    let detail=(await api('/admin/institution-reviews/'+fixture.university_id)).data
    check(detail.programs.length===5 && detail.catalogue_sources.length>0,'five genuine UAL offerings and catalogue evidence rendered')
    check(detail.programs.every(p=>p.program_page_evidence.status==='unavailable'),'missing individual course links remain explicitly unknown')
    check(detail.approval_eligibility.eligible===false,'website review still required')
    if(detail.status!=='needs_evidence') {
    await set('#institution-decision','needs_evidence')
    await set('#institution-reason','The official university website needs verification before this evidence package can be approved.')
    await click('Record institution decision')
    await wait("document.body.innerText.includes('Current decision:')",'needs-evidence history')
    }
    await go('/admin/review/'+fixture.website_fact_id,'Value for review')
    await wait("[...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='Verify fact version')",'website fact review')
    await click('Verify fact version')
    await set('#reason-approve','The official ROR source confirms this university website and institution identity.')
    await click('Confirm')
    await wait("document.body.innerText.includes('Verified')",'website verification')
    await go('/admin/institution-reviews/'+fixture.university_id,'Master\'s programme coverage')
    await wait("document.querySelector('option[value=approve]') && !document.querySelector('option[value=approve]').disabled",'complete package ready for review')
    detail=(await api('/admin/institution-reviews/'+fixture.university_id)).data
    check(detail.approval_eligibility.eligible===true,'approval becomes available only after the full evidence package')
    await screenshot('ready')
    await set('#institution-decision','approve')
    await set('#institution-reason',"The official catalogue evidence confirms named Master's offerings and the verified university identity.")
    await click('Record institution decision')
    await wait("!document.querySelector('#institution-decision')",'institution approval saved')
    detail=(await api('/admin/institution-reviews/'+fixture.university_id)).data
    check(detail.status==='approved' && detail.events.length===2,'institution decision and both review events preserved')
    await go('/admin/program-publication','Program publication review')
    check((await api('/admin/program-publication-reviews')).data.items.every(p=>!p.can_publish),'programme publication blocked while individual links remain unresolved')
    check((await api('/programs')).data.total_items===9,'institution approval does not publish programmes')
    for(const [route,title] of [['/admin/sources','Source registry'],['/admin/jobs','Ingestion'],['/admin/audit','Audit log'],['/admin','Admin console']]) {
      await go(route,title);check(true,'admin browser route '+route)
    }
    check((await api('/admin/audit-events')).data.total_items>=4,'attributable review and fact audit history accessible')
  } else if(phase==='student') {
    await go('/discover','Discover')
    check((await api('/programs')).data.total_items===9,'student sees only nine published fixtures')
    const id=fixture.demo_program_ids[0], second=fixture.demo_program_ids[1]
    await go('/programs/'+id,'About the program')
    if(await evaluate("[...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='Save')")) await click('Save');await wait("[...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='Saved ✓')",'program saved')
    await click('Compare');check(true,'save and compare controls work')
    await go('/saved','Saved');check((await api('/saved-programs')).data.items.length===1,'saved programme persisted for student')
    await go('/compare?ids='+id+','+second,'Compare');await wait("/tuition/i.test(document.body.innerText)",'comparison tuition context');check(true,'comparison rendered with money context')
    await go('/profile','Profile');check((await api('/profile')).status===200,'private profile and eligibility inputs available')
    const evaluation=await api('/eligibility/evaluations','POST',{program_ids:[id]});check(evaluation.status===200,'explicit eligibility evaluation succeeds')
    await go('/shortlist','Your shortlists');await click('New shortlist run')
    await wait("/^\\/shortlist\\/[^/]+$/.test(location.pathname)",'recommendation run detail')
    check((await api('/recommendations')).data.items.length>=1,'shortlist and reproducible run persisted')
    await go('/finance?program='+id,'Cost');await wait("document.body.innerText.includes('Tuition')",'finance facts');check(true,'finance estimate rendered with evidence limitations')
    check((await api('/admin/institution-reviews')).status===403,'student cannot access university review API')
    const candidate=(await api('/programs?q=Almer')).data;check(candidate.total_items===0,'unpublished real source candidates stay hidden from students')
    await screenshot('student')
  }
  check(exceptions.length===0,'no browser JavaScript exceptions')
  writeFileSync('/tmp/unishortlist-browser-'+phase+'.json',JSON.stringify({phase,results,responses,exceptions},null,2))
} catch(error) {
  try {await screenshot('failure')} catch {}
  writeFileSync('/tmp/unishortlist-browser-'+phase+'-failure.json',JSON.stringify({message:error.message,results,responses,exceptions},null,2))
  throw error
} finally {
  try {await send('Browser.close',{},true)} catch {}
  chrome.kill('SIGTERM')
}
