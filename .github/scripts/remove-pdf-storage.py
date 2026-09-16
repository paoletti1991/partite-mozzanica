from pathlib import Path
import json
import re

index = Path('public/index.html')
s = index.read_text(encoding='utf-8')

# Rimuove Firebase Storage dal bridge: non viene più usato dall'app.
s = s.replace("    const storageMod=await import('https://www.gstatic.com/firebasejs/12.16.0/firebase-storage.js');\n", "")
s = s.replace(
    "    const auth=authMod.getAuth(app), database=dbMod.getDatabase(app), storage=storageMod.getStorage(app);\n",
    "    const auth=authMod.getAuth(app), database=dbMod.getDatabase(app);\n"
)
s = re.sub(
    r"\n\s*async uploadFile\(file,path\)\{const target=storageMod\.ref\(storage,path\);await storageMod\.uploadBytes\(target,file\);return storageMod\.getDownloadURL\(target\);\},",
    "",
    s,
    count=1,
)

# UI admin: niente allegati PDF nelle fatture d'acquisto.
s, n = re.subn(
    r'\n\s*<div class="field"><label>Allegati PDF</label><input class="inp" id="f_pdf" type="file" accept="application/pdf" multiple>\s*<div class="hint">.*?</div></div>',
    '',
    s,
    count=1,
    flags=re.S,
)
if n != 1:
    raise SystemExit(f'Blocco allegati PDF admin non trovato o ambiguo: {n}')

# Salvataggio fattura d'acquisto admin: conserva numero/data/importo, senza file.
admin_save = r'''async function saveFattura(pid){
  if(!requirePermission('economics','create'))return;
  const p=DB.partite[pid];
  if(!p) return;

  const num=document.getElementById('f_num').value.trim();
  const data=document.getElementById('f_data').value;
  const imp=+document.getElementById('f_imp').value;
  if(!num||!data){toast('Inserisci numero e data fattura','err');return;}
  if(!Number.isFinite(imp)||imp<=0){
    toast('Inserisci un importo d’acquisto valido maggiore di zero','err');
    return;
  }

  const eco=ensurePartitaEconomics(p);
  eco.fattureAcquisto=eco.fattureAcquisto||[];
  eco.fattureAcquisto.push({
    id:uid('ft'),
    numero:num,
    data,
    importo:imp
  });

  if(!save())return;
  closeModal();
  render();
  toast('Fattura aggiunta');
}
function delFattura'''
s, n = re.subn(
    r'async function saveFattura\(pid\)\{.*?\n\}\nfunction delFattura',
    admin_save,
    s,
    count=1,
    flags=re.S,
)
if n != 1:
    raise SystemExit(f'Funzione saveFattura non trovata o ambigua: {n}')

# Rimuove colonna Allegati dalla tabella economica admin.
s = s.replace(
    '<th>Importo</th><th>Allegati</th><th></th>',
    '<th>Importo</th><th></th>'
)
s, _ = re.subn(
    r'\n\s*<td>\$\{\(f\.pdf\|\|\[\]\).*?</td>',
    '',
    s,
    count=1,
    flags=re.S,
)
s = s.replace(
    '<td colspan="2" class="num">${ekg(ekgI)}</td>',
    '<td class="num">${ekg(ekgI)}</td>'
)

# Testi pulsanti operatori: registrazione, non caricamento file.
s = s.replace('>+ Carica fattura</button>', '>+ Registra fattura</button>')

