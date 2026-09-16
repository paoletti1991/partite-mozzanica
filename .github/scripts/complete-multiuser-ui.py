from pathlib import Path
import re, subprocess, tempfile
p=Path('public/index.html')
text=p.read_text(encoding='utf-8')

def rep(old,new,label):
    global text
    n=text.count(old)
    if n!=1: raise RuntimeError(f'{label}: expected 1, found {n}')
    text=text.replace(old,new,1)

def insert_guard(signature,guard,label):
    global text
    n=text.count(signature)
    if n!=1: raise RuntimeError(f'{label}: expected 1 signature, found {n}')
    text=text.replace(signature,signature+'\n  '+guard,1)

# Local mode remains unrestricted; authenticated cloud users use profile permissions.
rep("""function hasPermission(section,action='read'){
  if(isAdmin()) return true;""","""function hasPermission(section,action='read'){
  if(!FB_ON) return true;
  if(isAdmin()) return true;""",'local permission compatibility')
rep("""  return CLOUD.profile.permissions?.[section]?.[action]===true;
}
  function canViewSection(view){""","""  return CLOUD.profile.permissions?.[section]?.[action]===true;
}
function requirePermission(section,action){
  if(hasPermission(section,action)) return true;
  toast('Non hai i permessi per questa operazione','err');
  return false;
}
  function canViewSection(view){""",'requirePermission helper')

