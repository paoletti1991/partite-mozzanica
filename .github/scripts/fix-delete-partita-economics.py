from pathlib import Path
import re
import subprocess
import tempfile

path=Path('public/index.html')
text=path.read_text(encoding='utf-8')

new='''function deletePartita(partitaId){
  const p=DB.partite[partitaId];
  if(!p){ toast('Partita non trovata','err'); return; }

  const reasons=[];
  const docs=Object.values(DB.documenti).filter(d=>(d.righe||[]).some(r=>r.partitaId===partitaId));
  if((p.lavorazioni||[]).length) reasons.push('sono presenti lavorazioni interne');
  if(docs.length) reasons.push('è utilizzata in '+docs.length+' document'+(docs.length===1?'o di uscita':'i di uscita'));

  const otherStores=Object.keys(DB).filter(k=>!['partite','documenti','counters','economics'].includes(k) && containsReference(DB[k],partitaId));
  if(otherStores.length) reasons.push('esistono altri record collegati ('+otherStores.join(', ')+')');

  if(reasons.length){
    modal(`<div class="modal"><div class="modal-h"><h3>Impossibile eliminare la partita</h3><button class="x" onclick="closeModal()">&times;</button></div>
      <div class="modal-b"><p style="margin:0 0 10px">La partita <b>${p.num}-Raee ${p.anno}</b> non pu&ograve; essere eliminata in sicurezza perch&eacute;:</p>
      <ul style="margin:0;padding-left:20px">${reasons.map(r=>`<li>${esc(r)}</li>`).join('')}</ul>
      <p class="hint" style="margin:12px 0 0">Rimuovi prima le lavorazioni o i documenti indicati e riprova.</p></div>
      <div class="modal-f"><button class="btn" onclick="closeModal()">Chiudi</button></div></div>`);
    toast('Eliminazione bloccata: la partita ha record collegati','err');
    return;
  }

  if(!window.confirm('Stai per eliminare definitivamente questa partita, incluse fatture, formulari e trasporto di ingresso collegati. L\\'operazione non è reversibile.')) return;

  const hadEconomics=!!DB.economics?.partite?.[partitaId];
  const previousEconomics=hadEconomics
    ? JSON.parse(JSON.stringify(DB.economics.partite[partitaId]))
    : null;

  delete DB.partite[partitaId];
  if(hadEconomics) delete DB.economics.partite[partitaId];

  if(!save()){
    DB.partite[partitaId]=p;
    if(hadEconomics) DB.economics.partite[partitaId]=previousEconomics;
    return;
  }

  ROUTE={view:'partite',id:null};
  history.replaceState(null,'','#partite');
  render();
  toast('Partita '+p.num+'-Raee eliminata');
}'''

pattern=r"function deletePartita\(partitaId\)\{.*?\n\}\n\n/\* ---- DOCUMENTO DI USCITA ---- \*/"
text,count=re.subn(pattern,new+"\n\n/* ---- DOCUMENTO DI USCITA ---- */",text,count=1,flags=re.S)
if count!=1:
    raise RuntimeError(f'deletePartita: sostituzione fallita, count={count}')

path.write_text(text,encoding='utf-8')

scripts=re.findall(r'<script(?P<attrs>[^>]*)>(?P<body>.*?)</script>',text,flags=re.S|re.I)
with tempfile.TemporaryDirectory() as td:
    for idx,(attrs,body) in enumerate(scripts):
        if 'src=' in attrs:
            continue
        suffix='.mjs' if 'type="module"' in attrs or "type='module'" in attrs else '.js'
        js=Path(td)/f'script_{idx}{suffix}'
        js.write_text(body,encoding='utf-8')
        subprocess.run(['node','--check',str(js)],check=True)

print('deletePartita aggiornata e sintassi valida')
