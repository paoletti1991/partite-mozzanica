from pathlib import Path
import re, json, subprocess, tempfile

p=Path('public/index.html')
text=p.read_text(encoding='utf-8')

def sub(pattern,repl,label,flags=re.S):
    global text
    text,n=re.subn(pattern,repl,text,count=1,flags=flags)
    if n!=1:
        raise RuntimeError(f'{label}: count={n}')

def rep(old,new,label):
    global text
    n=text.count(old)
    if n!=1:
        raise RuntimeError(f'{label}: expected 1, found {n}')
    text=text.replace(old,new,1)

# Cloud state
rep(
"let CLOUD={configured:FB_ON,user:null,profile:null,ready:false,syncing:false,lastSync:0,error:'',unsubscribe:null};",
"let CLOUD={configured:FB_ON,user:null,profile:null,ready:false,syncing:false,lastSync:0,error:'',unsubscribe:null,branchUnsubscribers:[],mode:'local',syncedDB:null,saveInFlight:false,savePending:false};",
'cloud state')

# Firebase bridge: legacy + granular branches + transaction counter + audit + safer migration
bridge=r'''window.firebaseBridge={
      configured:true,
      onAuth(callback){return authMod.onAuthStateChanged(auth,callback);},
      signIn(email,password){return authMod.signInWithEmailAndPassword(auth,email,password);},
      signOut(){return authMod.signOut(auth);},
      async readUserProfile(uid){
        const snap=await dbMod.get(dbMod.ref(database,'accessControl/users/'+uid));
        return snap.exists()?snap.val():null;
      },
      async readMeta(){
        const snap=await dbMod.get(dbMod.ref(database,'registroMozzanica/meta'));
        return snap.exists()?snap.val():null;
      },
      async readBranch(section){
        const ref=branchRefs[section];
        if(!ref) throw new Error('Sezione Firebase non valida: '+section);
        const snap=await dbMod.get(ref);
        return snap.exists()?snap.val():null;
      },
      listenBranch(section,callback){
        const ref=branchRefs[section];
        if(!ref) throw new Error('Sezione Firebase non valida: '+section);
        return dbMod.onValue(ref,snap=>callback(snap.exists()?snap.val():null));
      },
      async writeBranchUpdates(updates,auditEntries=[]){
        const payload={...(updates||{})};
        (auditEntries||[]).forEach(entry=>{
          const key=dbMod.push(branchRefs.audit).key;
          payload['audit/'+key]={
            ...entry,
            uid:auth.currentUser?.uid||'',
            at:dbMod.serverTimestamp()
          };
        });
        if(Object.keys(payload).length) await dbMod.update(registroRef,payload);
      },
      async nextCounter(year){
        const ref=dbMod.ref(database,'registroMozzanica/counters/'+String(year));
        const result=await dbMod.runTransaction(ref,current=>(Number(current)||0)+1);
        if(!result.committed) throw new Error('Progressivo non assegnato');
        return +result.snapshot.val();
      },
      async migrateLegacyToBranches(){
        const legacySnap=await dbMod.get(dataRef);
        if(!legacySnap.exists()) throw new Error('Archivio precedente non trovato');

        const wrapper=legacySnap.val();
        const legacy=wrapper?.data;
        if(!legacy) throw new Error('Dati precedenti non trovati');

        const destinationSections=['partite','documenti','produttori','trasportatori','counters','economics'];
        const existing=await Promise.all(destinationSections.map(section=>dbMod.get(branchRefs[section])));
        if(existing.some(snap=>snap.exists())){
          throw new Error('Migrazione interrotta: una o più nuove sezioni contengono già dati');
        }

        const partiteOperative={};
        const documentiOperativi={};
        const economics={partite:{},documenti:{}};
        const counters=JSON.parse(JSON.stringify(legacy.counters||{}));

        Object.entries(legacy.partite||{}).forEach(([id,source])=>{
          const p=JSON.parse(JSON.stringify(source));
          const stored=legacy.economics?.partite?.[id]||{};
          economics.partite[id]={
            fattureAcquisto:stored.fattureAcquisto ?? p.fattureAcquisto ?? [],
            definizioniFornitore:stored.definizioniFornitore ?? p.definizioniFornitore ?? [],
            trasportoIngresso:stored.trasportoIngresso ?? p.trasportoIngresso ?? null
          };
          delete p.fattureAcquisto;
          delete p.definizioniFornitore;
          delete p.trasportoIngresso;
          partiteOperative[id]=p;
          const year=String(p.anno||'');
          if(year) counters[year]=Math.max(+counters[year]||0,+p.num||0);
        });

        Object.entries(legacy.documenti||{}).forEach(([id,source])=>{
          const d=JSON.parse(JSON.stringify(source));
          const stored=legacy.economics?.documenti?.[id]||{};
          economics.documenti[id]={
            trasportoCosto:stored.trasportoCosto ?? d.trasportoCosto ?? 0,
            valorizzazione:stored.valorizzazione ?? d.valorizzazione ?? null,
            naturaEconomicaBozza:stored.naturaEconomicaBozza ?? d.naturaEconomicaBozza ?? null,
            fatturaCliente:stored.fatturaCliente ?? d.fatturaCliente ?? null,
            fatturaCosto:stored.fatturaCosto ?? d.fatturaCosto ?? null
          };
          delete d.trasportoCosto;
          delete d.valorizzazione;
          delete d.naturaEconomicaBozza;
          delete d.fatturaCliente;
          delete d.fatturaCosto;
          documentiOperativi[id]=d;
        });

        await dbMod.update(registroRef,{
          partite:partiteOperative,
          documenti:documentiOperativi,
          produttori:legacy.produttori||{},
          trasportatori:legacy.trasportatori||{},
          counters,
          economics,
          meta:{schemaVersion:3,migratedAt:dbMod.serverTimestamp()}
        });

        return {
          partite:Object.keys(partiteOperative).length,
          documenti:Object.keys(documentiOperativi).length,
          produttori:Object.keys(legacy.produttori||{}).length,
          trasportatori:Object.keys(legacy.trasportatori||{}).length
        };
      },
      async read(){const snap=await dbMod.get(dataRef);return snap.exists()?snap.val():null;},
      write(data){return dbMod.set(dataRef,{data,updatedAt:dbMod.serverTimestamp(),updatedBy:auth.currentUser?.uid||''});},
      listen(callback){return dbMod.onValue(dataRef,snap=>callback(snap.exists()?snap.val():null));},
      async uploadFile(file,path){const target=storageMod.ref(storage,path);await storageMod.uploadBytes(target,file);return storageMod.getDownloadURL(target);},
      currentUser(){return auth.currentUser;}
    };'''