# Sostituisce l'intera gestione fatture operatori con soli metadati numero/data.
operator_block = r'''function operationalInvoiceRecord(kind,id){
  return kind==='acquisto' ? DB.partite[id] : DB.documenti[id];
}
function operationalInvoiceKey(kind){
  return kind==='acquisto' ? 'fattureDocumentaliAcquisto' : 'fattureDocumentaliVendita';
}
function renderOperationalInvoices(kind,id){
  const rec=operationalInvoiceRecord(kind,id);
  const items=(rec&&rec[operationalInvoiceKey(kind)])||[];
  if(!items.length) return `<div class="empty"><div class="big">Nessuna fattura registrata</div>Gli operatori possono registrare numero e data senza accedere a importi o altri dati economici.</div>`;
  return `<table><thead><tr><th>N. fattura</th><th>Data</th></tr></thead><tbody>${items.map(f=>`<tr><td class="mono">${esc(f.numero||'—')}</td><td>${dfmt(f.data)}</td></tr>`).join('')}</tbody></table>`;
}
function openOperationalInvoice(kind,id){
  const section=kind==='acquisto'?'partite':'uscite';
  if(!requirePermission(section,'update'))return;
  const rec=operationalInvoiceRecord(kind,id);if(!rec){toast('Elemento non trovato','err');return;}
  modal(`<div class="modal"><div class="modal-h"><h3>${kind==='acquisto'?"Fattura d'acquisto":'Fattura di vendita'}</h3><button class="x" onclick="closeModal()">×</button></div><div class="modal-b"><div class="row2"><div class="field"><label>N. fattura <span class="req">*</span></label><input class="inp mono" id="ofi_num"></div><div class="field"><label>Data <span class="req">*</span></label><input class="inp" type="date" id="ofi_data"></div></div><div class="mini">Per questo profilo vengono registrati soltanto numero e data. Importi e dati economici restano riservati all'amministratore.</div></div><div class="modal-f"><button class="btn" onclick="closeModal()">Annulla</button><span style="flex:1"></span><button class="btn primary" onclick="saveOperationalInvoice('${kind}','${id}')">Registra</button></div></div>`);
}
function saveOperationalInvoice(kind,id){
  const section=kind==='acquisto'?'partite':'uscite';
  if(!requirePermission(section,'update'))return;
  const rec=operationalInvoiceRecord(kind,id);if(!rec){toast('Elemento non trovato','err');return;}
  const numero=(document.getElementById('ofi_num')?.value||'').trim();
  const data=document.getElementById('ofi_data')?.value||'';
  if(!numero||!data){toast('Inserisci numero e data della fattura','err');return;}

  const key=operationalInvoiceKey(kind);
  const before=JSON.parse(JSON.stringify(rec[key]||[]));
  rec[key]=[...(rec[key]||[]),{
    id:'ofi_'+Date.now().toString(36),
    numero,
    data,
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

/* ---------- DASHBOARD ---------- */'''
s, n = re.subn(
    r'function operationalInvoiceRecord\(kind,id\)\{.*?\/\* ---------- DASHBOARD ---------- \*\/',
    operator_block,
    s,
    count=1,
    flags=re.S,
)
if n != 1:
    raise SystemExit(f'Blocco fatture operatori non trovato o ambiguo: {n}')

# Verifiche di sicurezza: nessun upload o campo PDF deve restare.
for forbidden in ['firebase-storage.js', 'uploadFile(file,path)', 'id="ofi_file"', 'id="f_pdf"', 'fatture-acquisto/', 'fatture-vendita/']:
    if forbidden in s:
        raise SystemExit(f'Riferimento Storage/PDF ancora presente: {forbidden}')

index.write_text(s, encoding='utf-8')

# Firebase config: rimuove completamente la sezione Storage.
fp = Path('firebase.json')
firebase = json.loads(fp.read_text(encoding='utf-8'))
firebase.pop('storage', None)
fp.write_text(json.dumps(firebase, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# README: allinea la documentazione al nuovo assetto senza Storage.
rp = Path('README_INSTALLAZIONE.md')
r = rp.read_text(encoding='utf-8')
r = r.replace('- **Firebase Storage** per i PDF delle fatture;\n', '')
r = r.replace('6. Attiva **Storage**.\n7. La configurazione della Web App è già inserita in `public/firebase-config.js`.', '6. La configurazione della Web App è già inserita in `public/firebase-config.js`.')
r = r.replace('Il progetto `partite-mozzanica` e l\'UID autorizzato sono già inseriti in `.firebaserc`, `database.rules.json` e `storage.rules`. Le regole negano l\'accesso a tutti gli altri utenti.', 'Il progetto `partite-mozzanica` e l\'UID autorizzato sono già inseriti in `.firebaserc` e `database.rules.json`. Le regole negano l\'accesso a tutti gli altri utenti.')
r = r.replace('firebase deploy --only database,storage', 'firebase deploy --only database')
r = r.replace('Per autorizzare altri utenti in futuro, aggiungi il loro UID alle condizioni presenti in entrambi i file delle regole prima di ripubblicarle.', 'Per autorizzare altri utenti in futuro, configura il relativo profilo in `accessControl/users` e mantieni coerenti le regole del Realtime Database.')
r = re.sub(r'\n### Fatture per gli operatori\n.*?(?=\n## 3\.)', '\n', r, flags=re.S)
r = re.sub(r'\n\s*storageBucket: ".*?",', '', r)
if 'Firebase Storage' in r or 'storage.rules' in r or '--only database,storage' in r or 'fatture-acquisto/' in r or 'fatture-vendita/' in r:
    raise SystemExit('README contiene ancora riferimenti operativi a Storage')
rp.write_text(r, encoding='utf-8')

print('Rimozione PDF/Storage completata')
