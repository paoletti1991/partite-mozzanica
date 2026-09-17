from pathlib import Path
import re

p = Path('public/index.html')
s = p.read_text(encoding='utf-8')

# Regola desiderata:
# - la numerazione resta continua;
# - si puo' eliminare soltanto l'ultima partita numerata dell'anno;
# - eliminandola il contatore torna al numero precedente;
# - eventuali numeri finali gia' consumati senza una partita vengono recuperati
#   automaticamente prima della successiva creazione.

# 1) Il fallback locale considera sia le partite esistenti sia il contatore.
old_next = '''function nextNum(year){
  const list = Object.values(DB.partite).filter(p=>p.anno===year);
  const max = list.reduce((m,p)=>Math.max(m, p.num||0), 0);
  return max+1;
}'''
new_next = '''function nextNum(year){
  const list = Object.values(DB.partite).filter(p=>+p.anno===+year);
  const maxExisting = list.reduce((m,p)=>Math.max(m, +p.num||0), 0);
  const counter = +(DB.counters?.[String(year)]||0);
  return Math.max(maxExisting,counter)+1;
}'''
if old_next not in s:
    raise SystemExit('Funzione nextNum non trovata o gia modificata')
s = s.replace(old_next, new_next, 1)

# 2) Riallineamento del contatore a piccoli passi (+1/-1).
#    Questo consente di recuperare in sicurezza un ultimo numero rimasto
#    prenotato dopo una cancellazione o un salvataggio interrotto.
old_counter = '''      async nextCounter(year){
        const ref=dbMod.ref(database,'registroMozzanica/counters/'+String(year));
        const result=await dbMod.runTransaction(ref,current=>(Number(current)||0)+1);
        if(!result.committed) throw new Error('Progressivo non assegnato');
        return +result.snapshot.val();
      },'''
new_counter = '''      async syncCounterToExistingMax(year,target){
        const ref=dbMod.ref(database,'registroMozzanica/counters/'+String(year));
        const wanted=Math.max(0,Number(target)||0);
        for(let i=0;i<1000;i++){
          const snap=await dbMod.get(ref);
          const current=Number(snap.val())||0;
          if(current===wanted) return current;
          const result=await dbMod.runTransaction(ref,value=>{
            const n=Number(value)||0;
            if(n===wanted) return;
            return n<wanted ? n+1 : n-1;
          });
          if(result.committed){
            const value=+result.snapshot.val();
            if(value===wanted) return value;
          }else{
            const verify=await dbMod.get(ref);
            if((Number(verify.val())||0)===wanted) return wanted;
          }
        }
        throw new Error('Contatore non riallineato');
      },
      async nextCounter(year){
        const ref=dbMod.ref(database,'registroMozzanica/counters/'+String(year));
        const result=await dbMod.runTransaction(ref,current=>(Number(current)||0)+1);
        if(!result.committed) throw new Error('Progressivo non assegnato');
        return +result.snapshot.val();
      },'''
if old_counter not in s:
    raise SystemExit('Funzione nextCounter non trovata')
s = s.replace(old_counter, new_counter, 1)

# 3) Prima di creare una partita il contatore viene sempre riallineato al
#    numero massimo realmente presente. Se, per esempio, la 38 era stata
#    eliminata e l'ultima presente e' la 37, la nuova partita torna ad essere 38.
old_save_head = '''async function savePartita(anno){
  if(!requirePermission('partite','create'))return;
  anno=+anno||YEAR;
  let num=nextNum(anno);
  if(CLOUD.user&&CLOUD.mode==='branches'){
    try{num=await window.firebaseBridge.nextCounter(anno);DB.counters[String(anno)]=num;}
    catch(e){toast('Impossibile assegnare il progressivo della partita','err');return;}
  }
  const cer=document.getElementById('pcer_val').value;'''
