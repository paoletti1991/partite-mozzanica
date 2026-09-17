from pathlib import Path

p = Path('public/index.html')
s = p.read_text(encoding='utf-8')


def patch_section(text, start_token, end_token):
    start = text.index(start_token)
    end = text.index(end_token, start)
    block = text[start:end]

    old_header = '<th>Partita</th><th>Produttore</th>'
    new_header = '<th>Partita</th><th>Formulario ingresso</th><th>Produttore</th>'
    if old_header not in block:
        raise SystemExit(f'Header elenco partite non trovato in {start_token}')
    block = block.replace(old_header, new_header, 1)

    old_prod = '<td>${esc(prodName(p.produttoreId))}</td>'
    new_prod = '<td class="mono">${esc((p.formulariIngresso||[]).map(f=>f.numero||\'—\').join(\', \')||\'—\')}</td><td>${esc(prodName(p.produttoreId))}</td>'
    if old_prod not in block:
        raise SystemExit(f'Riga produttore non trovata in {start_token}')
    block = block.replace(old_prod, new_prod, 1)

    return text[:start] + block + text[end:]


# Elenco partite per operatori.
s = patch_section(
    s,
    'function viewPartiteOperational(){',
    'function viewPartitaDetailOperational(){'
)

# Elenco partite per amministratore.
s = patch_section(
    s,
    'function viewPartite(){',
    'function viewPartitaDetail(){'
)

# Verifica che la colonna sia presente in entrambe le viste.
if s.count('<th>Formulario ingresso</th>') < 2:
    raise SystemExit('Verifica fallita: la colonna Formulario ingresso non è presente in entrambe le viste')

p.write_text(s, encoding='utf-8')
