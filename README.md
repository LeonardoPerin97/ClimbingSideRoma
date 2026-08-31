# ClimbingSide Roma

ClimbingSide Roma è un’applicazione web Django per gestire il catalogo di una palestra
di arrampicata e registrare le ripetizioni degli utenti.

L’applicazione consente di catalogare pareti, vie e boulder, associare immagini e
annotazioni grafiche, raccogliere valutazioni e gradi percepiti e mostrare statistiche
personali e collettive.

Il progetto è una riscrittura indipendente dell’applicazione ClimbingSide originale.
Il codice e il database della precedente applicazione Flask non vengono modificati né
importati.

## Indice

- [Funzionalità](#funzionalità)
- [Regole applicative](#regole-applicative)
- [Ruoli e permessi](#ruoli-e-permessi)
- [Stack tecnologico](#stack-tecnologico)
- [Architettura](#architettura)
- [Struttura del repository](#struttura-del-repository)
- [Modello dei dati](#modello-dei-dati)
- [Installazione locale](#installazione-locale)
- [Configurazione](#configurazione)
- [Email e verifica degli account](#email-e-verifica-degli-account)
- [Immagini e annotazioni](#immagini-e-annotazioni)
- [Test e qualità](#test-e-qualità)
- [Deployment su Northflank](#deployment-su-northflank)
- [Aggiornamento dell’applicazione](#aggiornamento-dellapplicazione)
- [Backup e ripristino](#backup-e-ripristino)
- [Risoluzione dei problemi](#risoluzione-dei-problemi)
- [Sviluppi futuri](#sviluppi-futuri)

## Funzionalità

### Account

- registrazione con username, email e lingua preferita;
- verifica dell’indirizzo email tramite link a scadenza;
- login case-insensitive e logout tramite richiesta `POST`;
- protezione dai tentativi ripetuti di accesso;
- recupero e modifica della password;
- profilo personale modificabile;
- profilo pubblico senza esposizione dell’email;
- interfaccia selezionabile in italiano o inglese;
- elenco pubblico dei climber ordinabile per nome, numero di ripetizioni e grado massimo.

### Pareti

- elenco pubblico delle pareti;
- ricerca e ordinamento;
- conteggio delle vie attive e delle ripetizioni;
- dettaglio della parete con distinzione tra vie e boulder;
- filtro per tipo;
- ordinamento crescente e decrescente per nome, grado, ripetizioni e valutazione media;
- grado ufficiale e grado medio proposto;
- istogramma continuo delle vie per grado, inclusi i Project;
- evidenziazione gialla delle vie completate dall’utente autenticato;
- archiviazione e ripristino senza perdita dello storico.

### Vie e boulder

- catalogo pubblico paginato;
- ricerca per nome;
- filtri per parete, tipo, grado e stato;
- ordinamento per nome, difficoltà, numero di ripetizioni e valutazione media;
- istogramma continuo del catalogo per grado;
- selezione interattiva dell’istogramma: tutte, solo vie o solo boulder;
- dettaglio con grado ufficiale, parete, tipo e route setter;
- numero di ripetizioni, valutazione media e grado medio proposto;
- distribuzione completa dei gradi decimali proposti;
- elenco delle ripetizioni dalla più recente alla meno recente;
- evidenziazione nel catalogo delle vie già completate dall’utente;
- creazione e modifica da parte di RouteSetter e Admin;
- archiviazione conservativa e cancellazione permanente protetta.

### Ripetizioni

Ogni ripetizione contiene:

- utente;
- via o boulder;
- data;
- valutazione intera da 1 a 5;
- grado francese percepito con decimale da 0 a 9;
- risultato dei tentativi: Onsight, Flash, numero di tentativi oppure N.D.;
- data di creazione e ultima modifica.

Ogni utente può registrare una sola ripetizione per via. La ripetizione può essere
modificata o eliminata esclusivamente dal proprietario. Negli elenchi la valutazione è
rappresentata da cinque stelle grigie con riempimento giallo proporzionale e dal solo
valore numerico, senza etichette ridondanti.

### Profili e statistiche

- numero totale di ripetizioni;
- massimo grado ufficiale completato;
- distinzione tra vie e boulder;
- filtro delle ripetizioni per tipo;
- ordinamento per data o grado;
- istogramma delle vie completate per grado;
- distribuzione per parete;
- statistiche collettive per tipo, grado, parete e mese;
- mesi senza attività mostrati esplicitamente;
- informazioni dell’account collocate in fondo al profilo privato.

### Home

La home mostra:

- numero di vie attive, pareti, climber e ripetizioni;
- ultime ripetizioni con Climber, Climb e Grade;
- cinque vie più ripetute;
- immagine hero ricavata dall’immagine aggiornata più recentemente di una via attiva.

### Amministrazione

- Django Admin per utenti autorizzati;
- dashboard operativa `/management/` riservata agli Admin;
- gestione di utenti, ruoli, pareti, vie e immagini;
- registro di audit non modificabile per le operazioni amministrative importanti;
- cancellazioni permanenti con conferma esplicita e protezione dei dati collegati.

## Regole applicative

- L’installazione rappresenta una sola palestra.
- Una parete può contenere contemporaneamente vie e boulder.
- Il campo `Tipo` distingue `Vie` e `Boulder`.
- I nomi di pareti e vie sono univoci senza distinzione tra maiuscole e minuscole.
- Una via può non avere alcun route setter oppure averne uno o più.
- Il grado ufficiale usa la scala francese da `4a` a `9c`.
- Un `Project` rappresenta una via non ancora liberata o graduata e non possiede un grado
  ufficiale.
- Non vengono memorizzate date di apertura o rimozione.
- Le vie storiche vengono archiviate, non eliminate automaticamente.
- Profili e ripetizioni sono pubblici; email e informazioni riservate non lo sono.
- Le date future non sono accettate per le ripetizioni.
- Una via con ripetizioni non può essere eliminata definitivamente.

## Ruoli e permessi

I ruoli sono implementati tramite gruppi e permessi Django, senza ID utente hardcoded.
I gruppi vengono creati e sincronizzati dopo le migrazioni.

| Operazione | User | RouteSetter | Admin |
|---|:---:|:---:|:---:|
| Consultare catalogo e statistiche | ✓ | ✓ | ✓ |
| Creare, modificare o eliminare le proprie ripetizioni | ✓ | ✓ | ✓ |
| Creare e modificare vie | — | ✓ | ✓ |
| Archiviare e ripristinare vie | — | ✓ | ✓ |
| Caricare, sostituire e annotare immagini | — | ✓ | ✓ |
| Eliminare definitivamente immagini | — | — | ✓ |
| Gestire pareti | — | — | ✓ |
| Gestire utenti e ruoli | — | — | ✓ |
| Cancellazioni permanenti | — | — | ✓ |
| Accedere al Django Admin | — | — | ✓ |

I controlli vengono applicati nel backend. Nascondere un pulsante nell’interfaccia non è
considerato un controllo di autorizzazione.

## Stack tecnologico

- Python 3.12–3.14;
- Django 5.2 LTS;
- PostgreSQL 17 in produzione e nello sviluppo Docker;
- SQLite per sviluppo locale rapido e test semplici;
- template Django server-rendered;
- JavaScript leggero senza frontend separato;
- CSS mobile-first;
- Cloudinary per le immagini in produzione;
- WhiteNoise per i file statici;
- Gunicorn come application server;
- `uv` per dipendenze e ambiente virtuale;
- pytest, Ruff, mypy e pre-commit;
- GitHub Actions per CI;
- Docker e Docker Compose;
- Northflank come piattaforma di deployment attuale.

La versione applicativa dichiarata in `pyproject.toml` è `0.9.0`.

## Architettura

L’applicazione utilizza un monolite Django modulare. Il rendering avviene sul server e
JavaScript viene usato solo per interazioni mirate, come menu mobile, campi dinamici,
grafici interattivi e annotazione delle immagini.

```mermaid
flowchart TD
    Browser[Browser mobile o desktop] --> Django[Django e template]
    Django --> PostgreSQL[(PostgreSQL)]
    Django --> Cloudinary[Cloudinary immagini]
    Django --> SMTP[Servizio SMTP]
    Northflank[Northflank health check] --> Django
```

Le responsabilità sono separate in tre applicazioni:

- `accounts`: utenti, autenticazione, profili, lingua, ruoli e rate limiting;
- `climbs`: pareti, vie, ripetizioni, immagini, annotazioni e statistiche di dominio;
- `core`: home, dashboard, audit, health check, logging e storage Cloudinary.

## Struttura del repository

```text
climbingside/
├── apps/
│   ├── accounts/
│   │   ├── admin.py          # gestione utenti e ruoli nel Django Admin
│   │   ├── backends.py       # login case-insensitive
│   │   ├── forms.py          # registrazione e modifica profilo
│   │   ├── middleware.py     # lingua preferita dell’utente
│   │   ├── models.py         # User e LoginAttempt
│   │   ├── rate_limit.py     # blocco temporaneo dei login ripetuti
│   │   ├── roles.py          # gruppi, ruoli e permessi
│   │   ├── services.py       # invio email di verifica
│   │   ├── tokens.py         # token di verifica email
│   │   ├── urls.py           # URL account
│   │   └── views.py          # registrazione, login e profili
│   ├── climbs/
│   │   ├── admin.py          # amministrazione del dominio
│   │   ├── annotations.py    # formato e validazione dell’annotazione JSON
│   │   ├── forms.py          # form pareti, vie, ripetizioni e immagini
│   │   ├── grades.py         # scala francese e ordinamento dei gradi
│   │   ├── images.py         # validazione sicura dei file caricati
│   │   ├── media_services.py # salvataggio e rimozione controllata immagini
│   │   ├── models.py         # Wall, ClimbingRoute, Ascent e RouteImage
│   │   ├── statistics.py     # aggregazioni e istogrammi
│   │   ├── urls.py           # URL catalogo e CRUD
│   │   └── views.py          # viste pubbliche e operative
│   └── core/
│       ├── admin.py          # audit log in sola lettura
│       ├── audit.py          # registrazione eventi amministrativi
│       ├── health.py         # controllo Django + database
│       ├── models.py         # AuditLogEntry
│       ├── storage.py        # adapter Cloudinary
│       ├── urls.py           # home, statistiche, management e health
│       └── views.py          # viste generali
├── config/
│   ├── settings/
│   │   ├── base.py           # impostazioni condivise
│   │   ├── development.py    # sviluppo locale
│   │   ├── test.py           # test automatici
│   │   └── production.py     # produzione, HTTPS, SMTP e Cloudinary
│   ├── logging.py            # log JSON strutturati
│   ├── urls.py               # router principale
│   ├── asgi.py
│   └── wsgi.py
├── locale/                   # traduzioni italiane compilate
├── static/
│   ├── css/app.css           # design system e layout responsive
│   ├── images/               # logo e asset versionati
│   └── js/
│       ├── app.js            # interazioni generali e grafici
│       └── route-annotation.js
├── templates/
│   ├── accounts/             # pagine account
│   ├── climbs/               # cataloghi, dettagli e form
│   ├── components/           # componenti riutilizzabili
│   ├── core/                 # home e dashboard
│   └── base.html             # layout e navigazione condivisi
├── tests/
│   ├── accounts/
│   ├── climbs/
│   └── core/
├── .github/workflows/ci.yml  # GitHub Actions
├── .env.example              # esempio senza credenziali
├── compose.yml               # sviluppo locale con PostgreSQL
├── Dockerfile                # immagine di produzione
├── manage.py
├── pyproject.toml            # dipendenze e configurazione strumenti
└── uv.lock                   # dipendenze bloccate e riproducibili
```

Le migrazioni si trovano nelle cartelle `migrations/` delle singole applicazioni.

## Modello dei dati

| Entità | Scopo e campi principali |
|---|---|
| `User` | Utente Django personalizzato con username, email univoca, lingua preferita e data di verifica email |
| `LoginAttempt` | Contatore temporaneo dei login falliti con identificatore sottoposto a hash |
| `Wall` | Parete con nome univoco e stato attivo/archiviato |
| `ClimbingRoute` | Via o boulder con nome, parete, tipo, grado ufficiale, Project, route setter e stato |
| `Ascent` | Ripetizione autonoma con utente, via, data, rating, grado proposto, tentativi e timestamp |
| `RouteImage` | Unica immagine della via con annotazione JSON versionata e autore del caricamento |
| `AuditLogEntry` | Evento amministrativo con attore, azione, entità, identificativo, metadati non sensibili e timestamp |

Relazioni principali:

- `Wall 1 → N ClimbingRoute`;
- `User N ↔ N ClimbingRoute` per i route setter;
- `User 1 → N Ascent`;
- `ClimbingRoute 1 → N Ascent`;
- `ClimbingRoute 1 → 0..1 RouteImage`.

Vincoli rilevanti:

- una sola ripetizione per coppia utente/via;
- rating compreso tra 1 e 5;
- grado percepito entro la scala supportata;
- tentativi coerenti con il tipo selezionato;
- Project senza grado ufficiale e vie non Project con grado obbligatorio;
- protezione delle relazioni storiche tramite `PROTECT`;
- indici dedicati alle principali query di catalogo e statistiche.

Non esiste un modello `Gym` perché la versione corrente è progettata per una sola
palestra.

## Installazione locale

### Requisiti

- Python 3.12, 3.13 o 3.14;
- [`uv`](https://docs.astral.sh/uv/);
- Git;
- Docker Desktop o Docker Engine, facoltativo.

### Avvio rapido con SQLite

```bash
git clone https://github.com/LeonardoPerin97/ClimbingSideRoma.git
cd ClimbingSideRoma
cp .env.example .env
uv sync --frozen --group dev
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Aprire `http://127.0.0.1:8000/`.

Per usare SQLite, lasciare `DATABASE_URL` commentata o assente in `.env`.

### Dati dimostrativi

```bash
uv run python manage.py seed_demo --dry-run
uv run python manage.py seed_demo
```

`--dry-run` convalida l’operazione e annulla la transazione. Il comando reale è
idempotente e può essere eseguito più volte senza duplicare i dati.

Gli utenti demo:

- non sono amministratori;
- usano indirizzi `example.invalid`;
- possiedono password inutilizzabili;
- non devono essere utilizzati come account reali.

### Avvio con PostgreSQL e Docker

```bash
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

L’applicazione sarà disponibile su `http://127.0.0.1:8000/`.

Comandi utili:

```bash
docker compose ps
docker compose logs -f web
docker compose stop
```

Il volume `postgres_data` conserva il database tra gli arresti dei container.

## Configurazione

Le impostazioni sono lette dalle variabili d’ambiente con `django-environ`.
In locale possono essere inserite in `.env`; in produzione devono essere salvate nel
secret store della piattaforma.

Non commettere mai:

- `.env`;
- password o token;
- database SQLite;
- dump PostgreSQL;
- file caricati dagli utenti;
- credenziali Cloudinary o SMTP.

### Variabili principali

| Variabile | Necessaria | Descrizione |
|---|:---:|---|
| `DJANGO_SETTINGS_MODULE` | sì | `config.settings.development`, `test` o `production` |
| `DJANGO_SECRET_KEY` | sì in produzione | Chiave segreta lunga e casuale |
| `DJANGO_DEBUG` | sì | Deve essere `false` in produzione |
| `DJANGO_ALLOWED_HOSTS` | sì | Host separati da virgola, senza `https://` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | produzione | Origini complete con `https://` |
| `DATABASE_URL` | produzione | Connessione PostgreSQL |
| `DATABASE_CONN_MAX_AGE` | no | Durata connessioni persistenti, default 60 secondi |
| `DJANGO_DEFAULT_LANGUAGE` | no | `it` oppure `en`, default `it` |
| `DJANGO_LOG_LEVEL` | no | Livello di logging, default `INFO` |
| `DJANGO_BYPASS_EMAIL_VERIFICATION` | no | Bypass temporaneo della verifica email |
| `LOGIN_FAILURE_LIMIT` | no | Numero massimo di errori login, default 5 |
| `LOGIN_LOCKOUT_MINUTES` | no | Durata del blocco, default 15 minuti |
| `CLOUDINARY_URL` | produzione | Credenziali Cloudinary nel formato previsto dall’SDK |
| `DJANGO_SECURE_SSL_REDIRECT` | produzione | Forza HTTPS, normalmente `true` |
| `DJANGO_HSTS_SECONDS` | produzione | Durata HSTS; usare con cautela durante il primo setup |
| `EMAIL_HOST` | se bypass disattivo | Server SMTP |
| `EMAIL_PORT` | se bypass disattivo | Generalmente 587 |
| `EMAIL_HOST_USER` | se bypass disattivo | Utente SMTP |
| `EMAIL_HOST_PASSWORD` | se bypass disattivo | Password o API key SMTP |
| `EMAIL_USE_TLS` | se bypass disattivo | Generalmente `true` |
| `DEFAULT_FROM_EMAIL` | se bypass disattivo | Mittente visualizzato |

Per generare una chiave segreta:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### Esempio di host in produzione

```text
DJANGO_ALLOWED_HOSTS=example.code.run,localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=https://example.code.run
```

`127.0.0.1` e `localhost` sono necessari anche per alcuni controlli interni della
piattaforma. In `DJANGO_ALLOWED_HOSTS` non va inserito lo schema; nelle origini CSRF lo
schema HTTPS è obbligatorio.

## Email e verifica degli account

### Comportamento normale

1. L’utente completa la registrazione.
2. L’account viene creato inattivo.
3. Django invia un link di verifica.
4. Il link attiva l’account e registra la data di verifica.
5. Il recupero password utilizza lo stesso servizio SMTP.

La registrazione e il reinvio non rivelano pubblicamente se un indirizzo è già presente.
In sviluppo le email vengono stampate nel terminale tramite il backend console.

### Bypass temporaneo

Se l’SMTP non è ancora disponibile:

```text
DJANGO_BYPASS_EMAIL_VERIFICATION=true
```

Con il bypass attivo:

- i nuovi account vengono attivati immediatamente;
- l’email resta indicata come non verificata;
- nessuna email viene inviata;
- reinvio verifica e recupero password via email vengono disabilitati;
- un Admin può modificare manualmente la password dal Django Admin.

Il bypass non attiva automaticamente gli account inattivi creati in precedenza. Un
Admin può aprire l’utente nel Django Admin, selezionare `Active` e salvare.

Per ripristinare il flusso normale:

1. configurare tutte le variabili SMTP;
2. impostare `DJANGO_BYPASS_EMAIL_VERIFICATION=false`;
3. riavviare i servizi dipendenti;
4. effettuare un test con un indirizzo controllato.

Le password SMTP e le app password vanno copiate esattamente come generate e conservate
solo nel secret store e in un password manager personale.

## Immagini e annotazioni

Ogni via può avere una sola immagine.

Formati ammessi:

- JPEG;
- PNG;
- WebP non animato.

Limiti:

- massimo 8 MB;
- massimo 12.000 pixel per lato;
- massimo 36 megapixel complessivi;
- corrispondenza obbligatoria tra estensione, content type e contenuto reale.

In sviluppo i file vengono salvati in `media/`. In produzione il backend
`CloudinaryMediaStorage` carica le immagini su Cloudinary e nel database conserva solo
l’identificativo del file.

L’annotazione:

- non modifica l’immagine originale;
- è salvata come JSON versionato;
- utilizza coordinate normalizzate tra 0 e 1;
- resta allineata durante il ridimensionamento responsive;
- supporta partenza sinistra, partenza destra, movimenti numerati e top;
- consente trascinamento, selezione, annullamento e cancellazione;
- accetta al massimo 100 marcatori.

Partenze e top possono comparire una sola volta. I movimenti vengono rinumerati in modo
consecutivo. Sostituire l’immagine azzera l’annotazione perché le coordinate potrebbero
non essere più valide.

Durante il salvataggio dell’annotazione Django valida il JSON senza tentare di scaricare
nuovamente l’immagine da Cloudinary. La validazione completa del file avviene al momento
del caricamento.

## URL principali

| URL | Descrizione |
|---|---|
| `/` | Home |
| `/register/` | Registrazione |
| `/login/` | Login |
| `/logout/` | Logout POST |
| `/account/` | Profilo personale |
| `/users/` | Elenco climber |
| `/users/<username>/` | Profilo pubblico |
| `/walls/` | Elenco pareti |
| `/walls/<id>/` | Dettaglio parete |
| `/routes/` | Catalogo vie e boulder |
| `/routes/<id>/` | Dettaglio via |
| `/routes/<id>/image/` | Caricamento o sostituzione immagine |
| `/routes/<id>/annotation/` | Editor annotazione |
| `/ascents/new/` | Nuova ripetizione |
| `/ascents/<id>/edit/` | Modifica ripetizione |
| `/ascents/<id>/delete/` | Eliminazione ripetizione |
| `/statistics/` | Statistiche collettive |
| `/management/` | Dashboard Admin |
| `/admin/` | Django Admin |
| `/healthz/` | Health check applicazione e database |

## Traduzioni

I testi sorgente dei template sono in inglese e la traduzione italiana si trova in
`locale/it/LC_MESSAGES/django.po`.

Dopo aver modificato testi traducibili:

```bash
uv run python manage.py makemessages -l it
uv run python manage.py compilemessages
```

La compilazione richiede GNU gettext. Il selettore lingua salva la preferenza per gli
utenti autenticati e usa il cookie Django per gli utenti anonimi.

## Test e qualità

Installare le dipendenze di sviluppo:

```bash
uv sync --frozen --group dev
```

Eseguire tutti i controlli:

```bash
uv run pytest --cov --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
uv run mypy apps config
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py check
```

Per applicare automaticamente formattazione e correzioni sicure:

```bash
uv run ruff check . --fix
uv run ruff format .
```

I test coprono:

- modelli e vincoli;
- registrazione, verifica email, login, logout e password;
- rate limiting;
- ruoli e autorizzazioni;
- CRUD di pareti e vie;
- creazione, modifica ed eliminazione delle ripetizioni;
- statistiche e ordinamenti;
- caricamento e cancellazione immagini;
- annotazioni con storage locale e remoto;
- CSRF e accessi non autorizzati;
- audit e dashboard amministrativa;
- health check e storage Cloudinary.

### Pre-commit

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

### GitHub Actions

La workflow `.github/workflows/ci.yml` viene eseguita su push verso `main` e sulle pull
request.

- job `quality`: Ruff e mypy con Python 3.14;
- job `tests`: pytest e controlli Django con Python 3.12 e 3.14 e PostgreSQL 17.

## Sicurezza

- password gestite e hashate dal sistema di autenticazione Django;
- secret esclusivamente in variabili d’ambiente;
- CSRF attivo su tutti i form;
- logout consentito solo tramite POST;
- autorizzazioni verificate nel backend;
- cookie di sessione e CSRF sicuri in produzione;
- redirect HTTPS, HSTS e intestazioni di sicurezza;
- login rate-limited tramite identificatori sottoposti a hash;
- validazione backend di file, annotazioni, date, gradi e tentativi;
- query ottimizzate con `select_related`, annotazioni e paginazione;
- transazioni per operazioni critiche;
- cancellazioni distruttive con conferma;
- log JSON senza corpi delle richieste o credenziali;
- audit persistente e in sola lettura;
- database e media esclusi dal repository.

## Health check

```http
GET /healthz/
```

Risposta corretta:

```json
{"status": "ok"}
```

Se PostgreSQL non è raggiungibile, l’endpoint restituisce HTTP 503:

```json
{"status": "unavailable"}
```

Non vengono restituiti dettagli sensibili sull’errore.

In produzione `/healthz/` è escluso dal redirect HTTPS interno tramite:

```python
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
```

Questo consente a Northflank di interrogare l’endpoint in HTTP sulla rete interna senza
disabilitare HTTPS per le pagine pubbliche.

## Deployment su Northflank

La configurazione seguente è adatta al sandbox Northflank usato per test e piccoli
carichi. Prima dell’utilizzo reale in palestra verificare limiti, disponibilità, backup
e condizioni del piano corrente.

### 1. Repository GitHub

1. Pubblicare il progetto su GitHub.
2. Collegare GitHub a Northflank.
3. Creare un progetto Northflank.
4. Creare un combined service collegato al repository e al branch `main`.
5. Selezionare il `Dockerfile` nella radice come metodo di build.
6. Abilitare CI e CD.

Il Dockerfile installa soltanto le dipendenze di produzione, raccoglie i file statici e
avvia Gunicorn sulla porta indicata da `PORT`, con fallback `8000`.

### 2. PostgreSQL

1. Creare un addon PostgreSQL.
2. Attendere che risulti operativo.
3. Collegare la sua `DATABASE_URL` al servizio web tramite Secret Group o variabile
   runtime.
4. Non copiare la connessione in file versionati.

### 3. Cloudinary

1. Creare un account e un cloud Cloudinary.
2. Copiare `CLOUDINARY_URL` nel Secret Group Northflank.
3. Non inserire API key o API secret nel repository.

Formato previsto:

```text
cloudinary://API_KEY:API_SECRET@CLOUD_NAME
```

### 4. Secret Group

Variabili consigliate per il servizio web:

```text
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_SECRET_KEY=<chiave-casuale>
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=<hostname>.code.run,localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=https://<hostname>.code.run
DJANGO_DEFAULT_LANGUAGE=it
DJANGO_LOG_LEVEL=INFO
DATABASE_URL=<variabile-dell-addon-postgresql>
CLOUDINARY_URL=<secret-cloudinary>
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_HSTS_SECONDS=0
DJANGO_BYPASS_EMAIL_VERIFICATION=true
LOGIN_FAILURE_LIMIT=5
LOGIN_LOCKOUT_MINUTES=15
```

Durante la prima configurazione è prudente mantenere `DJANGO_HSTS_SECONDS=0`. Dopo aver
verificato stabilmente HTTPS, host e dominio, è possibile impostare:

```text
DJANGO_HSTS_SECONDS=31536000
```

Se l’SMTP funziona, impostare il bypass a `false` e aggiungere le variabili `EMAIL_*`.

### 5. Porta e dominio pubblico

Configurare una porta pubblica:

```text
Port: 8000
Protocol: HTTP
```

Northflank termina HTTPS sul proxy pubblico e inoltra HTTP a Gunicorn nella rete
interna.

Dopo aver generato il dominio, aggiornare `DJANGO_ALLOWED_HOSTS` e
`DJANGO_CSRF_TRUSTED_ORIGINS` con il vero hostname.

### 6. Migrazioni

Creare un job, ad esempio `climbingside-migrate`, che utilizzi l’ultima build del
servizio e lo stesso Secret Group.

Comando:

```bash
python manage.py migrate --noinput
```

Eseguire il job prima del primo avvio e dopo ogni release che contiene migrazioni. Se il
job è configurato per avviarsi automaticamente al cambio immagine, controllare comunque
il risultato prima di considerare concluso il deployment.

### 7. Primo amministratore senza shell

Se il piano non offre accesso shell, usare temporaneamente un job.

Aggiungere come secret:

```text
DJANGO_SUPERUSER_PASSWORD=<password-temporanea-sicura>
```

Impostare temporaneamente il comando:

```bash
python manage.py createsuperuser --noinput --username <username> --email <email>
```

Dopo l’esecuzione riuscita:

1. rimuovere `DJANGO_SUPERUSER_PASSWORD` dal Secret Group;
2. ripristinare il comando del job:

   ```bash
   python manage.py migrate --noinput
   ```

3. verificare l’accesso a `/admin/`.

### 8. Readiness probe

Configurazione consigliata:

| Campo | Valore |
|---|---|
| Type | Readiness |
| Protocol | HTTP |
| Port | `8000` |
| Path | `/healthz/` |
| Initial delay | 10 secondi |
| Interval | 10 secondi |
| Timeout | 5 secondi |
| Max failures | 5 |
| Success threshold | 1 |

La probe HTTP è preferibile alla sola TCP perché verifica Gunicorn, Django e la
connessione a PostgreSQL.

### 9. Verifica del deployment

Controllare:

1. build completata;
2. commit distribuito uguale all’ultimo commit GitHub;
3. job migrazioni riuscito;
4. pod `Ready`;
5. `/healthz/` restituisce `{"status":"ok"}`;
6. login e pagine principali funzionano;
7. caricamento immagine raggiunge Cloudinary;
8. registrazione ed email funzionano oppure il bypass è dichiaratamente attivo.

## Aggiornamento dell’applicazione

Prima di modificare una copia locale:

```bash
git pull --rebase origin main
```

Dopo le modifiche:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy apps config
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py check
git status
git add -A
git commit -m "Descrizione sintetica della modifica"
git push origin main
```

Con CI e CD attivi, Northflank costruisce e distribuisce il nuovo commit. Un semplice
restart riavvia l’immagine esistente e non sostituisce un build mancante o fallito.

Non usare `git push --force` per risolvere un rifiuto `fetch first`. Integrare prima il
remoto:

```bash
git pull --rebase origin main
git push origin main
```

In caso di conflitto, eseguire `git status`, risolvere i file indicati e non cancellare
modifiche remote senza averle verificate.

## Backup e ripristino

Il database e le immagini richiedono strategie separate.

### PostgreSQL

Esempio con strumenti PostgreSQL installati:

```bash
pg_dump --format=custom --no-owner --file=climbingside.dump "$DATABASE_URL"
createdb climbingside_restore_test
pg_restore --no-owner --dbname=climbingside_restore_test climbingside.dump
```

Regole consigliate:

- creare backup automatici regolari;
- cifrare i dump;
- conservarli fuori dal servizio applicativo;
- limitare l’accesso;
- provare periodicamente un ripristino in un ambiente separato;
- non commettere mai i dump su GitHub.

### Cloudinary

Il database contiene identificativi e annotazioni, non i byte delle immagini. Verificare
quindi anche la politica di conservazione, backup o versionamento disponibile nel piano
Cloudinary utilizzato.

## Risoluzione dei problemi

### `service "web" is not running`

```bash
docker compose ps
docker compose logs web
docker compose up -d --build
```

### `Invalid HTTP_HOST header: 127.0.0.1:8000`

Assicurarsi che la variabile includa:

```text
DJANGO_ALLOWED_HOSTS=<hostname-pubblico>,localhost,127.0.0.1
```

### Readiness HTTP in timeout

Verificare:

- porta `8000`;
- path `/healthz/`;
- `127.0.0.1` negli host consentiti;
- presenza di `SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]`;
- raggiungibilità di PostgreSQL;
- Secret Group applicato al servizio web.

La probe TCP può essere usata temporaneamente per verificare che Gunicorn sia in
ascolto, ma non sostituisce il controllo applicativo e del database.

### Il nuovo commit è su GitHub ma il sito non cambia

1. confrontare il commit GitHub con `Currently deployed` su Northflank;
2. verificare che CI e CD siano attivi;
3. controllare build e deployment;
4. verificare che il pod sia `Ready`;
5. usare `Ctrl + F5` o una finestra anonima per escludere la cache degli asset.

### `git push` rifiutato con `fetch first`

```bash
git pull --rebase origin main
git push origin main
```

Non usare `--force` senza una ragione verificata.

### Le email non arrivano

- controllare che il bypass sia `false`;
- verificare host, porta, TLS, username, password e mittente SMTP;
- controllare log applicativi e pannello del provider;
- verificare dominio mittente, SPF, DKIM e DMARC quando richiesti;
- non stampare password o API key nei log;
- usare temporaneamente il bypass se il provider non è ancora configurato.

### Errore 500 salvando un’annotazione

La versione corrente evita di rivalidare il file remoto durante il salvataggio del JSON.
Verificare di avere la versione aggiornata di `apps/climbs/forms.py` e consultare i log
Northflank senza condividere secret o credenziali.

## Sviluppi futuri

- configurazione SMTP definitiva e disattivazione del bypass;
- dominio personalizzato indipendente dalla piattaforma;
- backup PostgreSQL automatizzati e test periodici di ripristino;
- monitoraggio uptime, errori e utilizzo risorse;
- procedura controllata di anonimizzazione o eliminazione account;
- esportazione dei propri dati;
- eventuale supporto a valutazioni con mezze stelle, previa decisione sul modello dati;
- ulteriori miglioramenti all’editor delle annotazioni;
- valutazione di una modalità installabile/PWA per l’uso in palestra.

## Note finali

- Il progetto non importa dati dalla vecchia palestra.
- SQLite è destinato allo sviluppo, non alla produzione.
- I file multimediali non devono essere salvati nel filesystem effimero del container.
- Ogni nuova dipendenza deve avere uno scopo chiaro.
- Prima di ogni release eseguire test, lint, type checking e controllo delle migrazioni.
