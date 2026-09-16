from pathlib import Path
import re, json, subprocess, tempfile

idx=Path('public/index.html')
text=idx.read_text(encoding='utf-8')

def rep(old,new,label):
    global text
    n=text.count(old)
    if n!=1:
        raise RuntimeError(f'{label}: expected 1, found {n}')
    text=text.replace(old,new,1)

# 1. Load only RTDB branches the current user is actually allowed to read.
rep("""function branchSections(){
  const out=['partite','documenti','produttori','trasportatori','counters'];
  if(hasPermission('economics','read'))out.push('economics');
  return out;
}""","""function branchSections(){
  const out=[];
  if(hasPermission('partite','read')){
    out.push('partite');
    out.push('counters');
  }
  if(hasPermission('uscite','read'))out.push('documenti');
  if(hasPermission('produttori','read'))out.push('produttori');
  if(hasPermission('trasportatori','read'))out.push('trasportatori');
  if(hasPermission('economics','read'))out.push('economics');
  return out;
}""",'permission-aware branchSections')

# 2. Refresh after a completed granular save so remote changes skipped during the write are recovered.
rep("""function applyBranch(section,value,doRender=true){
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
async function syncBranchCloud(){""","""function applyBranch(section,value,doRender=true){
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
async function refreshBranchCloud(){
  if(CLOUD.mode!=='branches'||!CLOUD.user||CLOUD.saveInFlight)return false;
  if(JSON.stringify(DB)!==JSON.stringify(CLOUD.syncedDB))return false;
  const sections=branchSections();
  const values=await Promise.all(sections.map(s=>window.firebaseBridge.readBranch(s)));
  const fresh=emptyDB();
  sections.forEach((section,i)=>{
    if(section==='economics'){
      fresh.economics=values[i]||{partite:{},documenti:{}};
      fresh.economics.partite=fresh.economics.partite||{};
      fresh.economics.documenti=fresh.economics.documenti||{};
    }else fresh[section]=values[i]||{};
  });
  DB=normalizeDB(fresh);
  CLOUD.syncedDB=cloneData(DB);
  persistLocal(DB,false);
  render();
  return true;
}
async function syncBranchCloud(){""",'refreshBranchCloud')

rep("""    await window.firebaseBridge.writeBranchUpdates(changes.updates,changes.audits);
    CLOUD.syncedDB=cloneData(next);
    CLOUD.lastSync=Date.now();""","""    await window.firebaseBridge.writeBranchUpdates(changes.updates,changes.audits);
    CLOUD.syncedDB=cloneData(next);
    CLOUD.lastSync=Date.now();""",'locate granular success')
# Insert refresh in finally only when no newer local mutation is pending.
rep("""    if(CLOUD.savePending||JSON.stringify(DB)!==JSON.stringify(CLOUD.syncedDB)){
      CLOUD.savePending=false;queueGranularSave();
    }
  }
}""","""    if(CLOUD.savePending||JSON.stringify(DB)!==JSON.stringify(CLOUD.syncedDB)){
      CLOUD.savePending=false;queueGranularSave();
    }else{
      refreshBranchCloud().catch(()=>{});
    }
  }
}""",'post-save refresh')

# 3. Choose a route the user can actually view instead of always falling back to dashboard.
rep("""function render(){
  const years=availableYears();
  if(!years.includes(YEAR)) YEAR=new Date().getFullYear();

  if(CLOUD.user && CLOUD.profile && !canViewSection(ROUTE.view)){
    ROUTE={view:'dash',id:null};

    if(location.hash!=='#dash'){
      history.replaceState(null,'','#dash');
    }

    toast('Non hai i permessi per accedere a questa sezione','err');
  }

  renderNav(); renderYears();""","""function firstAllowedView(){
  return ['dash','partite','uscite','rimanenze','dafornitore','report','produttori','trasportatori']
    .find(canViewSection)||null;
}
function render(){
  const years=availableYears();
  if(!years.includes(YEAR)) YEAR=new Date().getFullYear();

  if(CLOUD.user && CLOUD.profile && !canViewSection(ROUTE.view)){
    const fallback=firstAllowedView();
    if(fallback){
      ROUTE={view:fallback,id:null};
      if(location.hash!=='#'+fallback)history.replaceState(null,'','#'+fallback);
    }
  }

  renderNav(); renderYears();""",'permission route fallback')

