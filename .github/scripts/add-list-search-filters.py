from pathlib import Path

p = Path('public/index.html')
s = p.read_text(encoding='utf-8')

marker = 'const LIST_SEARCH_CONFIG = {'
if marker in s:
    raise SystemExit('Filtri ricerca già presenti')

helper = r'''
const LIST_SEARCH_STATE={};
const LIST_SEARCH_CONFIG={
  partite:{placeholder:'Cerca per partita, formulario, produttore, CER, peso o stato…'},
  uscite:{placeholder:'Cerca per documento, destinatario, partita, data o peso…'},
  rimanenze:{placeholder:'Cerca per partita, produttore, CER o quantità…'},
  produttori:{placeholder:'Cerca produttore, P.IVA, indirizzo o altro dato…'},
  trasportatori:{placeholder:'Cerca trasportatore, P.IVA, albo o altro dato…'},
  dafornitore:{placeholder:'Cerca tra le voci da definire…'}
};
function normalizeListSearch(v){
  return String(v??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/\s+/g,' ').trim();
}
function listSearchKey(view){ return view+'|'+YEAR; }
function listSearchRows(root){
  return [...root.querySelectorAll('table tbody tr')].filter(tr=>!tr.querySelector('td[colspan]'));
}
function applyListSearchFilter(view,root){
  const key=listSearchKey(view), query=normalizeListSearch(LIST_SEARCH_STATE[key]||'');
  const terms=query.split(' ').filter(Boolean);
  const rows=listSearchRows(root);
  let visible=0;
  rows.forEach(tr=>{
    const text=normalizeListSearch(tr.textContent||'');
    const ok=!terms.length||terms.every(t=>text.includes(t));
    tr.style.display=ok?'':'none';
    if(ok)visible++;
  });
  const count=root.querySelector('[data-list-search-count]');
  if(count) count.textContent=terms.length?`${visible} di ${rows.length} righe`:`${rows.length} righe`;
  const clear=root.querySelector('[data-list-search-clear]');
  if(clear) clear.style.visibility=terms.length?'visible':'hidden';
}
function setListSearchFilter(view,value){
  LIST_SEARCH_STATE[listSearchKey(view)]=value||'';
  const root=document.getElementById('view');
  if(root)applyListSearchFilter(view,root);
}
function clearListSearchFilter(view){
  LIST_SEARCH_STATE[listSearchKey(view)]='';
  const root=document.getElementById('view');
  if(!root)return;
  const input=root.querySelector('[data-list-search-input]');
  if(input){input.value='';input.focus();}
  applyListSearchFilter(view,root);
}
function installListSearchFilter(view,root){
  const cfg=LIST_SEARCH_CONFIG[view];
  if(!cfg||!root.querySelector('table tbody'))return;
  const key=listSearchKey(view), current=LIST_SEARCH_STATE[key]||'';
  const bar=document.createElement('div');
  bar.className='panel';
  bar.style.marginBottom='14px';
  bar.innerHTML=`<div class="panel-b" style="padding:10px 14px;display:flex;align-items:center;gap:10px;flex-wrap:wrap"><div style="position:relative;flex:1;min-width:240px"><input class="inp" data-list-search-input value="${esc(current)}" placeholder="${esc(cfg.placeholder)}" aria-label="Ricerca" style="width:100%;padding-right:34px"><span style="position:absolute;right:11px;top:50%;transform:translateY(-50%);color:var(--muted);pointer-events:none">⌕</span></div><span class="mini" data-list-search-count></span><button class="btn ghost sm" data-list-search-clear onclick="clearListSearchFilter('${view}')">Azzera</button></div>`;
  const input=bar.querySelector('[data-list-search-input]');
  input.addEventListener('input',e=>setListSearchFilter(view,e.target.value));
  root.insertBefore(bar,root.firstChild);
  applyListSearchFilter(view,root);
}
'''

render_token = 'function render(){'
if render_token not in s:
    raise SystemExit('Funzione render non trovata')
s = s.replace(render_token, helper + '\n' + render_token, 1)

old = "  el.innerHTML = fn();\n  if(el._after){ const a=el._after; el._after=null; a(); }"
new = "  el.innerHTML = fn();\n  installListSearchFilter(v,el);\n  if(el._after){ const a=el._after; el._after=null; a(); }"
if old not in s:
    raise SystemExit('Punto di aggancio filtri non trovato nel render')
s = s.replace(old, new, 1)

for required in [
    'const LIST_SEARCH_CONFIG={',
    'function installListSearchFilter(view,root)',
    'function applyListSearchFilter(view,root)',
    'installListSearchFilter(v,el);',
    "partite:{placeholder:",
    "uscite:{placeholder:",
    "rimanenze:{placeholder:",
    "produttori:{placeholder:",
    "trasportatori:{placeholder:"
]:
    if required not in s:
        raise SystemExit('Verifica filtri fallita: '+required)

p.write_text(s, encoding='utf-8')
