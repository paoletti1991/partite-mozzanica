from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import csv
import io
import json
import re
from datetime import date

ENDPOINT = 'https://publications.europa.eu/webapi/rdf/sparql'
SCHEME = 'http://data.europa.eu/6p8/low2015/scheme'
EXPECTED_LEAF_CODES = 842
EXPECTED_CHAPTERS = 20

query = f'''PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?notation ?label
WHERE {{
  ?c skos:inScheme <{SCHEME}> ;
     skos:notation ?notation ;
     skos:prefLabel ?label .
  FILTER(lang(?label) = "it")
}}
ORDER BY ?notation'''

qs = urlencode({'query': query, 'format': 'text/csv'})
req = Request(
    ENDPOINT + '?' + qs,
    headers={
        'User-Agent': 'partite-mozzanica-build/1.0',
        'Accept': 'text/csv',
    },
)
with urlopen(req, timeout=60) as response:
    text = response.read().decode('utf-8-sig')

rows = list(csv.DictReader(io.StringIO(text)))
if len(rows) < 900:
    raise SystemExit(f'Catalogo EER ufficiale incompleto: ricevute solo {len(rows)} voci')

chapters = []
leaf = []
seen = set()

for row in rows:
    notation = (row.get('notation') or '').strip()
    label = (row.get('label') or '').strip()
    code = re.sub(r'\D', '', notation)
    if len(code) not in (2, 4, 6):
        continue
    if code in seen:
        raise SystemExit(f'Codice EER duplicato nel catalogo ufficiale: {code}')
    seen.add(code)

    hazard = '*' in notation
    pretty = ' '.join(code[i:i+2] for i in range(0, len(code), 2))
    desc = re.sub(r'^\s*\d{2}(?:\s+\d{2}){0,2}\s*\*?\s*', '', label, count=1).strip()
    if not desc:
        raise SystemExit(f'Descrizione italiana mancante per {notation}')

    if len(code) == 2:
        chapters.append({'code': code, 'desc': desc, 'chapter': True})
    elif len(code) == 6:
        leaf.append({'code': code, 'pretty': pretty, 'desc': desc, 'hazard': hazard})

if len(chapters) != EXPECTED_CHAPTERS:
    raise SystemExit(f'Capitoli EER inattesi: {len(chapters)} invece di {EXPECTED_CHAPTERS}')
if len(leaf) != EXPECTED_LEAF_CODES:
    raise SystemExit(f'Codici EER a 6 cifre inattesi: {len(leaf)} invece di {EXPECTED_LEAF_CODES}')

leaf_by_code = {item['code']: item for item in leaf}
for code in ('010304', '150110', '160601', '200135'):
    if code not in leaf_by_code or not leaf_by_code[code]['hazard']:
        raise SystemExit(f'Verifica pericolosità fallita per {code}')
for code in ('010101', '150101', '160604', '200136'):
    if code not in leaf_by_code or leaf_by_code[code]['hazard']:
        raise SystemExit(f'Verifica non pericoloso fallita per {code}')
for code in ('010309', '170201', '200138'):
    if code not in leaf_by_code:
        raise SystemExit(f'Verifica completezza fallita: manca {code}')

# La decisione delegata (UE) 2025/934 modifica l'elenco per i rifiuti di batterie,
# ma, dopo la rettifica pubblicata il 19/08/2025, si applica dal 09/12/2026.
# Evitiamo di distribuire automaticamente l'elenco 2015 oltre tale data senza
# aggiornare questa sorgente ufficiale alla nuova versione applicabile.
if date.today() >= date(2026, 12, 9):
    raise SystemExit(
        'Dal 09/12/2026 si applica la Decisione delegata (UE) 2025/934: '
        'aggiornare la sorgente EER prima di pubblicare.'
    )

chapter_by_code = {item['code']: item for item in chapters}
catalog = []
for chapter_code in sorted(chapter_by_code):
    catalog.append(chapter_by_code[chapter_code])
    catalog.extend(sorted((x for x in leaf if x['code'].startswith(chapter_code)), key=lambda x: x['code']))

p = Path('public/index.html')
s = p.read_text(encoding='utf-8')
start = s.index('const CER_DATA = ')
script_end = s.index('\n</script>', start)
new_decl = 'const CER_DATA = ' + json.dumps(catalog, ensure_ascii=False, separators=(',', ':')) + ';'
s = s[:start] + new_decl + s[script_end:]

