from pathlib import Path

p = Path('public/index.html')
s = p.read_text(encoding='utf-8')

# 1) Anche l'eventuale fallback locale deve rispettare il contatore annuale:
#    un numero gia' assegnato non viene mai riutilizzato dopo una cancellazione.
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

# 2) Funzione admin per riallineare in sicurezza un contatore eventualmente
#    rimasto indietro dopo un ripristino. Non decrementa mai il contatore.
old_counter = '''      async nextCounter(year){
        const ref=dbMod.ref(database,'registroMozzanica/counters/'+String(year));
        const result=await dbMod.runTransaction(ref,current=>(Number(current)||0)+1);
        if(!result.committed) throw new Error('Progressivo non assegnato');
        return +result.snapshot.val();
      },'''
new_counter = '''      async ensureCounterAtLeast(year,floor){
        const ref=dbMod.ref(database,'registroMozzanica/counters/'+String(year));
        const minimum=Math.max(0,Number(floor)||0);
        const result=await dbMod.runTransaction(ref,current=>Math.max(Number(current)||0,minimum));
        if(!result.committed) throw new Error('Contatore non riallineato');
        return +result.snapshot.val();
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

# 3) Prima di assegnare un nuovo numero confronta contatore e numeri esistenti.
#    L'admin puo' riallineare automaticamente un contatore arretrato; un operatore
#    viene fermato senza creare duplicati o consumare numeri in modo ambiguo.
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
      let counter=+(DB.counters?.[String(anno)]||0);
      if(counter<maxExisting){
        if(!isAdmin()){
          toast('Numerazione non allineata: accedi come amministratore per riallineare il progressivo','err');
          return;
        }
        counter=await window.firebaseBridge.ensureCounterAtLeast(anno,maxExisting);
        DB.counters[String(anno)]=counter;
      }
      num=await window.firebaseBridge.nextCounter(anno);
      DB.counters[String(anno)]=num;
      if(num<=maxExisting || Object.values(DB.partite).some(p=>+p.anno===+anno && +p.num===+num)){
        toast('Progressivo non valido: creazione interrotta per evitare un duplicato','err');
        return;
      }
    }catch(e){toast('Impossibile assegnare il progressivo della partita','err');return;}
  }
  const cer=document.getElementById('pcer_val').value;'''
if old_save_head not in s:
    raise SystemExit('Testata savePartita non trovata')
s = s.replace(old_save_head, new_save_head, 1)

# 4) Numero e anno restano esplicitamente immutabili anche in caso di future
#    modifiche al form di editing.
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

# Verifiche finali.
required = [
    'Math.max(maxExisting,counter)+1',
    'async ensureCounterAtLeast(year,floor)',
    'Numerazione non allineata',
    'p.num=immutableNum',
    'p.anno=immutableAnno',
]
for token in required:
    if token not in s:
        raise SystemExit('Verifica numerazione fallita: manca '+token)

p.write_text(s, encoding='utf-8')
print('Protezione numerazione partite applicata')