# Operational-only renderers for users without economics.read.
ops=r'''
function viewDashOperational(){
  const ps=Object.values(DB.partite).filter(p=>p.anno===YEAR);
  const docs=Object.values(DB.documenti).filter(d=>(d.righe||[]).some(r=>DB.partite[r.partitaId]?.anno===YEAR));
  const kgIn=ps.reduce((s,p)=>s+(+p.kgIngresso||0),0);
  const kgOut=ps.reduce((s,p)=>s+kgUsciti(p),0);
  const stock=ps.reduce((s,p)=>s+giacenza(p),0);
  const worked=ps.filter(p=>(p.lavorazioni||[]).length).length;
  const hazardous=ps.filter(p=>giacenza(p)>0.01&&cerByCode[p.cer]?.hazard);
  const recent=[...ps].sort((a,b)=>b.num-a.num).slice(0,8);
  return `<div class="dash-hero"><div class="intro"><div class="eyebrow">Mozzanica · ${YEAR}</div><h2>Panoramica operativa</h2><div class="desc">Dati di magazzino e movimentazione · valori economici non disponibili per questo profilo</div><div class="dash-actions">${hasPermission('partite','create')?'<button class="btn primary sm" onclick="openPartita()">+ Nuova partita</button>':''}${hasPermission('uscite','create')?'<button class="btn ghost-light sm" onclick="openDocumento()">+ Documento uscita</button>':''}</div></div></div>
  <div class="kpis dash-kpis">
    <div class="kpi accent"><div class="lab">Partite in ingresso</div><div class="val">${ps.length}</div><div class="sub">${kg(kgIn)} complessivi</div></div>
    <div class="kpi"><div class="lab">Materiale uscito</div><div class="val">${kg(kgOut)}</div><div class="sub">${docs.length} documenti di uscita</div></div>
    <div class="kpi"><div class="lab">Giacenza attuale</div><div class="val">${kg(stock)}</div><div class="sub">materiale presente in impianto</div></div>
    <div class="kpi"><div class="lab">Partite lavorate</div><div class="val">${worked}</div><div class="sub">con almeno una lavorazione</div></div>
    <div class="kpi ${hazardous.length?'warn-card':''}"><div class="lab">Pericolosi in giacenza</div><div class="val">${hazardous.length}</div><div class="sub">${kg(hazardous.reduce((s,p)=>s+giacenza(p),0))}</div></div>
  </div>
  <div class="panel"><div class="panel-h"><h3>Partite recenti</h3><span class="sp"></span><button class="btn sm" onclick="go('partite')">Registro completo</button></div>
  ${recent.length?`<table><thead><tr><th>Partita</th><th>Produttore</th><th>CER</th><th>Ingresso</th><th>Giacenza</th><th>Stato</th></tr></thead><tbody>${recent.map(p=>{const g=giacenza(p),out=kgUsciti(p);const stato=g<=.01?'<span class="tag green">chiusa</span>':out>0?'<span class="tag brass">parziale</span>':'<span class="tag grey">in giacenza</span>';return `<tr class="clk" onclick="go('partita','${p.id}')"><td><span class="pnum">${p.num}<span class="r">-Raee</span></span></td><td>${esc(prodName(p.produttoreId))}</td><td><span class="tag cer">${cerLabel(p.cer)}</span></td><td class="num">${kg(p.kgIngresso)}</td><td class="num">${kg(g)}</td><td>${stato}</td></tr>`;}).join('')}</tbody></table>`:emptyState('Nessuna partita per il '+YEAR,'')}
  </div>`;
}
function viewPartiteOperational(){
  const ps=Object.values(DB.partite).filter(p=>p.anno===YEAR).sort((a,b)=>a.num-b.num);
  return `<div class="panel"><div class="panel-h"><h3>Registro partite ${YEAR}</h3><span class="cnt">${ps.length} partite</span><span class="sp"></span>${hasPermission('partite','create')?'<button class="btn primary sm" onclick="openPartita()">+ Nuova partita</button>':''}</div>
  ${ps.length?`<table><thead><tr><th>Partita</th><th>Produttore</th><th>CER</th><th>Ingresso</th><th>Giacenza</th><th>Flusso</th></tr></thead><tbody>${ps.map(p=>{const g=giacenza(p),hasLav=(p.lavorazioni||[]).length>0,hasOut=kgUsciti(p)>0;return `<tr class="clk" onclick="go('partita','${p.id}')"><td><span class="pnum">${p.num}<span class="r">-Raee</span></span></td><td>${esc(prodName(p.produttoreId))}</td><td><span class="tag cer">${cerLabel(p.cer)}</span></td><td class="num">${kg(p.kgIngresso)}</td><td class="num">${kg(g)}</td><td><div class="flow"><span class="step done"><span class="b"></span>Ingresso</span><span class="arw">▸</span><span class="step ${hasLav?'done':''}"><span class="b"></span>Lavoraz.</span><span class="arw">▸</span><span class="step ${hasOut?'done':''}"><span class="b"></span>Uscita</span></div></td></tr>`;}).join('')}</tbody></table>`:emptyState('Nessuna partita per il '+YEAR,'')}
  </div>`;
}
function viewPartitaDetailOperational(){
  const p=DB.partite[ROUTE.id];if(!p)return emptyState('Partita non trovata','');
  const prod=DB.produttori[p.produttoreId]||{},lotti=lottiDisponibili(p),g=giacenza(p),editable=canEditPartita(p);
  const uscite=[];Object.values(DB.documenti).forEach(d=>(d.righe||[]).forEach(r=>{if(r.partitaId===p.id)uscite.push({d,r});}));
  return `<button class="btn ghost sm" onclick="go('partite')" style="margin-bottom:14px">← Registro partite</button>
  <div class="det-head"><div class="idbox"><div class="n">${p.num}<span class="r">-Raee</span></div><div class="y">${p.anno} · Mozzanica</div></div><div class="meta"><div class="prod">${esc(prod.ragioneSociale||'—')}</div><div class="row"><span>CER <b>${cerLabel(p.cer)}</b></span><span>Ingresso <b>${kg(p.kgIngresso)}</b></span><span>Data <b>${dfmt(p.dataIngresso)}</b></span><span>Giacenza <b>${kg(g)}</b></span></div></div></div>
  <div class="det-grid"><div>
    <div class="sec"><div class="sec-h"><h4>Lavorazioni interne</h4><span class="sp"></span>${hasPermission('partite','update')?`<button class="btn sm" onclick="openLavorazione('${p.id}')">+ Lavorazione parziale</button>`:''}</div><div class="sec-b pad0">${(p.lavorazioni||[]).length?`<table><thead><tr><th>Tipo</th><th>Data</th><th>Kg lavorati</th><th>Risultato</th><th></th></tr></thead><tbody>${p.lavorazioni.map(l=>`<tr><td>${l.tipo==='trit'?'Triturazione':'Selezione e cernita'}</td><td>${dfmt(l.data)}</td><td class="num">${kg(l.kgLavorati||l.pesoPrima)}</td><td>${l.frazioni?.length?l.frazioni.map(fr=>`${esc(fr.label)} ${kg(fr.kg)}`).join('<br>'):kg(l.pesoDopo)}</td><td>${hasPermission('partite','update')?`<button class="btn ghost sm" onclick="delLavorazione('${p.id}','${l.id}')">✕</button>`:''}</td></tr>`).join('')}</tbody></table>`:emptyState('Nessuna lavorazione','')}</div></div>
    <div class="sec"><div class="sec-h"><h4>Uscite verso impianti esterni</h4><span class="sp"></span>${hasPermission('uscite','create')?`<button class="btn sm" onclick="openDocumento(null,'${p.id}')">+ Documento di uscita</button>`:''}</div><div class="sec-b pad0">${uscite.length?`<table><thead><tr><th>Documento</th><th>Data</th><th>Destinatario</th><th>Kg</th><th>Tipo</th></tr></thead><tbody>${uscite.map(({d,r})=>`<tr class="clk" onclick="openDocView('${d.id}')"><td><span class="mono">${esc(d.numero||'')}</span></td><td>${dfmt(d.data)}</td><td>${esc(d.destinatario||'—')}</td><td class="num">${kg(r.kg)}</td><td>${r.saldo?'<span class="tag green">saldo</span>':'<span class="tag brass">parziale</span>'}</td></tr>`).join('')}</tbody></table>`:emptyState('Nessuna uscita','')}</div></div>
  </div><div>
    <div class="sec"><div class="sec-h"><h4>Disponibilità</h4></div><div class="sec-b"><div class="kv"><span class="k">Kg ingresso</span><span class="v">${kg(p.kgIngresso)}</span></div><div class="kv"><span class="k">Kg usciti</span><span class="v">${kg(kgUsciti(p))}</span></div><div class="kv"><span class="k">Giacenza</span><span class="v">${kg(g)}</span></div>${lotti.filter(l=>l.kg>.01).map(l=>`<div class="kv"><span class="k">${esc(l.label)}</span><span class="v">${kg(l.kg)}</span></div>`).join('')}</div></div>
    <div class="sec"><div class="sec-h"><h4>Ingresso</h4><span class="sp"></span>${editable&&hasPermission('partite','update')?`<button class="btn sm" onclick="openEditPartita('${p.id}')">Modifica</button>`:''}${hasPermission('partite','delete')?`<button class="btn danger sm" onclick="deletePartita('${p.id}')">Elimina</button>`:''}</div><div class="sec-b"><div class="kv"><span class="k">Produttore</span><span class="v">${esc(prod.ragioneSociale||'—')}</span></div>${(p.formulariIngresso||[]).map(f=>`<div class="kv"><span class="k">Formulario</span><span class="v mono">${esc(f.numero||'—')} · ${dfmt(f.data)}</span></div>`).join('')}</div></div>
  </div></div>`;
}
function viewUsciteOperational(){
  const docs=Object.values(DB.documenti).filter(d=>(d.righe||[]).some(r=>DB.partite[r.partitaId]?.anno===YEAR)).sort((a,b)=>new Date(b.data||0)-new Date(a.data||0));
  return `<div class="panel"><div class="panel-h"><h3>Documenti di uscita ${YEAR}</h3><span class="cnt">${docs.length} documenti</span><span class="sp"></span>${hasPermission('uscite','create')?'<button class="btn primary sm" onclick="openDocumento()">+ Nuovo documento</button>':''}</div>${docs.length?`<table><thead><tr><th>Documento</th><th>Data</th><th>Destinatario</th><th>Partite</th><th>Kg totali</th></tr></thead><tbody>${docs.map(d=>{const parts=[...new Set((d.righe||[]).map(r=>DB.partite[r.partitaId]).filter(Boolean).map(p=>p.num+'-Raee'))];const tot=(d.righe||[]).reduce((s,r)=>s+(+r.kg||0),0);return `<tr class="clk" onclick="openDocView('${d.id}')"><td><span class="tag ${d.tipo==='fir'?'grey':'brass'}">${d.tipo==='fir'?'FIR':'Annex VII'}</span> <span class="mono">${esc(d.numero||'')}</span></td><td>${dfmt(d.data)}</td><td>${esc(d.destinatario||'')}</td><td class="mono">${parts.join(', ')}</td><td class="num">${kg(tot)}</td></tr>`;}).join('')}</tbody></table>`:emptyState('Nessun documento di uscita','')}</div>`;
}
function viewRimanenzeOperational(){
  const rows=[];Object.values(DB.partite).forEach(p=>{const g=giacenza(p);if(g>.01)rows.push({p,g});});rows.sort((a,b)=>b.g-a.g);const tot=rows.reduce((s,r)=>s+r.g,0);
  return `<div class="kpis"><div class="kpi accent"><span class="edge">kg</span><div class="lab">Giacenza totale</div><div class="val">${kg(tot)}</div><div class="sub">${rows.length} partite con residuo</div></div></div><div class="panel"><div class="panel-h"><h3>Rifiuti giacenti in impianto</h3></div>${rows.length?`<table><thead><tr><th>Partita</th><th>Anno</th><th>Produttore</th><th>CER</th><th>Ingresso</th><th>Usciti</th><th>Giacenza</th></tr></thead><tbody>${rows.map(({p,g})=>`<tr class="clk" onclick="go('partita','${p.id}')"><td><span class="pnum">${p.num}<span class="r">-Raee</span></span></td><td>${p.anno}</td><td>${esc(prodName(p.produttoreId))}</td><td><span class="tag cer">${cerLabel(p.cer)}</span></td><td class="num">${kg(p.kgIngresso)}</td><td class="num">${kg(kgUsciti(p))}</td><td class="num">${kg(g)}</td></tr>`).join('')}</tbody></table>`:emptyState('Magazzino vuoto','')}</div>`;
}
function openDocViewOperational(id){
  const d=DB.documenti[id];if(!d)return;
  const rows=(d.righe||[]).map(r=>{const p=DB.partite[r.partitaId];return `<tr><td>${p?p.num+'-Raee':'?'}</td><td>${esc(r.lotto||'tal quale')}</td><td class="num">${kg(r.kg)}</td><td>${r.saldo?'<span class="tag green">saldo</span>':'<span class="tag brass">parziale</span>'}</td></tr>`;}).join('');
  modal(`<div class="modal wide"><div class="modal-h"><h3>${d.tipo==='fir'?'FIR':'Annex VII'} · <span class="mono">${esc(d.numero||'')}</span></h3><button class="x" onclick="closeModal()">×</button></div><div class="modal-b"><div class="kv"><span class="k">Data</span><span class="v">${dfmt(d.data)}</span></div><div class="kv"><span class="k">Destinatario</span><span class="v">${esc(d.destinatario||'—')}</span></div>${d.trasportatoreId?`<div class="kv"><span class="k">Trasportatore</span><span class="v">${esc(DB.trasportatori[d.trasportatoreId]?.ragioneSociale||'—')}</span></div>`:''}<table style="margin-top:14px"><thead><tr><th>Partita</th><th>Lotto</th><th>Kg</th><th>Tipo</th></tr></thead><tbody>${rows}</tbody></table></div><div class="modal-f">${hasPermission('uscite','delete')?`<button class="btn danger" onclick="deleteDocumento('${id}')">Elimina documento</button>`:''}<span style="flex:1"></span><button class="btn" onclick="closeModal()">Chiudi</button></div></div>`);
}
'''
marker="/* ---------- DASHBOARD ---------- */"
rep(marker,ops+'\n'+marker,'operational renderers')