# Terminologia e indicazioni uniformi in tutti i campi EER/CER.
s = s.replace('placeholder="Cerca CER: codice o descrizione…"', 'placeholder="Cerca EER (CER): codice o descrizione…"')
s = s.replace('<label>Codice CER <span class="req">*</span></label>', '<label>Codice EER (CER) <span class="req">*</span></label>')
s = s.replace('<label>CER frazione</label>', '<label>Codice EER (CER) frazione</label>')
s = s.replace('Elenco EER (Dec. 2000/532/CE). Digita codice o descrizione; * = pericoloso.', 'Elenco europeo dei rifiuti vigente (Decisione 2000/532/CE). Digita codice o descrizione; * = pericoloso.')
s = s.replace("toast('Seleziona un codice CER','err')", "toast('Seleziona un codice EER (CER) valido dall’elenco','err')")

# Ricerca per più parole, ignorando accenti e punteggiatura del codice.
old_build = """  function build(q){
    q=(q||'').toLowerCase().trim();
    const out=[]; let curChap=null;
    CER_DATA.forEach(c=>{
      if(c.chapter){ curChap=c; return; }
      const hay=(c.pretty+' '+c.desc).toLowerCase();
      if(!q || hay.includes(q) || c.code.includes(q.replace(/\\s/g,''))){"""
new_build = """  function build(q){
    const norm=v=>String(v||'').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase().trim();
    const raw=norm(q), compact=raw.replace(/[^0-9a-z]/g,'');
    const terms=raw.split(/\\s+/).filter(Boolean);
    const out=[]; let curChap=null;
    CER_DATA.forEach(c=>{
      if(c.chapter){ curChap=c; return; }
      const hay=norm(c.pretty+' '+c.desc), codeCompact=c.code;
      if(!raw || terms.every(t=>hay.includes(t)) || (compact && codeCompact.includes(compact))){"""
if old_build not in s:
    raise SystemExit('Blocco ricerca CER/EER non trovato')
s = s.replace(old_build, new_build, 1)

# Evita che in una frazione venga digitato testo libero non presente nell'elenco.
old_fraz = """    const fraz=[];
    document.querySelectorAll('#l_frazlist .sec').forEach(sec=>{
      const i=sec.id.split('_')[1];
      const lab=document.getElementById('fz_lab_'+i)?.value.trim()||'Frazione';
      const fkg=+document.getElementById('fz_kg_'+i)?.value;
      const fcer=document.getElementById('fz_cerval_'+i)?.value||source.cer;
      if(fkg>0) fraz.push({id:lav.id+'_fr_'+i,label:lab,kg:fkg,cer:fcer});
    });
    if(!fraz.length){ toast('Aggiungi almeno una frazione','err'); return; }"""
new_fraz = """    const fraz=[]; let invalidFrazCer=false;
    document.querySelectorAll('#l_frazlist .sec').forEach(sec=>{
      const i=sec.id.split('_')[1];
      const lab=document.getElementById('fz_lab_'+i)?.value.trim()||'Frazione';
      const fkg=+document.getElementById('fz_kg_'+i)?.value;
      const visibleCer=(document.getElementById('fz_cer_'+i)?.value||'').trim();
      const selectedCer=document.getElementById('fz_cerval_'+i)?.value||'';
      if(fkg>0 && visibleCer && !selectedCer){ invalidFrazCer=true; return; }
      const fcer=selectedCer||source.cer;
      if(fkg>0) fraz.push({id:lav.id+'_fr_'+i,label:lab,kg:fkg,cer:fcer});
    });
    if(invalidFrazCer){ toast('Seleziona un codice EER (CER) valido dall’elenco','err'); return; }
    if(!fraz.length){ toast('Aggiungi almeno una frazione','err'); return; }"""
if old_fraz not in s:
    raise SystemExit('Blocco frazioni CER/EER non trovato')
s = s.replace(old_fraz, new_fraz, 1)

# Dati selezionati tramite combobox devono esistere sempre nel catalogo ufficiale.
s = s.replace("if(!cer){ toast('Seleziona un codice EER (CER) valido dall’elenco','err'); return; }", "if(!cer || !cerByCode[cer]){ toast('Seleziona un codice EER (CER) valido dall’elenco','err'); return; }")

# Controlli finali sul build generato.
if s.count('Codice EER (CER)') < 3:
    raise SystemExit('Non tutti i campi CER sono stati convertiti a EER (CER)')
if '"code":"010309"' not in s or '"code":"200138"' not in s:
    raise SystemExit('Catalogo EER completo non inserito nel file finale')

p.write_text(s, encoding='utf-8')
print(f'Catalogo EER ufficiale caricato: {len(leaf)} codici, {len(chapters)} capitoli')
