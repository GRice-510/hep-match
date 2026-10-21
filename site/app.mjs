import {normalizePapers,matches,mergeBackup,markdown,bibtex,safeTranslate} from './core.mjs';
const $=id=>document.getElementById(id);
const PREFIX='hep-match:v1:'+location.pathname.replace(/index\.html$/,'')+':';
let toastTimer, locked=false, queue=[], history=[], view='en', translationBusy=false;
function notify(message){$('toast').textContent=message;$('toast').classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.remove('visible'),4000);}
function storageWarning(){$('storage-warning').hidden=false;$('storage-warning').textContent='このブラウザにデータを保存できません。記録を失わないよう、設定からJSONバックアップを書き出してください。';}
function read(key,fallback){try{const value=localStorage.getItem(PREFIX+key);return value?JSON.parse(value):fallback;}catch{storageWarning();return fallback;}}
function write(key,value){try{localStorage.setItem(PREFIX+key,JSON.stringify(value));return true;}catch{storageWarning();return false;}}
let stored=read('reading',{schema_version:1,saved:[],read:[]});
let state;
try{state=mergeBackup({saved:[],read:[]},stored);}catch{state={schema_version:1,saved:[],read:[]};storageWarning();}
let readSet=new Set(state.read),saved=new Map(state.saved.map(p=>[p.id,p]));
let preferences=read('preferences',{});
if(!preferences||typeof preferences!=='object') preferences={};
// Research abstracts need the original wording: unreviewed MT is opt-in.
view=preferences.language==='ja'?'ja':'en';
$('show-read').checked=preferences.showRead===true;
let doc={papers:[],categories:['hep-th']}, all=[], loaded=false;
let localTranslations=read('translations',{});
if(!localTranslations||typeof localTranslations!=='object'||Array.isArray(localTranslations)) localTranslations={};
function persist(){write('reading',{schema_version:1,read:[...readSet].slice(-50000),saved:[...saved.values()]});}
function savePreferences(){write('preferences',{language:view,showRead:$('show-read').checked,category:$('category').value});}
function node(tag,cls,value){const n=document.createElement(tag);if(cls)n.className=cls;if(value!==undefined)n.textContent=value;return n;}
function link(label,href){const n=node('a','',label);n.href=href;n.target='_blank';n.rel='noopener noreferrer';return n;}
function dateLabel(raw){const date=new Date(raw);return Number.isNaN(date.valueOf())?'日付不明':date.toLocaleDateString('ja-JP');}
let mathQueue=Promise.resolve();
function typeset(element){if(!window.MathJax?.typesetPromise)return;mathQueue=mathQueue.catch(()=>{}).then(()=>{if(element.isConnected)return MathJax.typesetPromise([element]);}).catch(()=>{});}
function clearMath(element){try{window.MathJax?.typesetClear?.([element]);}catch{}}
document.addEventListener('math-ready',()=>typeset($('paper-content')));
function cachedPaper(p){const value=localTranslations[p.id];if(value&&value.source===p.title+'\n'+p.abstract){return {...p,title_ja:typeof value.title==='string'?value.title:p.title_ja,abstract_ja:typeof value.abstract==='string'?value.abstract:p.abstract_ja,title_translator:'browser',abstract_translator:'browser'};}return p;}
function provider(name){return ({argos:'Argos試験訳 · 要原文確認',deepl:'DeepL参考訳',browser:'端末内の参考訳'})[name]||'参考訳';}
function updateMetrics(){const unread=all.filter(p=>!readSet.has(p.id)&&matches(p,$('category').value,$('search').value)).length;$('remaining').textContent=String(unread);$('saved-count').textContent=String(saved.size);$('undo').disabled=history.length===0||locked;$('language').textContent=view==='ja'?'原文に戻す':'日本語の参考訳を表示';$('language').setAttribute('aria-pressed',String(view==='ja'));}
function rebuild(){queue=all.filter(p=>($('show-read').checked||!readSet.has(p.id))&&matches(p,$('category').value,$('search').value));render();}
function render(){
  const raw=queue[0],content=$('paper-content');clearMath(content);content.replaceChildren();$('card').scrollTop=0;
  $('card').style.transform='';$('card').classList.remove('leaving','dragging');
  updateMetrics();$('skip').disabled=$('keep').disabled=!raw||locked;$('paper-tools').hidden=!raw;
  $('empty').hidden=Boolean(raw);content.hidden=!raw;
  $('position').textContent=queue.length?`あと ${queue.length} 件${$('show-read').checked?' · 確認済みを含む':''}`:'新着をチェック';
  if(!raw){
    if(!loaded){$('empty-title').textContent='新着データがまだありません';$('empty-text').textContent='初回はGitHubのActionsで「Update papers and deploy」を実行してください。設定手順は画面下の「使い方とソース」にあります。';$('empty-action').textContent='再読み込み';}
    else if(!all.length){$('empty-title').textContent='新着データの準備中です';$('empty-text').textContent='Actionsの取得処理が完了すると、ここに論文が表示されます。';$('empty-action').textContent='再読み込み';}
    else{$('empty-title').textContent='この条件の論文を確認しました';$('empty-text').textContent='保存した論文は「あとで読む」で確認できます。検索条件を変えるか、次の新着をお待ちください。';$('empty-action').textContent='保存リストを見る';}
    return;
  }
  const p=cachedPaper(raw),ja=view==='ja',badges=node('div','badges');
  for(const c of p.categories.slice(0,5)) badges.append(node('span','badge'+(c===p.primary?'':' secondary'),c));
  badges.append(node('span','paper-id',p.id+' · v'+p.version));content.append(badges);
  const title=node('h2','math',ja&&p.title_ja?p.title_ja:p.title);title.lang=ja&&p.title_ja?'ja':'en';content.append(title);
  if(ja&&p.title_ja){const original=node('p','original-title math',p.title);original.lang='en';content.append(original);}
  content.append(node('p','authors',p.authors.slice(0,5).join(', ')+(p.authors.length>5?` ほか ${p.authors.length-5} 名`:'')));
  content.append(node('p','details',`${dateLabel(p.published)} 投稿${p.comment?' · '+p.comment:''}`));
  const label=node('div','abstract-label');label.append(node('span','', 'ABSTRACT'));
  label.append(node('span','translation-label',ja&&p.abstract_ja?provider(p.abstract_translator):(ja?'未翻訳 · 原文':'原文')));content.append(label);
  const abstract=node('p','abstract math',ja&&p.abstract_ja?p.abstract_ja:p.abstract);abstract.lang=ja&&p.abstract_ja?'ja':'en';content.append(abstract);
  $('arxiv-link').href=p.abs_url;$('pdf-link').href=p.pdf_url;
  $('local-translate').hidden=!('Translator'in globalThis);$('local-translate').disabled=translationBusy;
  typeset(content);
}
async function load(){
  $('refresh').disabled=true;
  try{
    const response=await fetch('./data/latest.json',{cache:'no-store',signal:AbortSignal.timeout(15000)});
    if(!response.ok)throw new Error('HTTP '+response.status);
    const payload=await response.json();
    if(payload.schema_version!==1||!Array.isArray(payload.papers))throw new Error('Invalid digest');
    doc=payload;all=normalizePapers(payload.papers);loaded=true;
    const previous=$('category').value||preferences.category||'';
    $('category').replaceChildren(new Option('すべて',''));
    for(const c of (Array.isArray(doc.categories)?doc.categories:[]))if(typeof c==='string')$('category').append(new Option(c,c));
    $('category').value=[...$('category').options].some(o=>o.value===previous)?previous:'';
    $('sync').textContent=doc.generated_at?'最終取得 '+new Date(doc.generated_at).toLocaleString('ja-JP',{timeZone:'Asia/Tokyo',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})+' JST':'初回の自動取得を待っています。';
    $('coverage').textContent=all.length?`日本語訳：タイトル ${all.filter(p=>p.title_ja).length} / ${all.length} 件 · アブストラクト ${all.filter(p=>p.abstract_ja).length} / ${all.length} 件`:'';
    const warnings=[];
    if(doc.truncated)warnings.push('取得上限に達しています。期間内のすべての論文を含まない可能性があります。');
    if(doc.generated_at && Date.now()-new Date(doc.generated_at).valueOf()>3*86400000)warnings.push('最終取得から3日以上経過しています。Actionsの実行状況をご確認ください。');
    if(['engine_error','initializing','pending'].includes(doc.translation?.status)&&all.length)warnings.push('事前翻訳が完了していません。未翻訳の論文は原文で利用できます。');
    if(doc.translation?.engine==='argos'&&all.length)warnings.push('Argosの参考訳には物理用語の誤訳が見られます。初期表示は原文とし、訳は補助的に表示できます。');
    $('notice').textContent=warnings.join(' ');$('notice').hidden=!warnings.length;
    history=[];rebuild();
  }catch{
    $('notice').hidden=false;$('notice').textContent='配信データを読み込めませんでした。ネット接続とGitHub Actionsの実行結果をご確認ください。保存リストは引き続き利用できます。';render();
  }finally{$('refresh').disabled=false;}
}
function choose(keep){
  const p=queue[0];if(!p||locked)return;
  locked=true;history.push({paper:p,wasRead:readSet.has(p.id),previousSaved:saved.get(p.id)});
  readSet.add(p.id);if(keep)saved.set(p.id,cachedPaper(p));persist();
  $('card').classList.add('leaving');$('card').style.transform=`translateX(${keep?70:-70}px) rotate(${keep?3:-3}deg)`;
  $('skip').disabled=$('keep').disabled=$('undo').disabled=true;
  setTimeout(()=>{queue=queue.filter(x=>x.id!==p.id);locked=false;render();},180);
}
function undo(){if(locked||!history.length)return;const last=history.pop();if(!last.wasRead)readSet.delete(last.paper.id);if(last.previousSaved)saved.set(last.paper.id,last.previousSaved);else saved.delete(last.paper.id);persist();queue=[last.paper,...queue.filter(p=>p.id!==last.paper.id)];render();notify('直前の操作を取り消しました。');}
$('keep').addEventListener('click',()=>choose(true));$('skip').addEventListener('click',()=>choose(false));$('undo').addEventListener('click',undo);
$('refresh').addEventListener('click',load);
$('category').addEventListener('change',()=>{if(locked)return;history=[];savePreferences();rebuild();});$('search').addEventListener('input',()=>{if(!locked)rebuild();});
$('language').addEventListener('click',()=>{if(locked)return;view=view==='ja'?'en':'ja';savePreferences();render();});
$('show-read').addEventListener('change',()=>{history=[];savePreferences();rebuild();});
function showSaved(){renderSaved();$('saved-dialog').showModal();}
$('saved-open').addEventListener('click',showSaved);
$('settings-open').addEventListener('click',()=>{$('settings-dialog').showModal();});
for(const b of document.querySelectorAll('[data-close]'))b.addEventListener('click',()=>$(b.dataset.close).close());
$('empty-action').addEventListener('click',()=>all.length?showSaved():load());
$('browser-info').textContent='Translator'in globalThis?'このブラウザは端末内翻訳に対応しています。初回はモデルのダウンロードが必要な場合があります。':'このブラウザには端末内翻訳APIがありません。生成済みの訳はそのまま読めます。未翻訳のものはarXivを開いて、ブラウザのページ翻訳も利用できます。';
function renderSaved(){
  const list=$('saved-list');clearMath(list);list.replaceChildren();const items=[...saved.values()].reverse().filter(p=>matches(p,'',$('saved-search').value));
  if(!items.length)list.append(node('p','muted','この条件の保存論文はありません。'));
  for(const p of items){const item=node('article','saved-item');item.append(node('h3','math',view==='ja'&&p.title_ja?p.title_ja:p.title));item.append(node('p','',p.authors.slice(0,3).join(', ')));item.append(node('p','muted',p.id+' · '+p.primary));const links=node('div','saved-links');links.append(link('arXiv ↗',p.abs_url),link('PDF ↗',p.pdf_url));const remove=node('button','text-button','保存を外す');remove.addEventListener('click',()=>{saved.delete(p.id);history=[];persist();renderSaved();updateMetrics();notify('保存を外しました。既読の記録は残ります。');});links.append(remove);item.append(links);list.append(item);}typeset(list);
}
$('saved-search').addEventListener('input',renderSaved);
function download(name,contents,type='text/plain;charset=utf-8'){const url=URL.createObjectURL(new Blob([contents],{type}));const a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),2000);}
function backup(){download('hep-match-backup-'+new Date().toISOString().slice(0,10)+'.json',JSON.stringify({schema_version:1,exported_at:new Date().toISOString(),read:[...readSet],saved:[...saved.values()]},null,2),'application/json');}
$('backup-export').addEventListener('click',backup);$('saved-backup').addEventListener('click',backup);
$('backup-import').addEventListener('click',()=>$('backup-file').click());
$('backup-file').addEventListener('change',async event=>{const file=event.target.files[0];if(!file)return;try{if(file.size>8*1024*1024)throw new Error('8MB以下のバックアップを選んでください。');const merged=mergeBackup({read:[...readSet],saved:[...saved.values()]},JSON.parse(await file.text()));readSet=new Set(merged.read);saved=new Map(merged.saved.map(p=>[p.id,p]));history=[];persist();rebuild();notify('バックアップを追加しました。');}catch(error){notify(error.message||'バックアップを読み込めませんでした。');}finally{event.target.value='';}});
$('export-md').addEventListener('click',()=>download('hep-match-saved.md',markdown([...saved.values()])));
$('export-bib').addEventListener('click',()=>download('hep-match-saved.bib',bibtex([...saved.values()])));
$('copy-abstract').addEventListener('click',async()=>{const p=queue[0];if(!p)return;try{await navigator.clipboard.writeText(p.title+'\n\n'+p.abstract+'\n\n'+p.abs_url);notify('原文をコピーしました。');}catch{notify('コピーできませんでした。カード内の文章を選択してコピーしてください。');}});
let translatorPromise=null;
$('local-translate').addEventListener('click',async()=>{
  const p=queue[0];if(!p||translationBusy||!('Translator'in globalThis))return;
  translationBusy=true;$('local-translate').disabled=true;notify('端末内で翻訳します。初回は言語モデルを取得する場合があります。');
  try{
    // Create during the user gesture; awaiting a feature check first can lose activation.
    if(!translatorPromise)translatorPromise=Translator.create({sourceLanguage:'en',targetLanguage:'ja',monitor(m){m.addEventListener('downloadprogress',e=>{$('local-translate').textContent=`モデル取得 ${Math.round(e.loaded*100)}%`;});}});
    const translator=await translatorPromise;
    const title=await safeTranslate(p.title,t=>translator.translate(t));
    const abstract=await safeTranslate(p.abstract,t=>translator.translate(t));
    localTranslations[p.id]={source:p.title+'\n'+p.abstract,title,abstract};
    const ids=Object.keys(localTranslations);for(const id of ids.slice(0,Math.max(0,ids.length-300)))delete localTranslations[id];
    write('translations',localTranslations);if(saved.has(p.id)){saved.set(p.id,cachedPaper(p));persist();}
    if(queue[0]?.id===p.id){view='ja';savePreferences();render();}notify('参考訳を表示しました。');
  }catch{translatorPromise=null;notify('端末内翻訳を利用できませんでした。原文か事前翻訳をご利用ください。');}
  finally{translationBusy=false;$('local-translate').disabled=false;$('local-translate').textContent='この端末で翻訳';}
});
let drag=null;
$('card').addEventListener('pointerdown',event=>{if(locked||!queue.length||event.isPrimary===false||event.button!==0||event.target.closest('a,button,input,select'))return;drag={id:event.pointerId,x:event.clientX,y:event.clientY,mode:'pending',dx:0};});
$('card').addEventListener('pointermove',event=>{if(!drag||drag.id!==event.pointerId)return;const dx=event.clientX-drag.x,dy=event.clientY-drag.y;if(drag.mode==='pending'){if(Math.abs(dy)>10&&Math.abs(dy)>=Math.abs(dx)){drag=null;return;}if(Math.abs(dx)>12&&Math.abs(dx)>1.25*Math.abs(dy)){drag.mode='swipe';$('card').setPointerCapture(event.pointerId);$('card').classList.add('dragging');}}
  if(drag?.mode==='swipe'){drag.dx=dx;$('card').style.transform=`translateX(${Math.max(-130,Math.min(130,dx))}px) rotate(${dx/45}deg)`;}});
function endDrag(event,cancel=false){if(!drag||event.pointerId!==drag.id)return;const old=drag;drag=null;try{if($('card').hasPointerCapture(event.pointerId))$('card').releasePointerCapture(event.pointerId);}catch{}$('card').classList.remove('dragging');$('card').style.transform='';if(!cancel&&old.mode==='swipe'&&Math.abs(old.dx)>95)choose(old.dx>0);}
$('card').addEventListener('pointerup',e=>endDrag(e));$('card').addEventListener('pointercancel',e=>endDrag(e,true));
document.addEventListener('keydown',event=>{if(event.repeat||locked||document.querySelector('dialog[open]')||event.target.closest('input,textarea,select,button,[contenteditable=true]')||String(window.getSelection()).length)return;if(event.key==='ArrowRight'){event.preventDefault();choose(true);}if(event.key==='ArrowLeft'){event.preventDefault();choose(false);}if(event.key==='z'&&(event.ctrlKey||event.metaKey)){event.preventDefault();undo();}});
if('serviceWorker'in navigator)navigator.serviceWorker.register('./sw.js').catch(()=>{});
updateMetrics();load();