# Route economy-free users into operational-only variants.
rep("function viewDash(){\n  const s = annoStats(YEAR);","function viewDash(){\n  if(FB_ON&&CLOUD.user&&!hasPermission('economics','read')) return viewDashOperational();\n  const s = annoStats(YEAR);",'dash operational route')
rep("function viewPartite(){\n  const ps =","function viewPartite(){\n  if(FB_ON&&CLOUD.user&&!hasPermission('economics','read')) return viewPartiteOperational();\n  const ps =",'partite operational route')
rep("function viewPartitaDetail(){\n  const p =","function viewPartitaDetail(){\n  if(FB_ON&&CLOUD.user&&!hasPermission('economics','read')) return viewPartitaDetailOperational();\n  const p =",'detail operational route')
rep("function viewUscite(){\n  const docs =","function viewUscite(){\n  if(FB_ON&&CLOUD.user&&!hasPermission('economics','read')) return viewUsciteOperational();\n  const docs =",'uscite operational route')
rep("function viewRimanenze(){\n  const rows=[];","function viewRimanenze(){\n  if(FB_ON&&CLOUD.user&&!hasPermission('economics','read')) return viewRimanenzeOperational();\n  const rows=[];",'rimanenze operational route')
rep("function openDocView(id){\nconst d=DB.documenti[id];","function openDocView(id){\nif(FB_ON&&CLOUD.user&&!hasPermission('economics','read')){openDocViewOperational(id);return;}\nconst d=DB.documenti[id];",'doc operational route')