new_save_head = '''async function savePartita(anno){
  if(!requirePermission('partite','create'))return;
  anno=+anno||YEAR;
  const maxExisting=Object.values(DB.partite)
    .filter(p=>+p.anno===+anno)
    .reduce((m,p)=>Math.max(m,+p.num||0),0);
  let num=nextNum(anno);
  if(CLOUD.user&&CLOUD.mode==='branches'){
    try{
      const aligned=await window.firebaseBridge.syncCounterToExistingMax(anno,maxExisting);
      DB.counters[String(anno)]=aligned;
      num=await window.firebaseBridge.nextCounter(anno);
      DB.counters[String(anno)]=num;
      if(num!==maxExisting+1 || Object.values(DB.partite).some(p=>+p.anno===+anno && +p.num===+num)){
        toast('Progressivo non valido: creazione interrotta per evitare un duplicato','err');
        return;
      }
    }catch(e){toast('Impossibile riallineare o assegnare il progressivo della partita','err');return;}
  }
  const cer=document.getElementById('pcer_val').value;'''
if old_save_head not in s:
    raise SystemExit('Testata savePartita non trovata')
s = s.replace(old_save_head, new_save_head, 1)

# 4) Numero e anno restano sempre immutabili durante la modifica.
old_edit = '''  p.cer=cer;
  p.kgIngresso=kgv;
  p.produttoreId=prod;
  p.dataIngresso=dataIngresso;'''
new_edit = '''  const immutableNum=snapshot.num;
  const immutableAnno=snapshot.anno;
  p.cer=cer;
  p.kgIngresso=kgv;
  p.produttoreId=prod;
  p.dataIngresso=dataIngresso;
  p.num=immutableNum;
  p.anno=immutableAnno;'''
if old_edit not in s:
    raise SystemExit('Blocco modifica partita non trovato')
s = s.replace(old_edit, new_edit, 1)

# 5) Per mantenere una sequenza senza buchi si puo' cancellare soltanto
#    l'ultima partita numerata dell'anno. Prima della cancellazione si riallinea
#    il contatore; la cancellazione cloud di partita + contatore avviene poi in
#    un unico update Firebase, cosi' un'eventuale creazione concorrente fa
#    fallire tutta l'operazione invece di produrre numeri incoerenti.
if 'function deletePartita(partitaId){' not in s:
    raise SystemExit('Funzione deletePartita non trovata')
s = s.replace('function deletePartita(partitaId){', 'async function deletePartita(partitaId){', 1)

old_delete_head = '''  const p=DB.partite[partitaId];
  if(!p){ toast('Partita non trovata','err'); return; }

  const reasons=[];'''
new_delete_head = '''  const p=DB.partite[partitaId];
  if(!p){ toast('Partita non trovata','err'); return; }

  const anno=+p.anno||YEAR;
  const num=+p.num||0;
  const maxExisting=Object.values(DB.partite)
    .filter(x=>+x.anno===+anno)
    .reduce((m,x)=>Math.max(m,+x.num||0),0);

  if(num!==maxExisting){
    modal(`<div class="modal"><div class="modal-h"><h3>Eliminazione non consentita</h3><button class="x" onclick="closeModal()">&times;</button></div>
      <div class="modal-b"><p style="margin:0">Per mantenere la numerazione senza buchi puoi eliminare soltanto <b>l'ultima partita numerata dell'anno</b>.</p>
      <p class="hint" style="margin:12px 0 0">La partita ${p.num}-Raee non è l'ultima del ${p.anno}; eliminarla richiederebbe rinumerare partite successive già esistenti.</p></div>
      <div class="modal-f"><button class="btn" onclick="closeModal()">Chiudi</button></div></div>`);
    toast('Puoi eliminare solo l’ultima partita dell’anno','err');
    return;
  }

  if(CLOUD.user&&CLOUD.mode==='branches'){
    try{
      const aligned=await window.firebaseBridge.syncCounterToExistingMax(anno,maxExisting);
      DB.counters[String(anno)]=aligned;
    }catch(e){
      toast('Impossibile riallineare la numerazione prima della cancellazione','err');
      return;
    }
  }

  const reasons=[];'''
if old_delete_head not in s:
    raise SystemExit('Testata eliminazione partita non trovata')
s = s.replace(old_delete_head, new_delete_head, 1)

