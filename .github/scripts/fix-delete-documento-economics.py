from pathlib import Path
import re
import subprocess
import tempfile

path=Path('public/index.html')
text=path.read_text(encoding='utf-8')
old='''function deleteDocumento(documentoId){
  const d=DB.documenti[documentoId];
  if(!d){ toast('Documento non trovato','err'); return; }
  if(!window.confirm('Stai per eliminare definitivamente questo documento di uscita. Le quantità delle partite coinvolte torneranno disponibili. L\\'operazione non è reversibile.')) return;

  /* Giacenze, ricavi, utili e valorizzazioni sono calcolati dai documenti presenti:
     rimuovendo il record vengono quindi ripristinati e ricalcolati automaticamente. */
  delete DB.documenti[documentoId];
  if(!save()){ DB.documenti[documentoId]=d; return; }
  closeModal();
  render();
  toast('Documento eliminato e quantità ripristinate');
}'''
new='''function deleteDocumento(documentoId){
  const d=DB.documenti[documentoId];
  if(!d){ toast('Documento non trovato','err'); return; }
  if(!window.confirm('Stai per eliminare definitivamente questo documento di uscita. Le quantità delle partite coinvolte torneranno disponibili. L\\'operazione non è reversibile.')) return;

  const hadEconomics=!!DB.economics?.documenti?.[documentoId];
  const previousEconomics=hadEconomics
    ? JSON.parse(JSON.stringify(DB.economics.documenti[documentoId]))
    : null;

  /* Giacenze, ricavi, utili e valorizzazioni sono calcolati dai documenti presenti:
     rimuovendo il record operativo e quello economics vengono ripristinati e ricalcolati automaticamente. */
  delete DB.documenti[documentoId];
  if(hadEconomics) delete DB.economics.documenti[documentoId];

  if(!save()){
    DB.documenti[documentoId]=d;
    if(hadEconomics) DB.economics.documenti[documentoId]=previousEconomics;
    return;
  }

  closeModal();
  render();
  toast('Documento eliminato e quantità ripristinate');
}'''
count=text.count(old)
if count!=1:
    raise RuntimeError(f'deleteDocumento: attesa 1 occorrenza, trovate {count}')
text=text.replace(old,new,1)
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

print('deleteDocumento aggiornata e sintassi valida')