# Action-level guards.
insert_guard('function openPartita(){',"if(!requirePermission('partite','create'))return;",'openPartita guard')
insert_guard('async function savePartita(anno){',"if(!requirePermission('partite','create'))return;",'savePartita guard')
insert_guard('function openEditPartita(partitaId){',"if(!requirePermission('partite','update'))return;",'openEditPartita guard')
insert_guard('function saveEditPartita(partitaId){',"if(!requirePermission('partite','update'))return;",'saveEditPartita guard')
insert_guard('function openLavorazione(pid){',"if(!requirePermission('partite','update'))return;",'openLavorazione guard')
insert_guard('function saveLavorazione(pid){',"if(!requirePermission('partite','update'))return;",'saveLavorazione guard')
insert_guard('function delLavorazione(pid,lid){',"if(!requirePermission('partite','update'))return;",'delLavorazione guard')
insert_guard('function deletePartita(partitaId){',"if(!requirePermission('partite','delete'))return;",'deletePartita guard')
insert_guard('function openDocumento(existingId, preselectPid){',"if(!requirePermission('uscite','create'))return;",'openDocumento guard')
insert_guard('function saveDocumento(){',"if(!requirePermission('uscite','create'))return;",'saveDocumento guard')
insert_guard('function deleteDocumento(documentoId){',"if(!requirePermission('uscite','delete'))return;",'deleteDocumento guard')
insert_guard('function openFattura(pid){',"if(!requirePermission('economics','read')||!isAdmin())return;",'openFattura guard')
insert_guard('async function saveFattura(pid){',"if(!requirePermission('economics','read')||!isAdmin())return;",'saveFattura guard')
insert_guard('function delFattura(pid,fid){',"if(!requirePermission('economics','read')||!isAdmin())return;",'delFattura guard')
insert_guard('function saveValor(id){',"if(!requirePermission('economics','read')||!isAdmin())return;",'saveValor guard')
insert_guard('function openAnag(store, returnCb){',"if(!requirePermission(store,'create'))return;",'openAnag guard')
insert_guard('function saveAnag(store){',"if(!requirePermission(store,'create'))return;",'saveAnag guard')

