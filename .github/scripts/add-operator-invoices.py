from pathlib import Path
import re

path = Path('public/index.html')
s = path.read_text(encoding='utf-8')

new_detail = r'''function viewPartitaDetailOperational(){
  const p=DB.partite[ROUTE.id];if(!p)return emptyState('Partita non trovata','');
  const prod=DB.produttori[p.produttoreId]||{},lotti=lottiDisponibili(p),g=giacenza(p),editable=canEditPartita(p);
  const uscite=[];Object.values(DB.documenti).forEach(d=>(d.righe||[]).forEach(r=>{if(r.partitaId===p.id)uscite.push({d,r});}));
  return `<button class="btn ghost sm" onclick="go('partite')" style="margin-bottom:14px">← Registro partite</button>
  <div class="det-head"><div class="idbox"><div class="n">${p.num}<span class="r">-Raee</span></div><div class="y">${p.anno} · Mozzanica</div></div><div class="meta"><div class="prod">${esc(prod.ragioneSociale||'—')}</div><div class="row"><span>CER <b>${cerLabel(p.cer)}</b></span><span>Ingresso <b>${kg(p.kgIngresso)}</b></span><span>Data <b>${dfmt(p.dataIngresso)}</b></span><span>Giacenza <b>${kg(g)}</b></span></div></div></div>
  <div class="det-grid"><div>
    <div class="sec"><div class="sec-h"><h4>Fatture d'acquisto</h4><span class="sp"></span>${hasPermission('partite','update')?`<button class="btn sm" onclick="openOperationalInvoice('acquisto','${p.id}')">+ Carica fattura</button>`:''}</div><div class="sec-b pad0">${renderOperationalInvoices('acquisto',p.id)}</div></div>
    <div class="sec"><div class="sec-h"><h4>Lavorazioni interne</h4><span class="sp"></span>${hasPermission('partite','update')?`<button class="btn sm" onclick="openLavorazione('${p.id}')">+ Lavorazione parziale</button>`:''}</div><div class="sec-b pad0">${(p.lavorazioni||[]).length?`<table><thead><tr><th>Tipo</th><th>Data</th><th>Kg lavorati</th><th>Risultato</th><th></th></tr></thead><tbody>${p.lavorazioni.map(l=>`<tr><td>${l.tipo==='trit'?'Triturazione':'Selezione e cernita'}</td><td>${dfmt(l.data)}</td><td class="num">${kg(l.kgLavorati||l.pesoPrima)}</td><td>${l.frazioni?.length?l.frazioni.map(fr=>`${esc(fr.label)} ${kg(fr.kg)}`).join('<br>'):kg(l.pesoDopo)}</td><td>${hasPermission('partite','update')?`<button class="btn ghost sm" onclick="delLavorazione('${p.id}','${l.id}')">✕</button>`:''}</td></tr>`).join('')}</tbody></table>`:emptyState('Nessuna lavorazione','')}</div></div>
    <div class="sec"><div class="sec-h"><h4>Uscite verso impianti esterni</h4><span class="sp"></span>${hasPermission('uscite','create')?`<button class="btn sm" onclick="openDocumento(null,'${p.id}')">+ Documento di uscita</button>`:''}</div><div class="sec-b pad0">${uscite.length?`<table><thead><tr><th>Documento</th><th>Data</th><th>Destinatario</th><th>Kg</th><th>Tipo</th></tr></thead><tbody>${uscite.map(({d,r})=>`<tr class="clk" onclick="openDocView('${d.id}')"><td><span class="mono">${esc(d.numero||'')}</span></td><td>${dfmt(d.data)}</td><td>${esc(d.destinatario||'—')}</td><td class="num">${kg(r.kg)}</td><td>${r.saldo?'<span class="tag green">saldo</span>':'<span class="tag brass">parziale</span>'}</td></tr>`).join('')}</tbody></table>`:emptyState('Nessuna uscita','')}</div></div>
  </div><div>
    <div class="sec"><div class="sec-h"><h4>Disponibilità</h4></div><div class="sec-b"><div class="kv"><span class="k">Kg ingresso</span><span class="v">${kg(p.kgIngresso)}</span></div><div class="kv"><span class="k">Kg usciti</span><span class="v">${kg(kgUsciti(p))}</span></div><div class="kv"><span class="k">Giacenza</span><span class="v">${kg(g)}</span></div>${lotti.filter(l=>l.kg>.01).map(l=>`<div class="kv"><span class="k">${esc(l.label)}</span><span class="v">${kg(l.kg)}</span></div>`).join('')}</div></div>
    <div class="sec"><div class="sec-h"><h4>Ingresso</h4><span class="sp"></span>${editable&&hasPermission('partite','update')?`<button class="btn sm" onclick="openEditPartita('${p.id}')">Modifica</button>`:''}${hasPermission('partite','delete')?`<button class="btn danger sm" onclick="deletePartita('${p.id}')">Elimina</button>`:''}</div><div class="sec-b"><div class="kv"><span class="k">Produttore</span><span class="v">${esc(prod.ragioneSociale||'—')}</span></div>${(p.formulariIngresso||[]).map(f=>`<div class="kv"><span class="k">Formulario</span><span class="v mono">${esc(f.numero||'—')} · ${dfmt(f.data)}</span></div>`).join('')}</div></div>
  </div></div>`;
}
'''