sub(r"window\.firebaseBridge=\{.*?\n\s*\};\n\s*window\.dispatchEvent\(new CustomEvent\('firebase-bridge-ready'",bridge+"\n    window.dispatchEvent(new CustomEvent('firebase-bridge-ready'",'firebase bridge')

# Add meta branch ref if missing
rep("  audit:dbMod.ref(database,'registroMozzanica/audit')\n};","  audit:dbMod.ref(database,'registroMozzanica/audit'),\n  meta:dbMod.ref(database,'registroMozzanica/meta')\n};",'meta branch ref')

# Economics access is denied in-memory too for users without permission.
rep("""  const stored=DB.economics?.partite?.[p.id];""","""  if(FB_ON && CLOUD.user && !hasPermission('economics','read')){
    return {fattureAcquisto:[],definizioniFornitore:[],trasportoIngresso:null};
  }

  const stored=DB.economics?.partite?.[p.id];""",'partita economics gate')
rep("""  const stored=DB.economics?.documenti?.[d.id];""","""  if(FB_ON && CLOUD.user && !hasPermission('economics','read')){
    return {trasportoCosto:0,valorizzazione:null,naturaEconomicaBozza:null,fatturaCliente:null,fatturaCosto:null};
  }

  const stored=DB.economics?.documenti?.[d.id];""",'document economics gate')