pattern = re.compile(
    r"  if\(!window\.confirm\('Stai per eliminare definitivamente questa partita, incluse fatture, formulari e trasporto di ingresso collegati\. L\\'operazione non è reversibile\.'\)\) return;\n\n"
    r"  const hadEconomics=!!DB\.economics\?\.partite\?\.\[partitaId\];\n"
    r"  const previousEconomics=hadEconomics\n"
    r"    \? JSON\.parse\(JSON\.stringify\(DB\.economics\.partite\[partitaId\]\)\)\n"
    r"    : null;\n\n"
    r"  delete DB\.partite\[partitaId\];\n"
    r"  if\(hadEconomics\) delete DB\.economics\.partite\[partitaId\];\n\n"
    r"  if\(!save\(\)\)\{\n"
    r"    DB\.partite\[partitaId\]=p;\n"
    r"    if\(hadEconomics\) DB\.economics\.partite\[partitaId\]=previousEconomics;\n"
    r"    return;\n"
    r"  \}\n\n",
    re.S,
)
new_delete_body = '''  if(!window.confirm(`Stai per eliminare definitivamente la partita ${num}-Raee ${anno}. La numerazione tornerà a ${Math.max(0,num-1)}-Raee e il numero ${num} potrà essere assegnato alla prossima partita. L'operazione non è reversibile.`)) return;

  const hadEconomics=!!DB.economics?.partite?.[partitaId];
  const previousEconomics=hadEconomics
    ? JSON.parse(JSON.stringify(DB.economics.partite[partitaId]))
    : null;
  const previousCounter=+(DB.counters?.[String(anno)]||0);
  const newCounter=Math.max(0,num-1);

  if(CLOUD.user&&CLOUD.mode==='branches'){
    const updates={
      ['partite/'+partitaId]:null,
      ['counters/'+String(anno)]:newCounter
    };
    if(hadEconomics&&isAdmin()) updates['economics/partite/'+partitaId]=null;
    try{
      await window.firebaseBridge.writeBranchUpdates(updates,[{section:'partite',recordId:partitaId,action:'delete'}]);
    }catch(e){
      toast('Eliminazione non riuscita: la numerazione potrebbe essere cambiata. Riprova.','err');
      return;
    }

    delete DB.partite[partitaId];
    if(hadEconomics&&isAdmin()) delete DB.economics.partite[partitaId];
    DB.counters[String(anno)]=newCounter;
    if(CLOUD.syncedDB){
      delete CLOUD.syncedDB.partite[partitaId];
      if(hadEconomics&&isAdmin()&&CLOUD.syncedDB.economics?.partite) delete CLOUD.syncedDB.economics.partite[partitaId];
      CLOUD.syncedDB.counters=CLOUD.syncedDB.counters||{};
      CLOUD.syncedDB.counters[String(anno)]=newCounter;
    }
    persistLocal(DB,true);
    CLOUD.lastSync=Date.now();
    updateStoreStatus();
  }else{
    delete DB.partite[partitaId];
    if(hadEconomics) delete DB.economics.partite[partitaId];
    DB.counters[String(anno)]=newCounter;
    if(!save()){
      DB.partite[partitaId]=p;
      if(hadEconomics) DB.economics.partite[partitaId]=previousEconomics;
      DB.counters[String(anno)]=previousCounter;
      return;
    }
  }

'''
s, count = pattern.subn(new_delete_body, s, count=1)
if count != 1:
    raise SystemExit('Corpo eliminazione partita non trovato')

# Verifiche finali.
required = [
    'Math.max(maxExisting,counter)+1',
    'async syncCounterToExistingMax(year,target)',
    'num!==maxExisting',
    "['counters/'+String(anno)]:newCounter",
    'num!==maxExisting+1',
    'p.num=immutableNum',
    'p.anno=immutableAnno',
]
for token in required:
    if token not in s:
        raise SystemExit('Verifica numerazione fallita: manca '+token)

p.write_text(s, encoding='utf-8')
print('Numerazione continua e recupero ultimo progressivo applicati')