# Backup/admin operations are not exposed to operators.
insert_guard('function exportBackup(){',"if(!hasPermission('backup','manage')&&!isAdmin()){toast('Backup riservato all’amministratore','err');return;}",'export backup guard')
insert_guard('function chooseBackupFile(){',"if(!hasPermission('backup','manage')&&!isAdmin()){toast('Import backup riservato all’amministratore','err');return;}",'choose backup guard')
insert_guard('async function importBackupFile(input){',"if(!hasPermission('backup','manage')&&!isAdmin()){toast('Import backup riservato all’amministratore','err');return;}",'import backup guard')
insert_guard('function restorePreviousLocal(){',"if(!hasPermission('backup','manage')&&!isAdmin()){toast('Ripristino riservato all’amministratore','err');return;}",'restore guard')
insert_guard('function resetAll(){',"if(!isAdmin()){toast('Azzeramento riservato all’amministratore','err');return;}",'reset guard')
insert_guard('function doReset(){',"if(!isAdmin()){toast('Azzeramento riservato all’amministratore','err');return;}",'do reset guard')

# Sync-now and controlled migration helpers.
helper=r'''
function syncNow(){
  if(!CLOUD.user){openCloudLogin();return;}
  if(CLOUD.mode==='branches'){queueGranularSave();toast('Sincronizzazione multiutente avviata');return;}
  if(CLOUD.mode==='legacy'&&isAdmin()){pushCloud();toast('Sincronizzazione avviata');return;}
  toast('Sincronizzazione non disponibile in questo stato','err');
}
async function migrateToMultiuser(){
  if(!isAdmin()||CLOUD.mode!=='legacy'){toast('Migrazione disponibile solo all’amministratore prima del passaggio multiutente','err');return;}
  if(!window.confirm('Avviare la migrazione dell’archivio nelle nuove sezioni multiutente? Verifica di avere già esportato il backup JSON e il backup Firebase.'))return;
  CLOUD.syncing=true;updateStoreStatus();
  try{
    const result=await window.firebaseBridge.migrateLegacyToBranches();
    toast(`Migrazione completata: ${result.partite} partite e ${result.documenti} documenti`);
    await syncBranchCloud();
  }catch(e){toast('Migrazione non eseguita: '+String(e?.message||e),'err');}
  finally{CLOUD.syncing=false;updateStoreStatus();}
}
'''
rep("/* ---------- BACKUP / SINCRONIZZAZIONE ---------- */",helper+'\n/* ---------- BACKUP / SINCRONIZZAZIONE ---------- */','sync/migration helpers')

