from pathlib import Path
import re, subprocess, tempfile

p=Path('public/index.html')
text=p.read_text(encoding='utf-8')
pattern=r"function anagView\(store,titolo,kind\)\{.*?\n\}\n\nfunction emptyState"
m=re.search(pattern,text,re.S)
if not m:
    raise SystemExit('anagView non trovato')
replacement=r'''function anagView(store,titolo,kind){
  const rows=Object.values(DB[store]);
  const canCreate=hasPermission(store,'create');
  const canDelete=hasPermission(store,'delete');
  return `<div class="panel"><div class="panel-h"><h3>${titolo}</h3><span class="cnt">${rows.length}</span><span class="sp"></span>
    ${canCreate?`<button class="btn primary sm" onclick="openAnag('${store}')">+ Nuovo</button>`:''}</div>
  ${rows.length?`<table><thead><tr><th>Ragione sociale</th><th>P.IVA</th><th>Sede legale</th>${store==='trasportatori'?'<th>Tipo</th>':''}<th>VIES</th>${canDelete?'<th></th>':''}</tr></thead><tbody>
  ${rows.map(r=>`<tr><td style="font-weight:500">${esc(r.ragioneSociale)}</td><td class="mono">${esc(r.piva||'—')}</td>
    <td>${esc(r.indirizzo||'—')}</td>${store==='trasportatori'?`<td>${r.interno?'<span class="tag grey">interno</span>':'<span class="tag blue">esterno</span>'}</td>`:''}
    <td>${r.vies?'<span class="tag green">verificata</span>':'<span class="tag grey">—</span>'}</td>${canDelete?`<td style="text-align:right"><button class="btn danger sm" onclick="deleteAnag('${store}','${r.id}')">Elimina</button></td>`:''}</tr>`).join('')}
  </tbody></table>`:emptyState('Nessuna anagrafica','Aggiungi il primo '+kind+'.')}</div>`;
}
function deleteAnag(store,id){
  if(!requirePermission(store,'delete'))return;
  const record=DB[store]?.[id];
  if(!record){toast('Anagrafica non trovata','err');return;}
  if(store==='produttori'){
    const linked=Object.values(DB.partite).filter(p=>p.produttoreId===id);
    if(linked.length){toast('Impossibile eliminare: produttore collegato a '+linked.length+' partite','err');return;}
  }
  if(store==='trasportatori'){
    const linked=Object.values(DB.documenti).filter(d=>d.trasportatoreId===id);
    if(linked.length){toast('Impossibile eliminare: trasportatore collegato a '+linked.length+' documenti','err');return;}
  }
  if(!window.confirm('Eliminare definitivamente '+(store==='produttori'?'questo produttore':'questo trasportatore')+'?'))return;
  const snapshot=JSON.parse(JSON.stringify(record));
  delete DB[store][id];
  if(!save()){DB[store][id]=snapshot;return;}
  render();toast('Anagrafica eliminata');
}

function emptyState'''
text=text[:m.start()]+replacement+text[m.end():]
p.write_text(text,encoding='utf-8')

# Check classic script syntax only (module block may contain imports).
scripts=re.findall(r'<script([^>]*)>(.*?)</script>',text,re.S)
classic='\n'.join(body for attrs,body in scripts if 'type="module"' not in attrs and "type='module'" not in attrs)
with tempfile.NamedTemporaryFile('w',suffix='.js',delete=False,encoding='utf-8') as f:
    f.write(classic)
    name=f.name
subprocess.run(['node','--check',name],check=True)
