from pathlib import Path

p = Path('public/index.html')
s = p.read_text(encoding='utf-8')

# 1) Integra le fatture documentali inserite dagli operatori nei conteggi admin,
#    senza concedere agli operatori accesso al ramo economics o ai report.
start = s.index('  function partitaEconomicsData(p){')
end = s.index('function ensurePartitaEconomics(p){', start)
new_econ = r'''function mergePurchaseInvoices(economicInvoices, operationalInvoices){
  const merged=new Map();
  const put=(f,preferEconomic=false)=>{
    if(!f)return;
    const numero=String(f.numero||'').trim();
    const data=String(f.data||'');
    const key=(numero.toLowerCase()+'|'+data)||String(f.id||'');
    const previous=merged.get(key)||{};
    const amount=Number.isFinite(+f.importo)&&+f.importo>0 ? +f.importo : (+previous.importo||0);
    merged.set(key,{...previous,...f,numero,data,importo:amount,source:preferEconomic?'economics':(previous.source||'operational')});
  };
  (operationalInvoices||[]).forEach(f=>put({...f,source:'operational'},false));
  (economicInvoices||[]).forEach(f=>put(f,true));
  return [...merged.values()].filter(f=>String(f.numero||'').trim()||(+f.importo||0)>0);
}

function partitaEconomicsData(p){
  if(!p){
    return {fattureAcquisto:[],definizioniFornitore:[],trasportoIngresso:null};
  }

  if(FB_ON && CLOUD.user && !hasPermission('economics','read')){
    return {fattureAcquisto:[],definizioniFornitore:[],trasportoIngresso:null};
  }

  const stored=DB.economics?.partite?.[p.id];
  const economicInvoices=stored ? (stored.fattureAcquisto||[]) : (p.fattureAcquisto||[]);
  const operationalInvoices=p.fattureDocumentaliAcquisto||[];

  return {
    fattureAcquisto:mergePurchaseInvoices(economicInvoices,operationalInvoices),
    definizioniFornitore:stored ? (stored.definizioniFornitore||[]) : (p.definizioniFornitore||[]),
    trasportoIngresso:stored ? (stored.trasportoIngresso||null) : (p.trasportoIngresso||null)
  };
}

function documentoEconomicsData(d){
  if(!d){
    return {trasportoCosto:0,valorizzazione:null,naturaEconomicaBozza:null,fatturaCliente:null,fatturaCosto:null};
  }

  if(FB_ON && CLOUD.user && !hasPermission('economics','read')){
    return {trasportoCosto:0,valorizzazione:null,naturaEconomicaBozza:null,fatturaCliente:null,fatturaCosto:null};
  }

  const stored=DB.economics?.documenti?.[d.id];
  const base=stored ? {
    trasportoCosto:+stored.trasportoCosto||0,
    valorizzazione:stored.valorizzazione||null,
    naturaEconomicaBozza:stored.naturaEconomicaBozza||null,
    fatturaCliente:stored.fatturaCliente||null,
    fatturaCosto:stored.fatturaCosto||null
  } : {
    trasportoCosto:+d.trasportoCosto||0,
    valorizzazione:d.valorizzazione||null,
    naturaEconomicaBozza:d.naturaEconomicaBozza||null,
    fatturaCliente:d.fatturaCliente||null,
    fatturaCosto:d.fatturaCosto||null
  };

  const op=(d.fattureDocumentaliVendita||[]).filter(f=>Number.isFinite(+f.importo)&&+f.importo>0);
  const opTotal=op.reduce((sum,f)=>sum+(+f.importo||0),0);
  if(!base.valorizzazione && opTotal>0){
    base.valorizzazione={valoreRiconosciuto:opTotal,natura:'ricavo',source:'operational'};
    base.naturaEconomicaBozza='ricavo';
  }
  if(!base.fatturaCliente && op.length){
    base.fatturaCliente={
      numero:op.map(f=>String(f.numero||'').trim()).filter(Boolean).join(', '),
      data:op.map(f=>f.data||'').filter(Boolean).sort().slice(-1)[0]||'',
      source:'operational'
    };
  }
  return base;
}

'''
s = s[:start] + new_econ + s[end:]