# Replace local/cloud synchronization layer with user-scoped cache + branch granular sync.
new_layer=r'''function hasBusinessData(data){return !!(data&&(Object.keys(data.partite||{}).length||Object.keys(data.documenti||{}).length||Object.keys(data.produttori||{}).length||Object.keys(data.trasportatori||{}).length));}
function cloneData(value){return JSON.parse(JSON.stringify(value));}
function localKey(base){return (FB_ON&&CLOUD.user?.uid)?base+'_'+CLOUD.user.uid:base;}
function load(useLegacyFallback=false){
  try{
    const key=localKey(LS_KEY);
    let raw=localStorage.getItem(key);
    if(!raw&&useLegacyFallback&&key!==LS_KEY) raw=localStorage.getItem(LS_KEY);
    DB=raw?normalizeDB(JSON.parse(raw)):emptyDB();
  }catch(e){DB=emptyDB();}
}
function persistLocal(data,keepPrevious){
  try{
    const key=localKey(LS_KEY), prevKey=localKey(LS_PREV_KEY);
    const next=JSON.stringify(data), current=localStorage.getItem(key);
    if(keepPrevious&&current&&current!==next)localStorage.setItem(prevKey,current);
    localStorage.setItem(key,next);return true;
  }catch(e){toast('Copia locale non riuscita: spazio browser insufficiente','err');return false;}
}
function permissionSection(section){return section==='documenti'?'uscite':section;}
function canMutateSection(section,action){return isAdmin()||hasPermission(permissionSection(section),action);}
function changedRecords(base,next){
  const ids=new Set([...Object.keys(base||{}),...Object.keys(next||{})]);
  const out=[];
  ids.forEach(id=>{
    const before=base?.[id], after=next?.[id];
    if(JSON.stringify(before)===JSON.stringify(after)) return;
    const action=before===undefined?'create':after===undefined?'delete':'update';
    out.push({id,before,after,action});
  });
  return out;
}
function granularChanges(base,next){
  const sections=['partite','documenti','produttori','trasportatori','economics'];
  const updates={},audits=[],denied=[];
  sections.forEach(section=>{
    if(section==='economics'){
      ['partite','documenti'].forEach(kind=>{
        changedRecords(base?.economics?.[kind]||{},next?.economics?.[kind]||{}).forEach(ch=>{
          if(!canMutateSection('economics',ch.action)){denied.push('economics.'+kind+':'+ch.action);return;}
          updates['economics/'+kind+'/'+ch.id]=ch.after===undefined?null:cloneData(ch.after);
          audits.push({section:'economics/'+kind,recordId:ch.id,action:ch.action});
        });
      });
      return;
    }
    changedRecords(base?.[section]||{},next?.[section]||{}).forEach(ch=>{
      if(!canMutateSection(section,ch.action)){denied.push(section+':'+ch.action);return;}
      updates[section+'/'+ch.id]=ch.after===undefined?null:cloneData(ch.after);
      audits.push({section,recordId:ch.id,action:ch.action});
    });
  });
  return {updates,audits,denied};
}
function save(){
  DB=normalizeDB(DB);DB._meta.updatedAt=Date.now();DB._meta.device='browser';
  if(CLOUD.user&&CLOUD.mode==='branches'){
    const check=granularChanges(CLOUD.syncedDB||emptyDB(),DB);
    if(check.denied.length){toast('Operazione non autorizzata per questo utente','err');return false;}
  }
  if(!persistLocal(DB,true))return false;
  if(CLOUD.user&&CLOUD.mode==='branches')queueGranularSave();
  else queueCloudSave();
  updateStoreStatus();return true;
}
function queueCloudSave(){
  if(!CLOUD.user||!window.firebaseBridge||!isAdmin()||CLOUD.mode!=='legacy')return;
  clearTimeout(cloudSaveTimer);cloudSaveTimer=setTimeout(pushCloud,450);
}
async function pushCloud(){
  if(!CLOUD.user||!window.firebaseBridge||!isAdmin()||CLOUD.mode!=='legacy')return;
  CLOUD.syncing=true;CLOUD.error='';updateStoreStatus();
  const payload=cloneData(DB);
  try{await window.firebaseBridge.write(payload);CLOUD.lastSync=Date.now();}
  catch(e){CLOUD.error='Sincronizzazione non riuscita; dati conservati in locale';}
  finally{CLOUD.syncing=false;updateStoreStatus();}
}
function queueGranularSave(){
  if(!CLOUD.user||!window.firebaseBridge||CLOUD.mode!=='branches')return;
  clearTimeout(cloudSaveTimer);cloudSaveTimer=setTimeout(flushGranularSave,300);
}
async function flushGranularSave(){
  if(CLOUD.mode!=='branches'||!CLOUD.user)return;
  if(CLOUD.saveInFlight){CLOUD.savePending=true;return;}
  const base=cloneData(CLOUD.syncedDB||emptyDB()), next=cloneData(DB);
  const changes=granularChanges(base,next);
  if(changes.denied.length){CLOUD.error='Modifica non autorizzata';updateStoreStatus();return;}
  if(!Object.keys(changes.updates).length)return;
  CLOUD.saveInFlight=true;CLOUD.syncing=true;CLOUD.error='';updateStoreStatus();
  try{
    await window.firebaseBridge.writeBranchUpdates(changes.updates,changes.audits);
    CLOUD.syncedDB=cloneData(next);
    CLOUD.lastSync=Date.now();
  }catch(e){
    CLOUD.error='Sincronizzazione non riuscita; modifiche conservate in locale';
  }finally{
    CLOUD.saveInFlight=false;CLOUD.syncing=false;updateStoreStatus();
    if(CLOUD.savePending||JSON.stringify(DB)!==JSON.stringify(CLOUD.syncedDB)){
      CLOUD.savePending=false;queueGranularSave();
    }
  }
}
function applyCloudData(wrapper){
  if(!wrapper||!wrapper.data)return false;
  const incoming=normalizeDB(wrapper.data);incoming._meta.updatedAt=+wrapper.updatedAt||+incoming._meta.updatedAt||Date.now();
  DB=incoming;persistLocal(DB,true);render();return true;
}
async function syncInitialCloud(){
  if(!CLOUD.user||!window.firebaseBridge||!isAdmin())return;
  CLOUD.mode='legacy';CLOUD.syncing=true;updateStoreStatus();
  try{
    const remote=await window.firebaseBridge.read();
    const remoteTs=+(remote?.updatedAt||remote?.data?._meta?.updatedAt||0), localTs=+(DB._meta?.updatedAt||0);
    if(remote?.data&&(!hasBusinessData(DB)||remoteTs>localTs))applyCloudData(remote);
    else if(hasBusinessData(DB)||!remote?.data)await window.firebaseBridge.write(cloneData(DB));
    CLOUD.lastSync=Date.now();CLOUD.error='';
    if(CLOUD.unsubscribe)CLOUD.unsubscribe();
    CLOUD.unsubscribe=window.firebaseBridge.listen(next=>{
      const ts=+(next?.updatedAt||next?.data?._meta?.updatedAt||0);
      if(next?.data&&ts>+(DB._meta?.updatedAt||0))applyCloudData(next);
    });
  }catch(e){CLOUD.error='Accesso cloud non disponibile; copia locale attiva';}
  finally{CLOUD.syncing=false;updateStoreStatus();}
}
function branchSections(){
  const out=['partite','documenti','produttori','trasportatori','counters'];
  if(hasPermission('economics','read'))out.push('economics');
  return out;
}
function clearBranchListeners(){
  (CLOUD.branchUnsubscribers||[]).forEach(fn=>{try{fn();}catch(e){}});
  CLOUD.branchUnsubscribers=[];
}
function applyBranch(section,value,doRender=true){
  if(section==='economics'){
    DB.economics=value||{partite:{},documenti:{}};
    DB.economics.partite=DB.economics.partite||{};
    DB.economics.documenti=DB.economics.documenti||{};
  }else DB[section]=value||{};
  DB=normalizeDB(DB);
  if(CLOUD.syncedDB){
    if(section==='economics')CLOUD.syncedDB.economics=cloneData(DB.economics);
    else CLOUD.syncedDB[section]=cloneData(DB[section]);
  }
  persistLocal(DB,false);
  if(doRender)render();
}
async function syncBranchCloud(){
  CLOUD.mode='branches';CLOUD.syncing=true;CLOUD.error='';updateStoreStatus();
  clearBranchListeners();
  try{
    const sections=branchSections();
    const values=await Promise.all(sections.map(s=>window.firebaseBridge.readBranch(s)));
    DB=emptyDB();
    sections.forEach((s,i)=>applyBranch(s,values[i],false));
    CLOUD.syncedDB=cloneData(DB);
    persistLocal(DB,false);
    sections.forEach(section=>{
      const unsub=window.firebaseBridge.listenBranch(section,value=>{
        if(CLOUD.saveInFlight||cloudSaveTimer)return;
        applyBranch(section,value,true);
      });
      CLOUD.branchUnsubscribers.push(unsub);
    });
    CLOUD.lastSync=Date.now();render();
  }catch(e){
    load(false);
    CLOUD.syncedDB=cloneData(DB);
    CLOUD.error='Dati cloud non disponibili; visualizzata la cache di questo utente';
    render();
  }finally{CLOUD.syncing=false;updateStoreStatus();}
}
function initCloudBridge(){
  if(CLOUD.ready)return;
  if(!window.firebaseBridge){updateStoreStatus();return;}
  CLOUD.ready=true;
  window.firebaseBridge.onAuth(async user=>{
    CLOUD.user=user||null;CLOUD.profile=null;CLOUD.error='';CLOUD.syncedDB=null;CLOUD.mode='local';
    clearTimeout(cloudSaveTimer);cloudSaveTimer=null;
    if(CLOUD.unsubscribe){CLOUD.unsubscribe();CLOUD.unsubscribe=null;}
    clearBranchListeners();
    if(!user){DB=emptyDB();updateStoreStatus();render();return;}
    try{
      const profile=await window.firebaseBridge.readUserProfile(user.uid);
      if(!profile||profile.active!==true){DB=emptyDB();CLOUD.error='Utente non autorizzato';updateStoreStatus();render();return;}
      CLOUD.profile=profile;
      const meta=await window.firebaseBridge.readMeta();
      if(+meta?.schemaVersion>=3){
        await syncBranchCloud();
      }else if(isAdmin()){
        load(true);
        await syncInitialCloud();
      }else{
        DB=emptyDB();CLOUD.mode='blocked';CLOUD.error='Archivio multiutente non ancora migrato dall’amministratore';render();
      }
      updateStoreStatus();
    }catch(e){
      DB=emptyDB();CLOUD.error='Profilo o archivio utente non disponibile';updateStoreStatus();render();
    }
  });
}
window.addEventListener('firebase-bridge-ready',e=>{
  if(e.detail?.ok)initCloudBridge();else{CLOUD.ready=true;if(!e.detail?.localOnly)CLOUD.error='Firebase non raggiungibile';updateStoreStatus();}
});
window.addEventListener('online',()=>{
  if(!CLOUD.user)return;
  if(CLOUD.mode==='legacy'&&isAdmin())pushCloud();
  if(CLOUD.mode==='branches')queueGranularSave();
});'''
sub(r"function hasBusinessData\(data\)\{.*?window\.addEventListener\('online',\(\)=>\{if\(CLOUD\.user\)pushCloud\(\);\}\);",new_layer,'data sync layer')

