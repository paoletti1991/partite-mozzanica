from pathlib import Path

index = Path('public/index.html')
s = index.read_text(encoding='utf-8')

replacements = {
    'In cloud: dati su Realtime Database, PDF su Firebase Storage.': 'In cloud: dati su Firebase Realtime Database; le fatture documentali salvano solo numero e data.',
    "Le fatture d'acquisto (con PDF) e le lavorazioni si aggiungono dal dettaglio partita.": "Le fatture d'acquisto e le lavorazioni si aggiungono dal dettaglio partita.",
    "${eur(f.importo)}${(f.pdf||[]).length?' · '+(f.pdf||[]).map(x=>esc(x.name)).join(', '):''}": "${eur(f.importo)}",
    '  storageBucket: "partite-mozzanica.firebasestorage.app",\n': '',
}

for old, new in replacements.items():
    if old in s:
        s = s.replace(old, new)

required = [
    "function renderOperationalInvoices(kind,id)",
    "function openOperationalInvoice(kind,id)",
    "function saveOperationalInvoice(kind,id)",
    "fattureDocumentaliAcquisto",
    "fattureDocumentaliVendita",
    "openOperationalInvoice('acquisto'",
    "openOperationalInvoice('vendita'",
]
for token in required:
    if token not in s:
        raise SystemExit(f'Manca funzione/aggancio fatture operative: {token}')

for forbidden in [
    'firebase-storage.js',
    'fatture-acquisto/',
    'fatture-vendita/',
    'id="f_pdf"',
    'id="ofi_file"',
]:
    if forbidden in s:
        raise SystemExit(f'Residuo Storage/PDF non atteso: {forbidden}')

index.write_text(s, encoding='utf-8')

cfg = Path('public/firebase-config.js')
if cfg.exists():
    c = cfg.read_text(encoding='utf-8')
    c = c.replace('  storageBucket: "partite-mozzanica.firebasestorage.app",\n', '')
    cfg.write_text(c, encoding='utf-8')