# 2) Sostituisce la gestione fatture operative: numero, data, importo e cancellazione.
start = s.index('function operationalInvoiceRecord(kind,id){')
end = s.index('/* ---------- DASHBOARD ---------- */', start)
new_ops = r'''function operationalInvoiceRecord(kind,id){
  return kind==='acquisto' ? DB.partite[id] : DB.documenti[id];
}
function operationalInvoiceKey(kind){
  return kind==='acquisto' ? 'fattureDocumentaliAcquisto' : 'fattureDocumentaliVendita';
}
function operationalInvoiceSection(kind){
  return kind==='acquisto' ? 'partite' : 'uscite';
}
function renderOperationalInvoices(kind,id){
  const rec=operationalInvoiceRecord(kind,id);
  const items=(rec&&rec[operationalInvoiceKey(kind)])||[];
  if(!items.length) return `<div class="empty"><div class="big">Nessuna fattura registrata</div>Puoi registrare numero, data e importo della fattura. Report e analisi restano riservati all'amministratore.</div>`;
  const canDelete=hasPermission(operationalInvoiceSection(kind),'update');
  return `<table><thead><tr><th>N. fattura</th><th>Data</th><th>Importo</th>${canDelete?'<th></th>':''}</tr></thead><tbody>${items.map(f=>`<tr><td class="mono">${esc(f.numero||'—')}</td><td>${dfmt(f.data)}</td><td class="num">${eur(f.importo)}</td>${canDelete?`<td style="text-align:right"><button class="btn danger sm" onclick="event.stopPropagation();deleteOperationalInvoice('${kind}','${id}','${f.id}')">Elimina</button></td>`:''}</tr>`).join('')}</tbody></table>`;
}
function openOperationalInvoice(kind,id){
  const section=operationalInvoiceSection(kind);
  if(!requirePermission(section,'update'))return;
  const rec=operationalInvoiceRecord(kind,id);if(!rec){toast('Elemento non trovato','err');return;}
  modal(`<div class="modal"><div class="modal-h"><h3>${kind==='acquisto'?"Fattura d'acquisto":'Fattura di vendita'}</h3><button class="x" onclick="closeModal()">×</button></div><div class="modal-b"><div class="row2"><div class="field"><label>N. fattura <span class="req">*</span></label><input class="inp mono" id="ofi_num"></div><div class="field"><label>Data <span class="req">*</span></label><input class="inp" type="date" id="ofi_data"></div></div><div class="field"><label>Importo € <span class="req">*</span></label><input class="inp num" type="number" min="0.01" step="0.01" id="ofi_importo" placeholder="0,00"></div><div class="mini">L'importo viene registrato sulla fattura. Report, margini e analisi economiche restano non visibili a questo profilo.</div></div><div class="modal-f"><button class="btn" onclick="closeModal()">Annulla</button><span style="flex:1"></span><button class="btn primary" onclick="saveOperationalInvoice('${kind}','${id}')">Registra</button></div></div>`);
}
function saveOperationalInvoice(kind,id){
  const section=operationalInvoiceSection(kind);
  if(!requirePermission(section,'update'))return;
  const rec=operationalInvoiceRecord(kind,id);if(!rec){toast('Elemento non trovato','err');return;}
  const numero=(document.getElementById('ofi_num')?.value||'').trim();
  const data=document.getElementById('ofi_data')?.value||'';
  const importo=+(document.getElementById('ofi_importo')?.value||0);
  if(!numero||!data){toast('Inserisci numero e data della fattura','err');return;}
  if(!Number.isFinite(importo)||importo<=0){toast('Inserisci un importo valido maggiore di zero','err');return;}
  const key=operationalInvoiceKey(kind);
  const before=JSON.parse(JSON.stringify(rec[key]||[]));
  rec[key]=[...(rec[key]||[]),{
    id:'ofi_'+Date.now().toString(36)+Math.random().toString(36).slice(2,6),
    numero,
    data,
    importo,
    createdAt:Date.now(),
    createdBy:CLOUD.user?.uid||''
  }];
  if(!save()){
    rec[key]=before;
    toast('Impossibile salvare la fattura','err');
    return;
  }
  closeModal();
  if(kind==='acquisto') render(); else openDocViewOperational(id);
  toast('Fattura registrata');
}
function deleteOperationalInvoice(kind,id,fid){
  const section=operationalInvoiceSection(kind);
  if(!requirePermission(section,'update'))return;
  const rec=operationalInvoiceRecord(kind,id);if(!rec){toast('Elemento non trovato','err');return;}
  const key=operationalInvoiceKey(kind);
  const items=rec[key]||[];
  const invoice=items.find(f=>f.id===fid);
  if(!invoice){toast('Fattura non trovata','err');return;}
  if(!window.confirm(`Eliminare la fattura ${invoice.numero||''} del ${dfmt(invoice.data)}?`))return;
  const before=JSON.parse(JSON.stringify(items));
  rec[key]=items.filter(f=>f.id!==fid);
  if(!save()){
    rec[key]=before;
    toast('Impossibile eliminare la fattura','err');
    return;
  }
  if(kind==='acquisto') render(); else openDocViewOperational(id);
  toast('Fattura eliminata');
}

'''
s = s[:start] + new_ops + s[end:]

# 3) Nell'area admin, le fatture d'acquisto operative compaiono nei conteggi e
#    usano la corretta azione di cancellazione.
old = "<td><button class=\"btn ghost sm\" onclick=\"delFattura('${p.id}','${f.id}')\">✕</button></td></tr>`).join('')}"
new = "<td><button class=\"btn ghost sm\" onclick=\"${f.source==='operational'?`deleteOperationalInvoice('acquisto','${p.id}','${f.id}')`:`delFattura('${p.id}','${f.id}')`}\">✕</button></td></tr>`).join('')}"
if old in s:
  s = s.replace(old,new,1)

# Verifiche minime di sicurezza del build.
required = [
  "id=\"ofi_importo\"",
  "function deleteOperationalInvoice(kind,id,fid)",
  "fattureDocumentaliAcquisto",
  "fattureDocumentaliVendita",
  "Report, margini e analisi economiche restano non visibili",
  "report: ['report','read']"
]
for token in required:
  if token not in s:
    raise SystemExit('Verifica fallita, manca: '+token)

p.write_text(s,encoding='utf-8')
