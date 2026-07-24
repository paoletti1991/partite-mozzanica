# Registro Partite Mozzanica — Firebase + GitHub

Questa versione usa:

- **Firebase Realtime Database** per conservare i dati operativi;
- **Firebase Authentication** per limitare l'accesso agli utenti autorizzati;
- **Firebase Storage** per i PDF delle fatture;
- **GitHub Pages** per pubblicare il programma;
- una **copia locale automatica** nel browser usato;
- una **copia locale precedente**, ripristinabile dal programma;
- backup manuali in formato **JSON**, esportabili e importabili.

GitHub ospita il programma, mentre i dati restano in Firebase. La configurazione Firebase inserita nel sito non è una password: la protezione reale è affidata ad autenticazione e regole.

## 1. Creare e configurare Firebase

1. Apri Firebase Console e crea un progetto.
2. Aggiungi una **Web App** al progetto.
3. Attiva **Authentication > Metodo di accesso > Email/password**.
4. In **Authentication > Utenti**, crea manualmente gli account autorizzati. Il programma non consente la registrazione pubblica.
5. Crea un **Realtime Database**.
6. Attiva **Storage**.
7. La configurazione della Web App è già inserita in `public/firebase-config.js`.

Esempio:

```javascript
window.REGISTRO_FIREBASE_CONFIG = {
  apiKey: "...",
  authDomain: "nome-progetto.firebaseapp.com",
  databaseURL: "https://nome-progetto-default-rtdb.europe-west1.firebasedatabase.app",
  projectId: "nome-progetto",
  storageBucket: "nome-progetto.firebasestorage.app",
  messagingSenderId: "...",
  appId: "..."
};
```

## 2. Installare le regole di sicurezza

Installa Firebase CLI, accedi e associa la cartella al progetto:

```text
npm install -g firebase-tools
firebase login
```

Il progetto `partite-mozzanica` e l'UID autorizzato sono già inseriti in `.firebaserc`, `database.rules.json` e `storage.rules`. Le regole negano l'accesso a tutti gli altri utenti.

Pubblica le regole:

```text
firebase deploy --only database,storage
```

Per autorizzare altri utenti in futuro, aggiungi il loro UID alle condizioni presenti in entrambi i file delle regole prima di ripubblicarle.

## 3. Pubblicare su GitHub Pages

1. Crea un repository GitHub.
2. Carica nella radice del repository tutto il contenuto di questa cartella.
3. In **Settings > Pages**, imposta come origine **GitHub Actions**.
4. Pubblica sul ramo `main`.

Il flusso `.github/workflows/pages.yml` pubblicherà automaticamente la cartella `public`.

In Firebase Console, aggiungi il dominio GitHub Pages, per esempio `nomeutente.github.io`, tra i **domini autorizzati** di Authentication.

## 4. Primo accesso e recupero dati

1. Apri il programma dall'indirizzo GitHub Pages.
2. Premi **Backup e sincronizzazione** nella barra laterale.
3. Accedi con l'utente creato in Firebase.
4. Se possiedi un precedente backup JSON, usa **Importa backup JSON**.
5. Controlla che in basso appaia **Firebase + copia locale**.

La sincronizzazione iniziale confronta le date: conserva la versione più recente fra Firebase e copia locale. Se Firebase è vuoto, la copia locale viene caricata nel cloud.

## 5. Backup consigliato

Il programma salva automaticamente nel cloud e nel browser, ma è consigliato scaricare anche un backup JSON periodico:

1. premi **Backup e sincronizzazione**;
2. scegli **Scarica backup JSON**;
3. conserva il file in una cartella aziendale sottoposta a backup.

In caso di errore puoi usare **Ripristina copia precedente** oppure importare un JSON.

## Note importanti

- Non usare regole Firebase pubbliche come `".read": true` o `".write": true`.
- La copia del browser dipende dal dispositivo e dal profilo utilizzato; non sostituisce Firebase o il backup JSON.
- Per l'uso normale apri la versione pubblicata su GitHub Pages, non il file con doppio clic tramite `file://`.
- Se il collegamento internet manca, il programma continua a salvare localmente e ritenta la sincronizzazione quando torna online.
