from pathlib import Path
import re
import subprocess
import tempfile

path = Path('public/index.html')
text = path.read_text(encoding='utf-8')


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: attesa 1 occorrenza, trovate {count}')
    text = text.replace(old, new, 1)


replace_once(
    "  const missingPurchase=ps.filter(p=>!(p.fattureAcquisto||[]).some(f=>(+f.importo||0)>0));",
    """  const missingPurchase=ps.filter(p=>
    !(partitaEconomicsData(p).fattureAcquisto||[])
      .some(f=>(+f.importo||0)>0)
  );""",
    'dashboard acquisti senza valore',
)

replace_once(
    """function viewPartitaDetail(){
  const p = DB.partite[ROUTE.id];
  if(!p) return emptyState('Partita non trovata','');
  const e = partitaEconomics(p); const ekgI=eurokgIngresso(p); const g=giacenza(p);""",
    """function viewPartitaDetail(){
  const p = DB.partite[ROUTE.id];
  if(!p) return emptyState('Partita non trovata','');
  const ecoPartita = partitaEconomicsData(p);
  const e = partitaEconomics(p); const ekgI=eurokgIngresso(p); const g=giacenza(p);""",
    'accessor economics dettaglio partita',
)

replace_once(
    """        ${(p.fattureAcquisto||[]).length? `<table><thead><tr><th>N. fattura</th><th>Data</th><th>Importo</th><th>Allegati</th><th></th></tr></thead><tbody>
        ${p.fattureAcquisto.map(f=>`<tr><td class=\"mono\">${esc(f.numero||'—')}</td><td>${dfmt(f.data)}</td><td class=\"num\">${eur(f.importo)}</td>""",
    """        ${(ecoPartita.fattureAcquisto||[]).length? `<table><thead><tr><th>N. fattura</th><th>Data</th><th>Importo</th><th>Allegati</th><th></th></tr></thead><tbody>
        ${(ecoPartita.fattureAcquisto||[]).map(f=>`<tr><td class=\"mono\">${esc(f.numero||'—')}</td><td>${dfmt(f.data)}</td><td class=\"num\">${eur(f.importo)}</td>""",
    'fatture acquisto dettaglio partita',
)

replace_once(
    """        ${p.trasportoIngresso?`<div class=\"kv\"><span class=\"k\">Trasp. ingresso</span><span class=\"v\">${eur(p.trasportoIngresso.importo)}</span></div>`:''}""",
    """        ${ecoPartita.trasportoIngresso?`<div class=\"kv\"><span class=\"k\">Trasp. ingresso</span><span class=\"v\">${eur(ecoPartita.trasportoIngresso.importo)}</span></div>`:''}""",
    'trasporto ingresso dettaglio partita',
)

replace_once(
    """        <td>${uscitaValorizzata(d)?(naturaValorizzazione(d)==='costo'?'<span class=\"tag haz\">costo / perdita</span>':(d.fatturaCliente?'<span class=\"tag green\">ricavo fatturato</span>':'<span class=\"tag brass\">ricavo da fatturare</span>')):'<span class=\"tag amber\">da valorizzare</span>'}</td></tr>`;""",
    """        <td>${uscitaValorizzata(d)?(naturaValorizzazione(d)==='costo'?'<span class=\"tag haz\">costo / perdita</span>':(documentoEconomicoUscita(d)?'<span class=\"tag green\">ricavo fatturato</span>':'<span class=\"tag brass\">ricavo da fatturare</span>')):'<span class=\"tag amber\">da valorizzare</span>'}</td></tr>`;""",
    'stato fattura uscita',
)

replace_once(
    """function reportPartitaHtml(p,nested){
  const prod=DB.produttori[p.produttoreId]||{};
  const lavs=p.lavorazioni||[], formulari=p.formulariIngresso||[], fatture=p.fattureAcquisto||[], definizioni=p.definizioniFornitore||[];""",
    """function reportPartitaHtml(p,nested){
  const prod=DB.produttori[p.produttoreId]||{};
  const ecoPartita=partitaEconomicsData(p);
  const lavs=p.lavorazioni||[], formulari=p.formulariIngresso||[], fatture=ecoPartita.fattureAcquisto||[], definizioni=ecoPartita.definizioniFornitore||[];""",
    'economics report partita',
)

replace_once(
    """      ${p.trasportoIngresso?`<tr><td>Trasporto ingresso</td><td>—</td><td>—</td><td>${eur(p.trasportoIngresso.importo)}</td></tr>`:''}
      ${!formulari.length&&!fatture.length&&!definizioni.length&&!p.trasportoIngresso?'<tr><td colspan=\"4\">Nessun documento di ingresso o acquisto registrato.</td></tr>':''}""",
    """      ${ecoPartita.trasportoIngresso?`<tr><td>Trasporto ingresso</td><td>—</td><td>—</td><td>${eur(ecoPartita.trasportoIngresso.importo)}</td></tr>`:''}
      ${!formulari.length&&!fatture.length&&!definizioni.length&&!ecoPartita.trasportoIngresso?'<tr><td colspan=\"4\">Nessun documento di ingresso o acquisto registrato.</td></tr>':''}""",
    'trasporto ingresso report partita',
)

path.write_text(text, encoding='utf-8')

# Verifica sintattica dei blocchi JavaScript inline.
scripts = re.findall(r'<script(?P<attrs>[^>]*)>(?P<body>.*?)</script>', text, flags=re.S | re.I)
with tempfile.TemporaryDirectory() as td:
    for idx, (attrs, body) in enumerate(scripts):
        if 'src=' in attrs:
            continue
        suffix = '.mjs' if 'type="module"' in attrs or "type='module'" in attrs else '.js'
        js_path = Path(td) / f'script_{idx}{suffix}'
        js_path.write_text(body, encoding='utf-8')
        subprocess.run(['node', '--check', str(js_path)], check=True)

print('Refactor delle letture economics completato con sintassi valida.')