# Replace obsolete sync button in data manager and add a migration button for admin legacy mode.
text=text.replace("${FB_ON?(CLOUD.user?'<button class=\"btn\" onclick=\"pushCloud();closeModal();toast(\\'Sincronizzazione avviata\\')\">Sincronizza ora</button>':'<button class=\"btn\" onclick=\"openCloudLogin()\">Accedi a Firebase</button>'):'<button class=\"btn\" disabled>Configura Firebase per il cloud</button>'}","${FB_ON?(CLOUD.user?'<button class=\"btn\" onclick=\"syncNow();closeModal()\">Sincronizza ora</button>':'<button class=\"btn\" onclick=\"openCloudLogin()\">Accedi a Firebase</button>'):'<button class=\"btn\" disabled>Configura Firebase per il cloud</button>'}${isAdmin()&&CLOUD.mode==='legacy'?'<button class=\"btn primary\" onclick=\"closeModal();migrateToMultiuser()\">Prepara archivio multiutente</button>':''}")

p.write_text(text,encoding='utf-8')

# syntax validation
scripts=re.findall(r'<script(?P<attrs>[^>]*)>(?P<body>.*?)</script>',text,flags=re.S|re.I)
with tempfile.TemporaryDirectory() as td:
    for i,(attrs,body) in enumerate(scripts):
        if 'src=' in attrs: continue
        ext='.mjs' if 'type="module"' in attrs or "type='module'" in attrs else '.js'
        f=Path(td)/f's{i}{ext}';f.write_text(body,encoding='utf-8');subprocess.run(['node','--check',str(f)],check=True)
assert 'viewDashOperational' in text and 'openDocViewOperational' in text
assert "Backup riservato all’amministratore" in text
print('UI e permessi multiutente completati; sintassi valida.')
