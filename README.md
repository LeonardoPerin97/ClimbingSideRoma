# ClimbingSide Roma

ClimbingSide Roma è un’applicazione web per gestire le vie di una palestra di
arrampicata e il diario delle ripetizioni dei suoi utenti.

Il sistema permette di catalogare pareti, vie e boulder, registrare le salite,
raccogliere valutazioni e gradi percepiti, mostrare statistiche personali e collettive
e gestire immagini annotate delle vie.

L’applicazione è progettata per una sola palestra ed è realizzata come monolite Django
server-rendered, con un’architettura modulare, PostgreSQL in produzione e JavaScript
leggero per le interazioni che lo richiedono.

## Indice

- [Obiettivi del progetto](#obiettivi-del-progetto)
- [Funzionalità](#funzionalità)
- [Regole di dominio](#regole-di-dominio)
- [Architettura](#architettura)
- [Stack tecnologico](#stack-tecnologico)
- [Flussi principali del codice](#flussi-principali-del-codice)
- [Struttura del repository](#struttura-del-repository)
- [Mappa dei moduli](#mappa-dei-moduli)
- [Modello dei dati](#modello-dei-dati)
- [Ruoli e autorizzazioni](#ruoli-e-autorizzazioni)
- [Interfaccia e internazionalizzazione](#interfaccia-e-internazionalizzazione)
- [URL principali](#url-principali)
- [Installazione locale](#installazione-locale)
- [Configurazione](#configurazione)
- [Email e verifica degli account](#email-e-verifica-degli-account)
- [Immagini e annotazioni](#immagini-e-annotazioni)
- [Test e qualità del codice](#test-e-qualità-del-codice)
- [Sicurezza](#sicurezza)
- [Deployment su Northflank](#deployment-su-northflank)
- [Operazioni e manutenzione](#operazioni-e-manutenzione)
- [Sviluppi futuri](#sviluppi-futuri)

## Obiettivi del progetto

ClimbingSide Roma risponde a quattro esigenze principali:

1. **Catalogo della palestra**: rappresentare pareti, vie e boulder in modo ordinato e
   consultabile da smartphone.
2. **Diario personale**: permettere a ogni utente di registrare e aggiornare le proprie
   ripetizioni.
3. **Informazioni collettive**: aggregare valutazioni, gradi proposti e statistiche
   dell’intera community.
4. **Gestione operativa**: fornire a route setter e amministratori strumenti sicuri per
   mantenere il catalogo e le immagini.

Il progetto non dipende dal codice o dal database della precedente applicazione Flask e
non prevede l’importazione dei dati della vecchia palestra.

## Funzionalità

### Account e profili

- registrazione con username, email e lingua preferita;
- verifica dell’indirizzo email;
- login case-insensitive e logout sicuro;
- recupero e modifica della password;
- protezione dai tentativi ripetuti di login;
- profilo personale modificabile;
- profilo pubblico senza esposizione dell’email;
- selezione persistente della lingua italiana o inglese;
- elenco pubblico dei climber ordinabile per nome, numero di ripetizioni e grado
  massimo.

### Pareti

- elenco pubblico con ricerca, ordinamento e paginazione;
- conteggio delle vie attive e delle ripetizioni;
- dettaglio della parete con totali distinti per vie e boulder;
- filtro per tipo;
- ordinamento crescente e decrescente per nome, grado, ripetizioni e valutazione media;
- visualizzazione del grado ufficiale e del grado medio proposto;
- istogramma continuo delle vie per grado, inclusi i Project;
- evidenziazione delle vie completate dall’utente autenticato;
- creazione, modifica, archiviazione, ripristino e cancellazione controllata.

### Vie e boulder

- catalogo pubblico con ricerca per nome;
- filtri per parete, tipo, grado e stato;
- ordinamento per nome, difficoltà, numero di ripetizioni e valutazione media;
- istogramma continuo per grado suddiviso tra vie e boulder;
- selezione interattiva del grafico: tutte, solo vie o solo boulder;
- dettaglio con nome, grado ufficiale, parete, tipo e route setter;
- immagine e annotazione grafica del percorso;
- numero di ripetizioni e valutazione media;
- grado medio proposto e distribuzione completa dei gradi decimali;
- elenco delle ripetizioni dalla più recente alla meno recente;
- evidenziazione nel catalogo delle vie completate dall’utente;
- archiviazione conservativa delle vie non più presenti in palestra.

### Ripetizioni

Ogni utente può registrare una ripetizione specificando:

- via o boulder;
- data;
- valutazione da 1 a 5;
- grado francese percepito;
- decimale del grado da 0 a 9;
- Onsight, Flash, numero di tentativi oppure N.D.

È consentita una sola ripetizione per coppia utente/via. Il proprietario può modificarla
o eliminarla. Le valutazioni negli elenchi sono rappresentate da cinque stelle con base
grigia e riempimento giallo proporzionale, accompagnate dal valore numerico.

### Statistiche

Le statistiche personali comprendono:

- numero di ripetizioni;
- grado massimo ufficiale;
- distribuzione delle vie completate per grado;
- conteggio distinto di vie e boulder;
- distribuzione per parete;
- elenco filtrabile e ordinabile delle ripetizioni.

Le statistiche collettive comprendono:

- numero di pareti, vie, boulder, Project, utenti e ripetizioni;
- massimo grado ufficiale attivo;
- distribuzione delle vie per grado e tipo;
- distribuzione delle vie per parete;
- ripetizioni registrate negli ultimi dodici mesi.

### Home

La home presenta una sintesi immediata della palestra:

- numero di vie attive, pareti, climber e ripetizioni;
- ripetizioni recenti con climber, via e grado;
- vie più ripetute;
- collegamenti rapidi al catalogo e alla registrazione di una ripetizione;
- immagine hero derivata dall’immagine aggiornata più recentemente di una via attiva.

### Amministrazione

- dashboard operativa riservata agli amministratori;
- Django Admin configurato per i modelli applicativi;
- gestione di utenti e ruoli;
- gestione di pareti, vie, immagini e annotazioni;
- registro di audit in sola lettura;
- conferme esplicite per le operazioni distruttive;
- protezione dei dati storici collegati.

## Regole di dominio

Le regole seguenti definiscono il comportamento centrale dell’applicazione.

### Palestra e pareti

- L’installazione rappresenta una sola palestra.
- Una parete può contenere sia vie sia boulder.
- Le pareti non utilizzate vengono archiviate.
- Il nome di una parete è univoco senza distinzione tra maiuscole e minuscole.

### Vie

- Il termine `ClimbingRoute` identifica una via di arrampicata ed evita ambiguità con
  le route HTTP.
- Il campo `Tipo` distingue `Vie` e `Boulder`.
- Il nome della via è univoco senza distinzione tra maiuscole e minuscole.
- Il grado ufficiale usa la scala francese da `4a` a `9c`.
- Un `Project` è una via non ancora liberata o graduata e non possiede un grado
  ufficiale.
- Una via può non avere route setter oppure averne uno o più.
- Non vengono gestite date di apertura o rimozione.
- Le vie storiche vengono archiviate invece di essere eliminate.

### Ripetizioni

- Ogni utente può registrare una sola ripetizione della stessa via.
- La ripetizione può essere modificata o eliminata solo dal proprietario.
- La data non può essere futura.
- La valutazione è un intero compreso tra 1 e 5.
- Il grado percepito combina grado francese e decimale da 0 a 9.
- Il numero di tentativi è obbligatorio solo quando viene selezionato il relativo tipo.
- Profili e ripetizioni sono pubblici; email e informazioni riservate restano private.

### Conservazione dei dati

- L’archiviazione è preferita alla cancellazione permanente.
- La cancellazione permanente è riservata agli amministratori.
- Pareti e vie devono essere già archiviate prima della cancellazione.
- La conferma richiede l’inserimento esatto del nome.
- Una via con ripetizioni non può essere eliminata perché la relazione è protetta.

## Architettura

ClimbingSide utilizza un **monolite Django modulare**. Questa scelta mantiene nello
stesso progetto autenticazione, modelli relazionali, form, template, pannello
amministrativo e operazioni CRUD, evitando la complessità di un frontend separato.

```mermaid
flowchart TD
    Browser[Browser] --> Views[Viste Django]
    Views --> Forms[Form e validazione]
    Forms --> Models[Modelli di dominio]
    Models --> Database[(PostgreSQL)]
    Views --> Templates[Template e componenti]
    Templates --> Browser
    Views --> Services[Servizi applicativi]
    Services --> Cloudinary[Cloudinary]
    Services --> SMTP[SMTP]
```

### Applicazioni Django

Il codice è suddiviso per responsabilità:

- `apps.accounts`: autenticazione, utenti, profili, lingua, ruoli e rate limiting;
- `apps.climbs`: dominio dell’arrampicata, cataloghi, ripetizioni, immagini e statistiche;
- `apps.core`: home, dashboard, audit, health check, storage e logging.

### Livelli del codice

#### Modelli

I modelli rappresentano lo stato persistente e contengono:

- relazioni tra entità;
- vincoli di database;
- indici;
- validazione indipendente dall’interfaccia;
- proprietà di visualizzazione semplici.

#### Form

I form Django gestiscono:

- conversione e validazione dell’input;
- messaggi di errore;
- esclusione delle vie già ripetute dall’utente;
- coerenza tra Project e grado ufficiale;
- coerenza tra tipo di tentativo e numero di tentativi;
- validazione sicura delle immagini;
- normalizzazione delle annotazioni JSON.

#### Viste

Le viste coordinano il flusso HTTP:

- verificano autenticazione e permessi;
- costruiscono query ottimizzate;
- istanziano e validano i form;
- eseguono transazioni;
- registrano eventi di audit;
- producono redirect e messaggi di conferma;
- forniscono il contesto ai template.

#### Servizi

La logica con effetti esterni è isolata in moduli dedicati:

- invio delle email di verifica;
- caricamento e cancellazione delle immagini;
- adapter Cloudinary;
- registrazione dell’audit;
- calcolo delle statistiche;
- generazione e verifica dei token.

#### Template e componenti

I template estendono `templates/base.html` e riutilizzano componenti condivisi per:

- form;
- paginazione;
- schede delle vie;
- schede delle ripetizioni;
- istogrammi;
- valutazioni a stelle;
- statistiche dei profili.

La logica complessa resta in Python e non viene delegata ai template.

#### JavaScript

JavaScript è utilizzato soltanto dove migliora l’esperienza utente:

- menu mobile;
- selettore della lingua;
- campi dinamici Project e tentativi;
- filtro interattivo degli istogrammi;
- editor vettoriale delle annotazioni.

L’applicazione continua a funzionare come sito server-rendered e non richiede un sistema
di build frontend.

## Stack tecnologico

| Componente | Tecnologia | Responsabilità |
|---|---|---|
| Linguaggio | Python 3.12–3.14 | Logica applicativa e strumenti di sviluppo |
| Framework | Django 5.2 LTS | HTTP, autenticazione, ORM, form, template e admin |
| Database | PostgreSQL 17 | Persistenza relazionale in produzione |
| Database locale | SQLite | Avvio rapido senza servizi esterni |
| Server WSGI | Gunicorn | Esecuzione dell’applicazione in produzione |
| File statici | WhiteNoise | Pubblicazione di CSS, JavaScript e asset versionati |
| Immagini | Pillow e Cloudinary | Validazione, memorizzazione e distribuzione degli upload |
| Configurazione | django-environ | Lettura tipizzata delle variabili d’ambiente |
| Dipendenze | uv | Risoluzione, lock e installazione riproducibile |
| Test | pytest, pytest-django, coverage | Test automatici e misurazione della copertura |
| Qualità | Ruff, mypy, pre-commit | Lint, formattazione e controllo dei tipi |
| CI | GitHub Actions | Controlli automatici su push e pull request |
| Container | Docker | Build riproducibile per sviluppo e produzione |

Il frontend non usa Node.js né un framework JavaScript. HTML viene prodotto dai
template Django, lo stile è CSS nativo e gli script sono JavaScript senza dipendenze.

## Flussi principali del codice

### Registrazione

1. `RegistrationForm` valida username, email, lingua e password.
2. L’utente viene creato tramite il modello personalizzato `accounts.User`.
3. La password viene hashata dal sistema Django.
4. Il ruolo `User` viene assegnato tramite un gruppo Django.
5. Se la verifica email è attiva, l’account resta inattivo e viene inviato un token.
6. Il link valido imposta `email_verified_at` e attiva l’utente.

### Login

1. Il backend autentica lo username senza distinzione tra maiuscole e minuscole.
2. Il rate limiter calcola un identificatore hash basato su username e origine della
   richiesta.
3. Dopo la soglia configurata, l’accesso viene bloccato temporaneamente.
4. Un login riuscito elimina il relativo contatore di errori.

### Registrazione di una ripetizione

1. La vista richiede autenticazione e permesso `add_ascent`.
2. `AscentForm` mostra solo le vie non ancora registrate dall’utente.
3. Il form valida data, rating, grado percepito e tentativi.
4. Il modello applica nuovamente i vincoli essenziali.
5. Il database impedisce duplicati per utente e via.
6. La ripetizione viene salvata e diventa visibile nei profili e nelle statistiche.

### Consultazione del catalogo

1. La vista interpreta ricerca, filtri, ordinamento e pagina.
2. Le query usano `select_related`, aggregazioni e annotazioni Django.
3. Per gli utenti autenticati una sottoquery `Exists` identifica le vie completate.
4. Il risultato viene paginato a 20 elementi.
5. Il template renderizza schede, filtri e statistiche senza query aggiuntive.

### Caricamento di un’immagine

1. La vista verifica il permesso sul modello `RouteImage`.
2. Il form controlla dimensione, formato dichiarato e contenuto reale.
3. Il servizio salva il record e il file in una transazione controllata.
4. In produzione il file viene inviato a Cloudinary.
5. Un eventuale file sostituito viene eliminato solo dopo il commit del database.
6. L’operazione viene registrata nell’audit log.

### Salvataggio dell’annotazione

1. L’editor converte i marcatori in coordinate normalizzate.
2. Il JSON viene inserito in un campo nascosto del form.
3. Il backend verifica versione, struttura, tipi, coordinate e numerazione.
4. Viene aggiornato solo il campo `annotations` del record `RouteImage`.
5. L’immagine originale rimane invariata.

## Struttura del repository

```text
climbingside/
├── apps/
│   ├── accounts/
│   │   ├── admin.py          # utenti e ruoli nel Django Admin
│   │   ├── backends.py       # autenticazione case-insensitive
│   │   ├── forms.py          # registrazione e profilo
│   │   ├── middleware.py     # applicazione della lingua preferita
│   │   ├── models.py         # User e LoginAttempt
│   │   ├── rate_limit.py     # limitazione dei tentativi di login
│   │   ├── roles.py          # ruoli, gruppi e permessi
│   │   ├── services.py       # invio email
│   │   ├── signals.py        # sincronizzazione permessi post-migrate
│   │   ├── tokens.py         # token di verifica email
│   │   ├── urls.py
│   │   └── views.py
│   ├── climbs/
│   │   ├── admin.py
│   │   ├── annotations.py    # schema delle annotazioni
│   │   ├── forms.py
│   │   ├── grades.py         # scala francese e ordinamento
│   │   ├── images.py         # validazione degli upload
│   │   ├── media_services.py # ciclo di vita dei file
│   │   ├── models.py         # Wall, ClimbingRoute, Ascent, RouteImage
│   │   ├── statistics.py     # aggregazioni statistiche
│   │   ├── urls.py
│   │   └── views.py
│   └── core/
│       ├── admin.py          # audit log in sola lettura
│       ├── audit.py
│       ├── forms.py          # stile condiviso dei form
│       ├── health.py         # health check database
│       ├── models.py         # AuditLogEntry
│       ├── storage.py        # backend Cloudinary
│       ├── urls.py
│       └── views.py
├── config/
│   ├── settings/
│   │   ├── base.py           # configurazione condivisa
│   │   ├── development.py    # sviluppo
│   │   ├── test.py           # test
│   │   └── production.py     # produzione
│   ├── logging.py            # formatter JSON
│   ├── urls.py               # URL root
│   ├── asgi.py
│   └── wsgi.py
├── locale/                   # traduzioni gettext
├── static/
│   ├── css/app.css           # stile responsive
│   ├── images/               # logo e asset statici
│   └── js/
│       ├── app.js            # interazioni generali
│       └── route-annotation.js
├── templates/
│   ├── accounts/
│   ├── climbs/
│   ├── components/
│   ├── core/
│   └── base.html
├── tests/
│   ├── accounts/
│   ├── climbs/
│   └── core/
├── .github/workflows/ci.yml
├── .env.example
├── .pre-commit-config.yaml
├── compose.yml
├── Dockerfile
├── manage.py
├── pyproject.toml
└── uv.lock
```

Ogni applicazione Django contiene inoltre una cartella `migrations/` con l’evoluzione
versionata dello schema del database.

## Mappa dei moduli

Questa sezione indica dove cercare una responsabilità e come i moduli collaborano.

### Entrata e configurazione

| File | Responsabilità | Collegamenti principali |
|---|---|---|
| `manage.py` | Punto di ingresso dei comandi Django | Carica il modulo indicato da `DJANGO_SETTINGS_MODULE` |
| `config/urls.py` | Router HTTP principale | Include gli URL di `accounts`, `climbs` e `core` |
| `config/settings/base.py` | Configurazione condivisa | Registra app, middleware, database, template, storage e autenticazione |
| `config/settings/development.py` | Impostazioni locali | Estende `base.py` con comportamento adatto allo sviluppo |
| `config/settings/test.py` | Ambiente isolato dei test | Usato automaticamente da pytest-django |
| `config/settings/production.py` | Sicurezza e servizi di produzione | Richiede PostgreSQL, Cloudinary e configurazione SMTP o bypass |
| `config/wsgi.py` | Entrata sincrona dell’applicazione | Caricata da Gunicorn |
| `config/asgi.py` | Entrata ASGI | Disponibile per server o funzionalità asincrone future |
| `config/logging.py` | Formatter JSON | Usato dalla configurazione di logging in produzione |

### Applicazione `accounts`

| File | Responsabilità | Collegamenti principali |
|---|---|---|
| `models.py` | Modello utente personalizzato e tentativi di login | Referenziato da `AUTH_USER_MODEL` e dalle ripetizioni |
| `forms.py` | Registrazione, aggiornamento profilo e reinvio verifica | Valida unicità case-insensitive e usa `StyledFormMixin` |
| `views.py` | Flussi di account e profili | Usa form, token, rate limiter, servizi email e statistiche personali |
| `urls.py` | URL di autenticazione e profilo | Incluso alla radice da `config/urls.py` |
| `backends.py` | Login case-insensitive | Registrato in `AUTHENTICATION_BACKENDS` |
| `rate_limit.py` | Blocco temporaneo dei login ripetuti | Legge e aggiorna `LoginAttempt` |
| `roles.py` | Definizione di User, RouteSetter e Admin | Crea gruppi e assegna permessi Django |
| `signals.py` | Sincronizzazione automatica dei ruoli | Richiama `sync_role_permissions` dopo le migrazioni |
| `tokens.py` | Token firmati per la verifica email | Utilizzato dalle viste e dai link inviati per email |
| `services.py` | Composizione e invio della verifica email | Renderizza i template email e usa il backend configurato |
| `middleware.py` | Lingua preferita dell’utente | Attiva la lingua salvata dopo l’autenticazione |
| `admin.py` | Gestione sicura degli utenti | Integra ruoli e audit nel Django Admin |

### Applicazione `climbs`

| File | Responsabilità | Collegamenti principali |
|---|---|---|
| `models.py` | Pareti, vie, ripetizioni e immagini | Definisce relazioni, vincoli, indici e validazione di dominio |
| `forms.py` | Form CRUD, ripetizioni, upload e annotazioni | Usa gradi, validatori immagine e parser delle annotazioni |
| `views.py` | Cataloghi, dettagli e mutazioni del dominio | Coordina permessi, query, form, transazioni, audit e template |
| `urls.py` | URL di pareti, vie, immagini e ripetizioni | Collega ogni endpoint alla relativa vista |
| `grades.py` | Scala francese e grado decimale | Fornisce ordinamento, codifica e presentazione dei gradi |
| `statistics.py` | Statistiche personali e collettive | Produce bucket continui usati dagli istogrammi e dalle dashboard |
| `images.py` | Sicurezza degli upload | Verifica nome, formato, dimensioni, pixel e animazioni |
| `media_services.py` | Ciclo di vita delle immagini | Coordina database e storage durante sostituzione o cancellazione |
| `annotations.py` | Contratto JSON delle annotazioni | Normalizza e valida marcatori e coordinate |
| `templatetags/climbs_tags.py` | Filtri di presentazione dei gradi | Usato esclusivamente nei template |
| `admin.py` | Gestione del dominio nel Django Admin | Ottimizza query, applica vincoli di cancellazione e registra audit |
| `management/commands/seed_demo.py` | Dati locali dimostrativi | Crea dataset non sensibile in modo idempotente |

### Applicazione `core`

| File | Responsabilità | Collegamenti principali |
|---|---|---|
| `views.py` | Home, statistiche, dashboard e lingua | Interroga `climbs.statistics` e renderizza le pagine generali |
| `health.py` | Stato dell’applicazione | Verifica il database e risponde su `/healthz/` |
| `models.py` | Registro di audit | Riceve eventi dalle operazioni amministrative |
| `audit.py` | API per scrivere eventi di audit | Chiamata dalle viste e dalle classi Admin |
| `storage.py` | Adapter Django per Cloudinary | Implementa salvataggio, URL, esistenza e cancellazione dei file |
| `forms.py` | Stile condiviso dei controlli | Ereditato dai form delle altre applicazioni |
| `urls.py` | URL delle pagine generali | Incluso da `config/urls.py` |
| `admin.py` | Consultazione dell’audit | Impedisce modifica e cancellazione degli eventi |

### Presentazione

| Percorso | Responsabilità |
|---|---|
| `templates/base.html` | Struttura HTML comune, navigazione, messaggi e caricamento degli asset |
| `templates/accounts/` | Pagine e messaggi email dei flussi account |
| `templates/climbs/` | Cataloghi, dettagli, form e conferme del dominio |
| `templates/core/` | Home e dashboard |
| `templates/components/` | Form, paginazione, schede, stelle e istogrammi riutilizzabili |
| `static/css/app.css` | Design system, layout responsive e stati dei componenti |
| `static/js/app.js` | Interazioni generali e filtro degli istogrammi |
| `static/js/route-annotation.js` | Editor delle annotazioni sopra l’immagine |
| `locale/it/LC_MESSAGES/` | Catalogo delle traduzioni italiane |

### Test e infrastruttura

| Percorso | Responsabilità |
|---|---|
| `tests/accounts/` | Autenticazione, account, profili e ruoli |
| `tests/climbs/` | Modelli, CRUD, permessi, ripetizioni, immagini e statistiche |
| `tests/core/` | Home, dashboard, storage, audit e health check |
| `pyproject.toml` | Metadati, dipendenze e configurazione degli strumenti |
| `uv.lock` | Versioni risolte per installazioni riproducibili |
| `compose.yml` | Ambiente locale con applicazione e PostgreSQL |
| `Dockerfile` | Immagine di produzione e comando Gunicorn |
| `.github/workflows/ci.yml` | Pipeline di qualità e test |
| `.env.example` | Elenco documentato delle variabili senza valori sensibili |

## Modello dei dati

```mermaid
erDiagram
    USER ||--o{ ASCENT : registra
    WALL ||--o{ CLIMBING_ROUTE : contiene
    USER }o--o{ CLIMBING_ROUTE : imposta
    CLIMBING_ROUTE ||--o{ ASCENT : riceve
    CLIMBING_ROUTE ||--o| ROUTE_IMAGE : possiede
    USER ||--o{ ROUTE_IMAGE : carica
    USER ||--o{ AUDIT_LOG_ENTRY : esegue
```

### `User`

Estende `AbstractUser` e aggiunge:

- email obbligatoria e univoca;
- lingua preferita;
- data di verifica email.

Username ed email sono univoci anche senza distinzione tra maiuscole e minuscole.

### `LoginAttempt`

Memorizza lo stato del rate limiting:

- identificatore hash;
- numero di errori;
- primo errore;
- scadenza del blocco;
- ultimo aggiornamento.

Non salva password né username in chiaro.

### `Wall`

Rappresenta una parete:

- nome;
- stato archiviato.

### `ClimbingRoute`

Rappresenta una via o un boulder:

- nome;
- parete;
- tipo;
- grado ufficiale;
- flag Project;
- route setter opzionali;
- stato archiviato.

### `Ascent`

Rappresenta una ripetizione:

- utente;
- via;
- data;
- rating;
- grado proposto codificato;
- tipo e numero di tentativi;
- data di creazione;
- data di ultima modifica.

Il grado proposto viene memorizzato come intero che combina la posizione del grado
francese e il decimale. La presentazione leggibile viene gestita da `grades.py`.

### `RouteImage`

Rappresenta l’unica immagine associabile a una via:

- relazione one-to-one con `ClimbingRoute`;
- riferimento al file;
- annotazione JSON;
- utente che ha caricato il file;
- timestamp.

### `AuditLogEntry`

Registra operazioni amministrative:

- attore;
- azione;
- tipo e identificativo dell’entità;
- metadati tecnici non sensibili;
- timestamp.

Il modello è consultabile nel Django Admin ma non può essere modificato o cancellato
tramite l’interfaccia amministrativa.

### Vincoli e indici

I vincoli principali sono applicati nel database:

- unicità di username, email, pareti e vie;
- una ripetizione per utente e via;
- rating tra 1 e 5;
- grado percepito entro la scala supportata;
- coerenza tra Project e grado ufficiale;
- coerenza tra tipo e numero di tentativi.

Gli indici coprono stato e tipo delle vie, parete, grado ufficiale, utente/data,
via/data e campi principali dell’audit.

## Ruoli e autorizzazioni

I ruoli sono implementati attraverso gruppi e permessi Django. Non vengono utilizzati
ID utente fissi.

| Operazione | User | RouteSetter | Admin |
|---|:---:|:---:|:---:|
| Consultare catalogo e statistiche | ✓ | ✓ | ✓ |
| Gestire le proprie ripetizioni | ✓ | ✓ | ✓ |
| Creare e modificare vie | — | ✓ | ✓ |
| Archiviare e ripristinare vie | — | ✓ | ✓ |
| Caricare, sostituire e annotare immagini | — | ✓ | ✓ |
| Eliminare immagini | — | — | ✓ |
| Gestire pareti | — | — | ✓ |
| Gestire utenti e ruoli | — | — | ✓ |
| Eseguire cancellazioni permanenti | — | — | ✓ |
| Accedere al Django Admin | — | — | ✓ |

I gruppi `User`, `RouteSetter` e `Admin` e i relativi permessi vengono sincronizzati dal
segnale `post_migrate`.

Le viste controllano i permessi prima di eseguire qualsiasi operazione. I controlli
visivi nei template servono soltanto a migliorare l’interfaccia e non sostituiscono
l’autorizzazione backend.

## Interfaccia e internazionalizzazione

L’interfaccia è:

- mobile-first;
- responsive;
- server-rendered;
- utilizzabile senza un frontend separato;
- basata su un unico foglio di stile;
- costruita con template e componenti riutilizzabili;
- dotata di stati vuoti, errori, conferme e messaggi di successo;
- navigabile tramite tastiera;
- compatibile con etichette e ruoli ARIA nei componenti interattivi.

I titoli utilizzano Barlow Condensed e il testo Barlow, caricati da Google Fonts con
fallback di sistema.

La lingua predefinita è italiana. I testi sorgente sono traducibili tramite Django
gettext e l’interfaccia supporta italiano e inglese.

File principali:

```text
locale/it/LC_MESSAGES/django.po
locale/it/LC_MESSAGES/django.mo
```

Dopo aver modificato testi traducibili:

```bash
uv run python manage.py makemessages -l it
uv run python manage.py compilemessages
```

La compilazione richiede GNU gettext.

## URL principali

| URL | Accesso | Descrizione |
|---|---|---|
| `/` | pubblico | Home |
| `/register/` | pubblico | Registrazione |
| `/login/` | pubblico | Login |
| `/logout/` | autenticato, POST | Logout |
| `/password-reset/` | pubblico | Recupero password |
| `/account/` | autenticato | Profilo personale |
| `/account/edit/` | autenticato | Modifica profilo |
| `/users/` | pubblico | Elenco climber |
| `/users/<username>/` | pubblico | Profilo pubblico |
| `/walls/` | pubblico | Elenco pareti |
| `/walls/<id>/` | pubblico | Dettaglio parete |
| `/routes/` | pubblico | Catalogo vie e boulder |
| `/routes/<id>/` | pubblico | Dettaglio via |
| `/routes/<id>/image/` | RouteSetter/Admin | Immagine della via |
| `/routes/<id>/annotation/` | RouteSetter/Admin | Editor annotazione |
| `/ascents/new/` | autenticato | Nuova ripetizione |
| `/ascents/<id>/edit/` | proprietario | Modifica ripetizione |
| `/ascents/<id>/delete/` | proprietario | Elimina ripetizione |
| `/statistics/` | pubblico | Statistiche collettive |
| `/management/` | Admin | Dashboard operativa |
| `/admin/` | Admin | Django Admin |
| `/healthz/` | infrastruttura/pubblico | Health check |

## Installazione locale

### Requisiti

- Python 3.12, 3.13 o 3.14;
- [`uv`](https://docs.astral.sh/uv/);
- Git;
- Docker, facoltativo.

### Clone e dipendenze

```bash
git clone https://github.com/LeonardoPerin97/ClimbingSideRoma.git
cd ClimbingSideRoma
cp .env.example .env
uv sync --frozen --group dev
```

### Avvio con SQLite

Lasciare `DATABASE_URL` assente o commentata nel file `.env`.

```bash
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Aprire `http://127.0.0.1:8000/`.

In sviluppo:

- il database predefinito è SQLite;
- le immagini vengono salvate in `media/`;
- le email vengono stampate nel terminale;
- `DEBUG` è attivo.

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

PostgreSQL utilizza il volume nominato `postgres_data`.

### Dati dimostrativi

```bash
uv run python manage.py seed_demo --dry-run
uv run python manage.py seed_demo
```

Il dry-run verifica l’operazione e annulla la transazione. Il comando effettivo è
idempotente e non duplica i dati se eseguito più volte.

Gli utenti demo usano indirizzi `example.invalid`, non sono amministratori e possiedono
password inutilizzabili.

## Configurazione

La configurazione è suddivisa in:

- `config.settings.base`: impostazioni condivise;
- `config.settings.development`: sviluppo locale;
- `config.settings.test`: test automatici;
- `config.settings.production`: produzione.

Le variabili vengono lette con `django-environ`. In locale possono essere salvate in
`.env`; in produzione devono essere configurate nel secret store della piattaforma.

### Variabili principali

| Variabile | Descrizione |
|---|---|
| `DJANGO_SETTINGS_MODULE` | Modulo di configurazione Django |
| `DJANGO_SECRET_KEY` | Chiave crittografica dell’applicazione |
| `DJANGO_DEBUG` | Debug; deve essere `false` in produzione |
| `DJANGO_ALLOWED_HOSTS` | Host consentiti separati da virgola |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Origini HTTPS autorizzate per CSRF |
| `DATABASE_URL` | Connessione al database |
| `DATABASE_CONN_MAX_AGE` | Durata delle connessioni persistenti |
| `DJANGO_DEFAULT_LANGUAGE` | Lingua predefinita, `it` o `en` |
| `DJANGO_LOG_LEVEL` | Livello dei log |
| `DJANGO_BYPASS_EMAIL_VERIFICATION` | Bypass temporaneo delle email |
| `LOGIN_FAILURE_LIMIT` | Soglia degli errori di login |
| `LOGIN_LOCKOUT_MINUTES` | Durata del blocco login |
| `CLOUDINARY_URL` | Configurazione Cloudinary |
| `DJANGO_SECURE_SSL_REDIRECT` | Redirect obbligatorio a HTTPS |
| `DJANGO_HSTS_SECONDS` | Durata della policy HSTS |
| `EMAIL_HOST` | Host SMTP |
| `EMAIL_PORT` | Porta SMTP |
| `EMAIL_HOST_USER` | Utente SMTP |
| `EMAIL_HOST_PASSWORD` | Password o API key SMTP |
| `EMAIL_USE_TLS` | Abilitazione TLS SMTP |
| `DEFAULT_FROM_EMAIL` | Mittente delle email applicative |

Un esempio completo senza dati sensibili è disponibile in `.env.example`.

Per generare una chiave segreta:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### File esclusi dal repository

`.gitignore` esclude:

- `.env` e sue varianti;
- ambienti virtuali;
- database SQLite;
- coverage e cache degli strumenti;
- file statici raccolti;
- cartella media;
- configurazioni locali degli editor.

Non devono essere versionati secret, database, dump o file caricati dagli utenti.

## Email e verifica degli account

### Flusso normale

La produzione usa il backend SMTP Django. Sono necessarie le variabili `EMAIL_*` e un
mittente autorizzato dal provider.

Alla registrazione:

1. l’account viene creato inattivo;
2. viene inviato un link firmato;
3. il link verifica l’email e attiva l’account;
4. l’utente può effettuare il login.

Lo stesso servizio SMTP gestisce il recupero password.

### Bypass temporaneo

Per ambienti in cui l’SMTP non è disponibile:

```text
DJANGO_BYPASS_EMAIL_VERIFICATION=true
```

Con il bypass:

- i nuovi account vengono attivati immediatamente;
- l’email rimane non verificata;
- verifica, reinvio e recupero password via email sono disabilitati;
- un amministratore può gestire manualmente l’account dal Django Admin.

Il bypass deve essere disattivato quando il servizio SMTP è operativo:

```text
DJANGO_BYPASS_EMAIL_VERIFICATION=false
```

Gli account inattivi creati prima del bypass non vengono attivati automaticamente.

## Immagini e annotazioni

### Validazione delle immagini

Sono accettati:

- JPEG;
- PNG;
- WebP non animato.

Limiti:

- 8 MB;
- 12.000 pixel per lato;
- 36 megapixel complessivi;
- una sola immagine per via.

Il backend verifica:

- estensione;
- content type dichiarato;
- formato rilevato da Pillow;
- dimensioni;
- numero di frame;
- coerenza tra formato ed estensione.

Il nome salvato include un UUID e non riutilizza il nome originale dell’utente.

### Storage

- sviluppo: `FileSystemStorage` nella cartella `media/`;
- produzione: `CloudinaryMediaStorage`.

Il database conserva il riferimento all’immagine, mentre i byte sono gestiti dal
servizio esterno.

### Annotazioni

L’immagine originale non viene alterata. L’annotazione è un documento JSON con:

- versione dello schema;
- elenco dei marcatori;
- tipo;
- coordinate normalizzate;
- numero progressivo per i movimenti.

Tipi supportati:

- partenza sinistra;
- partenza destra;
- movimento;
- top.

Il server accetta al massimo 100 marcatori, coordinate comprese tra 0 e 1 e movimenti
numerati consecutivamente. Partenze e top sono unici.

## Test e qualità del codice

### Suite automatica

```bash
uv run pytest
```

Con coverage:

```bash
uv run pytest --cov --cov-report=term-missing
```

La suite copre:

- modelli e vincoli;
- autenticazione e profili;
- verifica email e password reset;
- rate limiting;
- ruoli e permessi;
- CRUD di pareti e vie;
- ripetizioni;
- statistiche e ordinamenti;
- immagini e Cloudinary;
- annotazioni;
- CSRF e accessi non autorizzati;
- audit e dashboard;
- health check.

### Lint, formattazione e type checking

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy apps config
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py check
```

Per applicare le correzioni automatiche:

```bash
uv run ruff check . --fix
uv run ruff format .
```

### Pre-commit

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

### Continuous Integration

`.github/workflows/ci.yml` definisce due job:

- `quality`: Ruff e mypy con Python 3.14;
- `tests`: pytest, controllo migrazioni e Django check con Python 3.12 e 3.14 su
  PostgreSQL 17.

La CI viene eseguita sui push a `main` e sulle pull request.

## Sicurezza

### Autenticazione

- password hashate dal framework;
- validatori password Django;
- token firmati e a scadenza;
- sessioni Django con cookie `HttpOnly` e `SameSite=Lax`;
- cookie `Secure` in produzione;
- rate limiting del login;
- logout esclusivamente tramite POST.

### Autorizzazione

- gruppi e permessi Django;
- controlli backend su ogni mutazione;
- verifica della proprietà delle ripetizioni;
- Django Admin disponibile solo agli amministratori;
- audit delle operazioni privilegiate.

### HTTP

- protezione CSRF;
- redirect HTTPS;
- HSTS configurabile;
- protezione clickjacking;
- `Content-Type` sniffing disabilitato;
- referrer policy restrittiva;
- supporto corretto del proxy HTTPS.

### Dati e file

- secret esclusivamente in variabili d’ambiente;
- database e media esclusi da Git;
- validazione approfondita degli upload;
- transazioni per le operazioni critiche;
- vincoli di database;
- cancellazioni protette;
- log senza password, token o corpi delle richieste.

## Deployment su Northflank

Il deployment utilizza:

- repository GitHub;
- combined service Northflank;
- build tramite Dockerfile;
- PostgreSQL come addon;
- Secret Group per la configurazione;
- Cloudinary per le immagini;
- job dedicato alle migrazioni;
- health check HTTP.

### 1. Servizio web

Creare un combined service collegato al repository e al branch `main`.

Configurazione:

```text
Build type: Dockerfile
Port: 8000
Protocol: HTTP
CI: enabled
CD: enabled
```

Il container esegue:

```bash
gunicorn config.wsgi:application \
  --bind 0.0.0.0:${PORT:-8000} \
  --workers 2 \
  --threads 2 \
  --timeout 60
```

### 2. PostgreSQL

Creare un addon PostgreSQL e rendere disponibile la sua `DATABASE_URL` al servizio web
e al job delle migrazioni.

La configurazione di produzione rifiuta database diversi da PostgreSQL.

### 3. Secret Group

Configurazione minima:

```text
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_SECRET_KEY=<secret-lungo-e-casuale>
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=<hostname>.code.run,localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=https://<hostname>.code.run
DJANGO_DEFAULT_LANGUAGE=it
DJANGO_LOG_LEVEL=INFO
DATABASE_URL=<connessione-postgresql>
CLOUDINARY_URL=<configurazione-cloudinary>
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_HSTS_SECONDS=0
DJANGO_BYPASS_EMAIL_VERIFICATION=true
LOGIN_FAILURE_LIMIT=5
LOGIN_LOCKOUT_MINUTES=15
```

In `DJANGO_ALLOWED_HOSTS` gli host non includono lo schema. Le origini CSRF includono
invece `https://`.

Durante la prima configurazione può essere prudente utilizzare:

```text
DJANGO_HSTS_SECONDS=0
```

Dopo aver verificato dominio e HTTPS:

```text
DJANGO_HSTS_SECONDS=31536000
```

Quando l’SMTP è configurato, impostare il bypass email a `false` e aggiungere le
variabili `EMAIL_*`.

### 4. Cloudinary

Configurare:

```text
CLOUDINARY_URL=cloudinary://API_KEY:API_SECRET@CLOUD_NAME
```

Il valore deve essere memorizzato come secret e non deve apparire nei log o nel
repository.

### 5. Migrazioni

Creare un job `climbingside-migrate` basato sulla stessa immagine e sullo stesso Secret
Group del servizio web.

Comando:

```bash
python manage.py migrate --noinput
```

Il job deve essere eseguito prima del primo avvio e per ogni release che contiene nuove
migrazioni.

### 6. Primo amministratore

Se non è disponibile una shell, utilizzare temporaneamente un job con:

```text
DJANGO_SUPERUSER_PASSWORD=<password-temporanea>
```

Comando:

```bash
python manage.py createsuperuser \
  --noinput \
  --username <username> \
  --email <email>
```

Dopo la creazione:

1. rimuovere `DJANGO_SUPERUSER_PASSWORD`;
2. ripristinare il comando `python manage.py migrate --noinput`;
3. verificare l’accesso a `/admin/`.

### 7. Health check

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

L’endpoint verifica anche il collegamento al database:

```json
{"status": "ok"}
```

In caso di database non disponibile restituisce HTTP 503 senza dettagli sensibili.

`production.py` esclude `/healthz/` dal redirect HTTPS interno, consentendo alla probe
di utilizzare HTTP sulla rete del container senza indebolire le pagine pubbliche.

### 8. Verifica della release

Una release è pronta quando:

- GitHub Actions è verde;
- la build Northflank è riuscita;
- il commit distribuito corrisponde a `main`;
- le migrazioni sono state applicate;
- il pod risulta `Ready`;
- `/healthz/` restituisce HTTP 200;
- statici e pagine principali vengono caricati;
- PostgreSQL e Cloudinary sono raggiungibili;
- il flusso email funziona oppure il bypass è esplicitamente attivo.

## Operazioni e manutenzione

### Aggiornare il codice

```bash
git pull --rebase origin main
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy apps config
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py check
git add -A
git commit -m "Descrizione della modifica"
git push origin main
```

Con CI e CD attivi, Northflank costruisce e distribuisce il nuovo commit.

### Creare una migrazione

Dopo una modifica intenzionale ai modelli:

```bash
uv run python manage.py makemigrations
uv run python manage.py migrate
uv run pytest
```

Le migrazioni devono essere versionate insieme al codice.

### File statici

Il Dockerfile esegue `collectstatic` durante la build. WhiteNoise utilizza nomi con hash
e compressione per servire CSS, JavaScript e immagini statiche.

### Logging e audit

In produzione i log sono JSON e contengono:

- timestamp;
- livello;
- logger;
- messaggio;
- stack trace per le eccezioni.

Non vengono serializzati corpi delle richieste o credenziali.

L’audit applicativo registra creazioni, modifiche, archiviazioni, ripristini,
cancellazioni, cambi ruolo e operazioni sulle immagini.

### Backup PostgreSQL

Esempio con gli strumenti PostgreSQL:

```bash
pg_dump \
  --format=custom \
  --no-owner \
  --file=climbingside.dump \
  "$DATABASE_URL"
```

Ripristino in un database di test:

```bash
createdb climbingside_restore_test
pg_restore \
  --no-owner \
  --dbname=climbingside_restore_test \
  climbingside.dump
```

I backup devono essere cifrati, conservati fuori dal servizio applicativo e verificati
periodicamente con un ripristino di prova.

Il database contiene riferimenti alle immagini e annotazioni, ma non i file Cloudinary.
La strategia di conservazione deve quindi includere anche il servizio media.

## Sviluppi futuri

- configurazione SMTP definitiva e disattivazione del bypass;
- dominio personalizzato;
- backup PostgreSQL automatizzati;
- monitoraggio di uptime, errori e risorse;
- esportazione dei dati personali;
- procedura controllata di anonimizzazione o eliminazione degli account;
- valutazioni con mezze stelle, se adottate anche nel modello dati;
- ulteriori strumenti per l’editor delle annotazioni;
- eventuale modalità PWA per l’utilizzo in palestra.

## Principi di contribuzione

- mantenere separati dominio, presentazione ed effetti esterni;
- usare type hints nel codice Python;
- aggiungere test per ogni comportamento modificato;
- non inserire logica complessa nei template;
- evitare query N+1;
- usare transazioni per operazioni che coinvolgono più record o servizi;
- non aggiungere dipendenze prive di uno scopo concreto;
- non inserire secret, database o file caricati nel repository;
- mantenere coerenti italiano e inglese;
- eseguire l’intera suite di qualità prima di ogni push.