# User-scoped previous backup
text=text.replace("localStorage.getItem(LS_PREV_KEY)","localStorage.getItem(localKey(LS_PREV_KEY))")

# Transaction-based number allocation once branch mode is active.
rep("function savePartita(anno){\n  anno=+anno||YEAR;\n  const num=nextNum(anno);","async function savePartita(anno){\n  anno=+anno||YEAR;\n  let num=nextNum(anno);\n  if(CLOUD.user&&CLOUD.mode==='branches'){\n    try{num=await window.firebaseBridge.nextCounter(anno);DB.counters[String(anno)]=num;}\n    catch(e){toast('Impossibile assegnare il progressivo della partita','err');return;}\n  }",'transaction partita number')

# Safe initialization: never render legacy shared cache before Firebase auth resolves.
rep("""/* ---------- INIT ---------- */
load();
if(location.hash){ const [v,id]=location.hash.slice(1).split('/'); ROUTE={view:v||'dash',id:id||null}; }
render();
if(window.firebaseBridge)initCloudBridge();""","""/* ---------- INIT ---------- */
if(location.hash){ const [v,id]=location.hash.slice(1).split('/'); ROUTE={view:v||'dash',id:id||null}; }
if(!FB_ON) load();
else DB=emptyDB();
render();
if(window.firebaseBridge)initCloudBridge();""",'safe init')

