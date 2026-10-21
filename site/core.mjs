// Pure helpers shared by the UI and Node tests. No network or storage access.
const ID = /^(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?\/\d{7})$/;
const CAT = /^[a-z-]+(?:\.[A-Z]{2})?$/;
const text = (v, max=30000) => typeof v === 'string' ? v.slice(0,max) : '';
export const mathPattern = () => /((?<!\\)\$\$[\s\S]*?(?<!\\)\$\$|(?<!\\)\$(?!\$)[^$\n]*?(?<!\\)\$|\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\])/g;
export const mathParts = value => value.split(mathPattern());
export function paper(raw) {
  if (!raw || typeof raw !== 'object' || !ID.test(raw.id || '') || !text(raw.title)) return null;
  const primary = CAT.test(raw.primary || '') ? raw.primary : '';
  const categories = [...new Set([primary,...(Array.isArray(raw.categories)? raw.categories : [])].filter(x=>typeof x==='string' && CAT.test(x)))];
  const p = {id:raw.id, version:Number.isInteger(raw.version)&&raw.version>0?raw.version:1,
    title:text(raw.title,3000), abstract:text(raw.abstract),
    authors:(Array.isArray(raw.authors)?raw.authors:[]).slice(0,500).map(x=>text(x,300)),
    primary,categories,published:text(raw.published,32),updated:text(raw.updated,32),comment:text(raw.comment,3000),
    abs_url:'https://arxiv.org/abs/'+raw.id, pdf_url:'https://arxiv.org/pdf/'+raw.id};
  for(const field of ['title','abstract']) {
    p[field+'_ja']=text(raw[field+'_ja']);
    p[field+'_translator']=text(raw[field+'_translator'],40);
  }
  return p;
}
export function normalizePapers(values) {
  const unique=new Map();
  for(const raw of (Array.isArray(values)?values:[]).slice(0,10000)) {
    const p=paper(raw); if(p && (!unique.has(p.id)||unique.get(p.id).version<=p.version)) unique.set(p.id,p);
  }
  return [...unique.values()];
}
export function matches(p, category='', query='') {
  if(category && !p.categories.includes(category)) return false;
  const haystack=[p.id,p.title,p.title_ja,p.abstract,p.abstract_ja,...p.authors].join(' ').toLocaleLowerCase();
  return query.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean).every(term=>haystack.includes(term));
}
export function mergeBackup(current, incoming) {
  if(!incoming || incoming.schema_version!==1 || !Array.isArray(incoming.saved) || !Array.isArray(incoming.read)) throw new Error('HEP Matchのバックアップではありません。');
  const saved=normalizePapers([...(current.saved||[]),...incoming.saved]);
  const read=[...new Set([...(current.read||[]),...incoming.read,...saved.map(p=>p.id)].filter(x=>typeof x==='string'&&ID.test(x)))].slice(-50000);
  return {schema_version:1,saved,read};
}
export function markdown(papers) {
  return papers.map(p=>`## ${p.title}\n\n${p.authors.join(', ')}\n\narXiv:${p.id} [${p.primary}]\n\n${p.abs_url}\n`).join('\n');
}
function bibEscape(value) {
  return mathParts(value).map((part,i)=>i%2?part:part.replace(/[\\{}%&#_]/g,c=>({'\\':'\\textbackslash{}','{':'\\{','}':'\\}','%':'\\%','&':'\\&','#':'\\#','_':'\\_'}[c]))).join('');
}
export function bibtex(papers) {
  return papers.map(p=>`@misc{arxiv${p.id.replace(/[^a-zA-Z0-9]/g,'')},\n  title = {{${bibEscape(p.title)}}},\n  author = {${p.authors.map(bibEscape).join(' and ')}},\n  year = {${/^\d{4}/.test(p.published)?p.published.slice(0,4):''}},\n  eprint = {${p.id}},\n  archivePrefix = {arXiv},\n  primaryClass = {${p.primary}},\n  url = {${p.abs_url}}\n}\n`).join('\n');
}
export async function safeTranslate(value, translate) {
  const parts=mathParts(value), result=[];
  for(let i=0;i<parts.length;i++) {
    const part=parts[i];
    if(i%2 || !part.trim()) { result.push(part); continue; }
    const leading=part.match(/^\s*/)[0], trailing=part.match(/\s*$/)[0];
    const translated=await translate(part.trim());
    if(typeof translated!=='string'||!translated.trim()||translated.length>Math.max(200,part.length*8)) throw new Error('翻訳結果を確認できませんでした。');
    result.push(leading+translated.trim()+trailing);
  }
  return result.join('');
}