# 4. New partite must be operational-only. Keep economics physically separate.
rep("""  DB.partite[id]={ id, num, anno, cer, kgIngresso:kgv, produttoreId:prod,
    dataIngresso,
    formulariIngresso: form?[{numero:form,data:document.getElementById('p_formdata').value}]:[],
    fattureAcquisto:[], definizioniFornitore:[], lavorazioni:[], trasportoIngresso:null,
    createdAt:Date.now() };
  save(); closeModal(); go('partita',id); toast('Partita '+num+'-Raee registrata');""","""  DB.partite[id]={ id, num, anno, cer, kgIngresso:kgv, produttoreId:prod,
    dataIngresso,
    formulariIngresso: form?[{numero:form,data:document.getElementById('p_formdata').value}]:[],
    lavorazioni:[],
    createdAt:Date.now() };
  if(!save()){
    delete DB.partite[id];
    return;
  }
  closeModal(); go('partita',id); toast('Partita '+num+'-Raee registrata');""",'operational savePartita')

# 5. Economics creation/edit/delete checks use action permissions, not just read.
rep("const createEconomics=hasPermission('economics','read');","const createEconomics=canMutateSection('economics','create');",'saveDocumento economics create permission')
text=text.replace("if(!requirePermission('economics','read')||!isAdmin())return;","if(!requirePermission('economics','create'))return;",2)
text=text.replace("if(!requirePermission('economics','read')||!isAdmin())return;","if(!requirePermission('economics','delete'))return;",1)
text=text.replace("if(!requirePermission('economics','read')||!isAdmin())return;","if(!requirePermission('economics','update'))return;",1)
if "if(!requirePermission('economics','read')||!isAdmin())return;" in text:
    raise RuntimeError('Residual admin-only economics guard found')

# 6. Do not let a stale listener overwrite local work; post-save refresh handles skipped events.
# Existing listener already skips while save is in flight/timer. Keep it by assertion.
if "if(CLOUD.saveInFlight||cloudSaveTimer)return;" not in text:
    raise RuntimeError('Expected branch listener protection missing')

idx.write_text(text,encoding='utf-8')

# 7. Harden rules: economics can only contain the two known child collections.
rules_path=Path('database.rules.json')
rules=json.loads(rules_path.read_text(encoding='utf-8'))
econ=rules['rules']['registroMozzanica']['economics']['$kind']
econ['.validate']="$kind === 'partite' || $kind === 'documenti'"
rules_path.write_text(json.dumps(rules,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# Static checks.
assert "fattureAcquisto:[], definizioniFornitore:[]" not in text
assert "const createEconomics=canMutateSection('economics','create');" in text
assert "async function refreshBranchCloud()" in text
assert "function firstAllowedView()" in text
assert "if(hasPermission('uscite','read'))out.push('documenti');" in text
assert rules['rules']['registroMozzanica']['economics']['$kind']['.validate']

scripts=re.findall(r'<script(?P<attrs>[^>]*)>(?P<body>.*?)</script>',text,flags=re.S|re.I)
with tempfile.TemporaryDirectory() as td:
    for i,(attrs,body) in enumerate(scripts):
        if 'src=' in attrs: continue
        ext='.mjs' if 'type="module"' in attrs or "type='module'" in attrs else '.js'
        f=Path(td)/f's{i}{ext}'
        f.write_text(body,encoding='utf-8')
        subprocess.run(['node','--check',str(f)],check=True)
json.loads(rules_path.read_text(encoding='utf-8'))
print('Hardening multiutente finale completato; JavaScript e rules validi.')