# Full multiuser rules, prepared but not deployed by this workflow.
rules={
  "rules":{
    ".read":False,".write":False,
    "accessControl":{"users":{"$uid":{
      ".read":"auth != null && (auth.uid === $uid || auth.uid === '4Kv4dvuYk5RQ7pMVdlCGo0k4uWj1')",
      ".write":"auth != null && auth.uid === '4Kv4dvuYk5RQ7pMVdlCGo0k4uWj1'"}}},
    "registroMozzanica":{
      "current":{
        ".read":"auth != null && auth.uid === '4Kv4dvuYk5RQ7pMVdlCGo0k4uWj1'",
        ".write":"auth != null && auth.uid === '4Kv4dvuYk5RQ7pMVdlCGo0k4uWj1'"
      },
      "meta":{
        ".read":"auth != null && root.child('accessControl/users').child(auth.uid).child('active').val() === true",
        ".write":"auth != null && auth.uid === '4Kv4dvuYk5RQ7pMVdlCGo0k4uWj1'"
      },
      "partite":{
        ".read":"auth != null && root.child('accessControl/users').child(auth.uid).child('active').val() === true && (auth.uid === '4Kv4dvuYk5RQ7pMVdlCGo0k4uWj1' || root.child('accessControl/users').child(auth.uid).child('permissions/partite/read').val() === true)",
        "$id":{
          ".write":"auth != null && root.child('accessControl/users').child(auth.uid).child('active').val() === true && (auth.uid === '4Kv4dvuYk5RQ7pMVdlCGo0k4uWj1' || (!data.exists() && newData.exists() && root.child('accessControl/users').child(auth.uid).child('permissions/partite/create').val() === true) || (data.exists() && newData.exists() && root.child('accessControl/users').child(auth.uid).child('permissions/partite/update').val() === true) || (data.exists() && !newData.exists() && root.child('accessControl/users').child(auth.uid).child('permissions/partite/delete').val() === true))"
        }
      },
      "documenti":{
        ".read":"auth != null && root.child('accessControl/users').child(auth.uid).child('active').val() === true && (auth.uid === '4Kv4dvuYk5RQ7pMVdlCGo0k4uWj1' || root.child('accessControl/users').child(auth.uid).child('permissions/uscite/read').val() === true)",
        "$id":{
          ".write":"auth != null && root.child('accessControl/users').child(auth.uid).child('active').val() === true && (auth.uid === '4Kv4dvuYk5RQ7pMVdlCGo0k4uWj1' || (!data.exists() && newData.exists() && root.child('accessControl/users').child(auth.uid).child('permissions/uscite/create').val() === true) || (data.exists() && newData.exists() && root.child('accessControl/users').child(auth.uid).child('permissions/uscite/update').val() === true) || (data.exists() && !newData.exists() && root.child('accessControl/users').child(auth.uid).child('permissions/uscite/delete').val() === true))"
        }
      },
      "produttori":{
        ".read":"auth != null && root.child('accessControl/users').child(auth.uid).child('active').val() === true && (auth.uid === '4Kv4dvuYk5RQ7pMVdlCGo0k4uWj1' || root.child('accessControl/users').child(auth.uid).child('permissions/produttori/read').val() === true)",
        "$id":{
          ".write":"auth != null && root.child('accessControl/users').child(auth.uid).child('active').val() === true && (auth.uid === '4Kv4dvuYk5RQ7pMVdlCGo0k4uWj1' || (!data.exists() && newData.exists() && root.child('accessControl/users').child(auth.uid).child('permissions/produttori/create').val() === true) || (data.exists() && newData.exists() && root.child('accessControl/users').child(auth.uid).child('permissions/produttori/update').val() === true) || (data.exists() && !newData.exists() && root.child('accessControl/users').child(auth.uid).child('permissions/produttori/delete').val() === true))"
        }
      },
      "trasportatori":{
        ".read":"auth != null && root.child('accessControl/users').child(auth.uid).child('active').val() === true && (auth.uid === '4Kv4dvuYk5RQ7pMVdlCGo0k4uWj1' || root.child('accessControl/users').child(auth.uid).child('permissions/trasportatori/read').val() === true)",
        "$id":{
          ".write":"auth != null && root.child('accessControl/users').child(auth.uid).child('active').val() === true && (auth.uid === '4Kv4dvuYk5RQ7pMVdlCGo0k4uWj1' || (!data.exists() && newData.exists() && root.child('accessControl/users').child(auth.uid).child('permissions/trasportatori/create').val() === true) || (data.exists() && newData.exists() && root.child('accessControl/users').child(auth.uid).child('permissions/trasportatori/update').val() === true) || (data.exists() && !newData.exists() && root.child('accessControl/users').child(auth.uid).child('permissions/trasportatori/delete').val() === true))"
        }
      },
      "counters":{
        ".read":"auth != null && root.child('accessControl/users').child(auth.uid).child('active').val() === true && (auth.uid === '4Kv4dvuYk5RQ7pMVdlCGo0k4uWj1' || root.child('accessControl/users').child(auth.uid).child('permissions/partite/read').val() === true)",
        "$year":{
          ".write":"auth != null && root.child('accessControl/users').child(auth.uid).child('active').val() === true && (auth.uid === '4Kv4dvuYk5RQ7pMVdlCGo0k4uWj1' || root.child('accessControl/users').child(auth.uid).child('permissions/partite/create').val() === true)",
          ".validate":"newData.isNumber() && newData.val() === (data.exists() ? data.val() + 1 : 1)"
        }
      },
      "economics":{
        ".read":"auth != null && root.child('accessControl/users').child(auth.uid).child('active').val() === true && (auth.uid === '4Kv4dvuYk5RQ7pMVdlCGo0k4uWj1' || root.child('accessControl/users').child(auth.uid).child('permissions/economics/read').val() === true)",
        "$kind":{"$id":{
          ".write":"auth != null && root.child('accessControl/users').child(auth.uid).child('active').val() === true && (auth.uid === '4Kv4dvuYk5RQ7pMVdlCGo0k4uWj1' || (!data.exists() && newData.exists() && root.child('accessControl/users').child(auth.uid).child('permissions/economics/create').val() === true) || (data.exists() && newData.exists() && root.child('accessControl/users').child(auth.uid).child('permissions/economics/update').val() === true) || (data.exists() && !newData.exists() && root.child('accessControl/users').child(auth.uid).child('permissions/economics/delete').val() === true))"
        }}
      },
      "audit":{
        ".read":"auth != null && auth.uid === '4Kv4dvuYk5RQ7pMVdlCGo0k4uWj1'",
        "$id":{
          ".write":"auth != null && root.child('accessControl/users').child(auth.uid).child('active').val() === true && !data.exists() && newData.exists() && newData.child('uid').val() === auth.uid"
        }
      }
    }
  }
}
Path('database.rules.json').write_text(json.dumps(rules,ensure_ascii=False,indent=2)+"\n",encoding='utf-8')

p.write_text(text,encoding='utf-8')

# Assertions + syntax checks
assert "CLOUD.mode==='branches'" in text
assert "runTransaction" in text
assert "meta:{schemaVersion:3" in text
assert "if(!FB_ON) load();" in text
json.loads(Path('database.rules.json').read_text(encoding='utf-8'))
scripts=re.findall(r'<script(?P<attrs>[^>]*)>(?P<body>.*?)</script>',text,flags=re.S|re.I)
with tempfile.TemporaryDirectory() as td:
    for i,(attrs,body) in enumerate(scripts):
        if 'src=' in attrs: continue
        ext='.mjs' if 'type="module"' in attrs or "type='module'" in attrs else '.js'
        f=Path(td)/f's{i}{ext}';f.write_text(body,encoding='utf-8')
        subprocess.run(['node','--check',str(f)],check=True)
print('Fondazione multiutente completata; JS e rules validi.')
