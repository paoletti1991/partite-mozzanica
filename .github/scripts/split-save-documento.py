from pathlib import Path
import re
import subprocess
import tempfile

path = Path('public/index.html')
text = path.read_text(encoding='utf-8')

old = '''function saveDocumento(){
  const num=document.getElementById('d_num').value.trim();
  const dest=document.getElementById('d_dest').value.trim();
  if(!num){ toast('N. documento obbligatorio','err'); return; }
  if(!dest){ toast('Destinatario obbligatorio','err'); return; }
  const righe=[];
  document.querySelectorAll('#d_disp .selrow').forEach((row,i)=>{
    const sel=document.getElementById('sel_'+i); if(!sel||!sel.checked)return;
    const saldo=document.getElementById('saldo_'+i).checked;
    const inp=document.getElementById('kg_'+i); const max=+inp.dataset.max;
    let kgv=saldo?max:+inp.value;
    if(!kgv||kgv<=0){ return; }
    if(kgv>max+0.001){ toast('Kg oltre la giacenza per '+DB.partite[sel.dataset.pid].num+'-Raee','err'); kgv=null; return; }
    righe.push({id:uid('riga'),partitaId:sel.dataset.pid, lotto:sel.dataset.lot, kg:kgv, saldo});
  });
  if(!righe.length){ toast('Seleziona almeno una partita con kg validi','err'); return; }
  const traspId=document.getElementById('d_trasp').value;
  const interno=traspId&&DB.trasportatori[traspId]?DB.trasportatori[traspId].interno:false;
  const id=uid('doc');
  DB.documenti[id]={ id, tipo:document.getElementById('d_tipo').value, numero:num,
    data:document.getElementById('d_data').value, destinatario:dest,
    trasportatoreId:traspId||null, trasportoInterno:!!interno,
    trasportoCosto:interno?0:(+document.getElementById('d_tcost').value||0),
    righe, valorizzazione:null, naturaEconomicaBozza:'ricavo', fatturaCliente:null, fatturaCosto:null, createdAt:Date.now() };
  save(); closeModal(); openDocView(id); toast('Documento creato');
}'''

new = '''function saveDocumento(){
  const num=document.getElementById('d_num').value.trim();
  const dest=document.getElementById('d_dest').value.trim();
  if(!num){ toast('N. documento obbligatorio','err'); return; }
  if(!dest){ toast('Destinatario obbligatorio','err'); return; }

  const righe=[];
  document.querySelectorAll('#d_disp .selrow').forEach((row,i)=>{
    const sel=document.getElementById('sel_'+i); if(!sel||!sel.checked)return;
    const saldo=document.getElementById('saldo_'+i).checked;
    const inp=document.getElementById('kg_'+i); const max=+inp.dataset.max;
    let kgv=saldo?max:+inp.value;
    if(!kgv||kgv<=0){ return; }
    if(kgv>max+0.001){ toast('Kg oltre la giacenza per '+DB.partite[sel.dataset.pid].num+'-Raee','err'); kgv=null; return; }
    righe.push({id:uid('riga'),partitaId:sel.dataset.pid,lotto:sel.dataset.lot,kg:kgv,saldo});
  });

  if(!righe.length){ toast('Seleziona almeno una partita con kg validi','err'); return; }

  const traspId=document.getElementById('d_trasp').value;
  const interno=traspId&&DB.trasportatori[traspId]?DB.trasportatori[traspId].interno:false;
  const id=uid('doc');

  DB.documenti[id]={
    id,
    tipo:document.getElementById('d_tipo').value,
    numero:num,
    data:document.getElementById('d_data').value,
    destinatario:dest,
    trasportatoreId:traspId||null,
    trasportoInterno:!!interno,
    righe,
    createdAt:Date.now()
  };

  const createEconomics=hasPermission('economics','read');

  if(createEconomics){
    DB.economics=DB.economics||{};
    DB.economics.documenti=DB.economics.documenti||{};
    DB.economics.documenti[id]={
      trasportoCosto:interno?0:(+document.getElementById('d_tcost').value||0),
      valorizzazione:null,
      naturaEconomicaBozza:'ricavo',
      fatturaCliente:null,
      fatturaCosto:null
    };
  }

  if(!save()){
    delete DB.documenti[id];
    if(createEconomics) delete DB.economics.documenti[id];
    return;
  }

  closeModal();
  openDocView(id);
  toast('Documento creato');
}'''

count = text.count(old)
if count != 1:
    raise RuntimeError(f'saveDocumento: attesa 1 occorrenza esatta, trovate {count}')
text = text.replace(old, new, 1)

# Verifica che il nuovo record operativo non contenga più campi economics.
block = re.search(r'function saveDocumento\(\)\{.*?\n\}\n\n/\* ---- VISTA DOCUMENTO', text, re.S)
if not block:
    raise RuntimeError('Impossibile rileggere saveDocumento modificata')
section = block.group(0)
operational = re.search(r'DB\.documenti\[id\]=\{(.*?)\n  \};', section, re.S)
if not operational:
    raise RuntimeError('Record operativo documento non individuato')
for forbidden in ['trasportoCosto','valorizzazione','naturaEconomicaBozza','fatturaCliente','fatturaCosto']:
    if forbidden in operational.group(1):
        raise RuntimeError(f'Campo economics ancora nel record operativo: {forbidden}')

path.write_text(text, encoding='utf-8')

# Controllo sintattico di tutti gli script inline.
scripts = re.findall(r'<script(?P<attrs>[^>]*)>(?P<body>.*?)</script>', text, flags=re.S | re.I)
with tempfile.TemporaryDirectory() as td:
    for idx, (attrs, body) in enumerate(scripts):
        if 'src=' in attrs:
            continue
        suffix = '.mjs' if 'type="module"' in attrs or "type='module'" in attrs else '.js'
        js_path = Path(td) / f'script_{idx}{suffix}'
        js_path.write_text(body, encoding='utf-8')
        subprocess.run(['node', '--check', str(js_path)], check=True)

print('saveDocumento separata in operativo/economics con sintassi valida.')