pat_detail = r"function viewPartitaDetailOperational\(\)\{.*?\n\}\n(?=function viewUsciteOperational\(\)\{)"
s, n = re.subn(pat_detail, new_detail, s, count=1, flags=re.S)
if n != 1:
    raise SystemExit(f'viewPartitaDetailOperational replacement failed: {n}')

new_doc_and_helpers = r'''function openDocViewOperational(id){
  const d=DB.documenti[id];if(!d)return;
  const rows=(d.righe||[]).map(r=>{const p=DB.partite[r.partitaId];return `<tr><td>${p?p.num+'-Raee':'?'}</td><td>${esc(r.lotto||'tal quale')}</td><td class="num">${kg(r.kg)}</td><td>${r.saldo?'<span class="tag green">saldo</span>':'<span class="tag brass">parziale</span>'}</td></tr>`;}).join('');
  modal(`<div class="modal wide"><div class="modal-h"><h3>${d.tipo==='fir'?'FIR':'Annex VII'} · <span class="mono">${esc(d.numero||'')}</span></h3><button class="x" onclick="closeModal()">×</button></div><div class="modal-b"><div class="kv"><span class="k">Data</span><span class="v">${dfmt(d.data)}</span></div><div class="kv"><span class="k">Destinatario</span><span class="v">${esc(d.destinatario||'—')}</span></div>${d.trasportatoreId?`<div class="kv"><span class="k">Trasportatore</span><span class="v">${esc(DB.trasportatori[d.trasportatoreId]?.ragioneSociale||'—')}</span></div>`:''}<div class="sec" style="margin-top:16px"><div class="sec-h"><h4>Fatture di vendita</h4><span class="sp"></span>${hasPermission('uscite','update')?`<button class="btn sm" onclick="openOperationalInvoice('vendita','${d.id}')">+ Carica fattura</button>`:''}</div><div class="sec-b pad0">${renderOperationalInvoices('vendita',d.id)}</div></div><table style="margin-top:14px"><thead><tr><th>Partita</th><th>Lotto</th><th>Kg</th><th>Tipo</th></tr></thead><tbody>${rows}</tbody></table></div><div class="modal-f">${hasPermission('uscite','delete')?`<button class="btn danger" onclick="deleteDocumento('${id}')">Elimina documento</button>`:''}<span style="flex:1"></span><button class="btn" onclick="closeModal()">Chiudi</button></div></div>`);
}

function operationalInvoiceRecord(kind,id){
  return kind==='acquisto' ? DB.partite[id] : DB.documenti[id];
}
function operationalInvoiceKey(kind){
  return kind==='acquisto' ? 'fattureDocumentaliAcquisto' : 'fattureDocumentaliVendita';
}
function renderOperationalInvoices(kind,id){
  const rec=operationalInvoiceRecord(kind,id);
  const items=(rec&&rec[operationalInvoiceKey(kind)])||[];
  if(!items.length) return `<div class="empty"><div class="big">Nessuna fattura caricata</div>Il file PDF può essere associato senza mostrare importi o altri dati economici.</div>`;
  return `<table><thead><tr><th>N. fattura</th><th>Data</th><th>PDF</th></tr></thead><tbody>${items.map(f=>`<tr><td class="mono">${esc(f.numero||'—')}</td><td>${dfmt(f.data)}</td><td>${f.url?`<a class="pill-file" href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.name||'Apri PDF')}</a>`:'<span class="mini">file non disponibile</span>'}</td></tr>`).join('')}</tbody></table>`;
}
function openOperationalInvoice(kind,id){
  const section=kind==='acquisto'?'partite':'uscite';
  if(!requirePermission(section,'update'))return;
  const rec=operationalInvoiceRecord(kind,id);if(!rec){toast('Elemento non trovato','err');return;}
  modal(`<div class="modal"><div class="modal-h"><h3>${kind==='acquisto'?"Fattura d'acquisto":'Fattura di vendita'}</h3><button class="x" onclick="closeModal()">×</button></div><div class="modal-b"><div class="row2"><div class="field"><label>N. fattura <span class="req">*</span></label><input class="inp mono" id="ofi_num"></div><div class="field"><label>Data <span class="req">*</span></label><input class="inp" type="date" id="ofi_data"></div></div><div class="field"><label>PDF fattura <span class="req">*</span></label><input class="inp" type="file" id="ofi_file" accept="application/pdf,.pdf"><div class="mini" style="margin-top:6px">Solo PDF, massimo 15 MB. L'importo non viene richiesto né mostrato.</div></div></div><div class="modal-f"><button class="btn" onclick="closeModal()">Annulla</button><span style="flex:1"></span><button class="btn primary" onclick="saveOperationalInvoice('${kind}','${id}')">Carica</button></div></div>`);
}
async function saveOperationalInvoice(kind,id){
  const section=kind==='acquisto'?'partite':'uscite';
  if(!requirePermission(section,'update'))return;
  const rec=operationalInvoiceRecord(kind,id);if(!rec){toast('Elemento non trovato','err');return;}
  const numero=(document.getElementById('ofi_num')?.value||'').trim();
  const data=document.getElementById('ofi_data')?.value||'';
  const file=document.getElementById('ofi_file')?.files?.[0];
  if(!numero||!data||!file){toast('Inserisci numero, data e PDF della fattura','err');return;}
  if(!(file.type==='application/pdf'||file.name.toLowerCase().endsWith('.pdf'))){toast('È consentito solo un file PDF','err');return;}
  if(file.size>15*1024*1024){toast('Il PDF supera il limite di 15 MB','err');return;}
  if(!CLOUD.user||!window.firebaseBridge){toast('Accedi a Firebase per caricare il PDF','err');return;}
  try{
    const safe=file.name.replace(/[^a-zA-Z0-9._-]+/g,'_');
    const folder=kind==='acquisto'?'fatture-acquisto':'fatture-vendita';
    const path=`registro-mozzanica/${folder}/${id}/${Date.now()}_${safe}`;
    const url=await window.firebaseBridge.uploadFile(file,path);
    const key=operationalInvoiceKey(kind);
    const before=JSON.parse(JSON.stringify(rec[key]||[]));
    rec[key]=[...(rec[key]||[]),{id:'ofi_'+Date.now().toString(36),numero,data,name:file.name,url,path,uploadedAt:Date.now(),uploadedBy:CLOUD.user.uid||''}];
    if(!save()){rec[key]=before;toast('Impossibile salvare la fattura','err');return;}
    closeModal();
    if(kind==='acquisto') render(); else openDocViewOperational(id);
    toast('Fattura caricata');
  }catch(e){
    console.error(e);
    toast('Caricamento PDF non riuscito. Verifica le regole Storage.','err');
  }
}

/* ---------- DASHBOARD ---------- */'''
pat_doc = r"function openDocViewOperational\(id\)\{.*?\n\}\n\n/\* ---------- DASHBOARD ---------- \*/"
s, n = re.subn(pat_doc, new_doc_and_helpers, s, count=1, flags=re.S)
if n != 1:
    raise SystemExit(f'openDocViewOperational replacement failed: {n}')

path.write_text(s, encoding='utf-8')
print('operator invoice UI patched')
