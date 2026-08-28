# ClimbingSide

Nuova applicazione Django per catalogare pareti, vie e boulder di una palestra e per
registrare le ripetizioni degli utenti.

Questo repository è una riscrittura indipendente. Il codice e il database della vecchia
applicazione Flask non vengono importati o modificati.

## Stato

Incrementi 1, 2, 3, 4, 5, 6, 7, 8 e 9 completati:

- fondazione Django 5.2 LTS;
- configurazioni separate per sviluppo, test e produzione;
- modello utente personalizzato con email obbligatoria e lingua preferita;
- registrazione con verifica email a scadenza;
- login e logout sicuri;
- recupero e modifica della password;
- profilo privato modificabile e profilo pubblico senza esposizione dell'email;
- ruoli `User`, `RouteSetter` e `Admin` basati su gruppi e permessi Django;
- limitazione dei tentativi di login con identificatori sottoposti a hash;
- lingua persistente per gli utenti autenticati;
- interfaccia mobile-first originale, ispirata alla chiarezza dei cataloghi di arrampicata;
- home con riepilogo della palestra, ripetizioni recenti e vie più salite;
- selettore italiano/inglese identificato dalle bandiere;
- logo ClimbingSide nella navigazione e home dedicata a Climbing Side Roma;
- catalogo pubblico di pareti, vie e boulder;
- ricerca, filtri, ordinamento per grado francese e paginazione;
- dettaglio parete con riepilogo, filtro per tipo, ordinamenti bidirezionali,
  grado medio proposto, vie personali evidenziate e istogramma dei gradi;
- dettaglio via con grado ufficiale in evidenza, riepilogo della propria ripetizione,
  distribuzione decimale dei gradi proposti, tipo, parete e route setter;
- creazione e modifica delle vie riservata a `RouteSetter` e `Admin`;
- gestione delle pareti e degli utenti riservata agli amministratori;
- archiviazione conservativa e cancellazione permanente protetta;
- nomi di pareti e vie univoci senza distinzione tra maiuscole e minuscole;
- ripetizione autonoma con utente, via, data, valutazione e grado percepito;
- distinzione tra `Onsight`, `Flash`, numero di tentativi e `N.D.`;
- una sola ripetizione modificabile per utente e via;
- form di creazione con data odierna, tre stelle e grado ufficiale `.5` come valori
  iniziali quando la via è preselezionata;
- statistiche pubbliche di vie, pareti e utenti;
- una sola immagine per via, validata per tipo, contenuto, dimensione e numero di pixel;
- caricamento e sostituzione riservati a `RouteSetter` e `Admin`;
- eliminazione dell'immagine riservata agli amministratori;
- annotazione vettoriale modificabile con partenze, movimenti numerati e top;
- riposizionamento tramite trascinamento, annullamento, selezione e cancellazione dei marcatori;
- visualizzazione pubblica dell'immagine con annotazione responsive;
- filesystem locale in sviluppo e Cloudinary in produzione;
- profili con grado massimo, istogramma dei gradi, pareti e ripetizioni ordinabili per
  data o grado ufficiale;
- elenco utenti ordinabile per nome, vie completate e grado massimo;
- dashboard pubblica con statistiche collettive per tipo, grado, parete e mese;
- dashboard operativa riservata agli amministratori;
- audit persistente e non modificabile delle operazioni amministrative importanti;
- comando idempotente per generare dati dimostrativi senza credenziali utilizzabili;
- health check del database;
- logging JSON in produzione;
- Docker e PostgreSQL per lo sviluppo;
- pytest, Ruff, mypy, pre-commit e GitHub Actions.

## Direzione visiva

L'incremento 7 introduce un design system coerente per tutte le pagine. La direzione
prende spunto dalla densità informativa e dal contrasto di Climbook senza copiarne
layout, marchio o componenti: ClimbingSide usa una testata antracite, accento ambra,
titoli condensati, bordi netti e schede compatte pensate per la consultazione in
palestra. Home, cataloghi, dettagli, profili, form, statistiche e gestione condividono
ora la stessa gerarchia visiva.

L'incremento 8 rende le pagine più vicine al flusso operativo dell'applicazione
originale: i dati delle pareti sono più leggibili, le liste sono filtrabili e ordinabili
in entrambe le direzioni, gli elementi già completati sono evidenziati senza etichette
ridondanti e gli istogrammi condividono un unico componente accessibile e responsive.

L'incremento 9 integra il logo della palestra nella navigazione, compatta il selettore
lingua con le bandiere italiana e britannica, semplifica il messaggio della home e usa
la dicitura `Tipo` nell'interfaccia per distinguere tra vie e boulder.

Su smartphone la navigazione diventa un menu espandibile, i riepiloghi si ridispongono,
la tabella delle attività recenti diventa una lista leggibile e le azioni sulla via
occupano tutta la larghezza disponibile. La foto hero usa l'immagine più recentemente
aggiornata di una via attiva; se non esistono immagini viene mostrato un fondo neutro.

I font Barlow e Barlow Condensed sono caricati da Google Fonts con `display=swap` per
mantenere il testo immediatamente visibile; i fallback di sistema consentono comunque
di usare l'applicazione se il servizio esterno non è raggiungibile.

L'immagine originale viene conservata una sola volta. L'annotazione non viene impressa
nel file: è memorizzata come coordinate normalizzate e viene sovrapposta nel browser.
In questo modo resta modificabile e continua ad allinearsi quando l'immagine viene
ridimensionata su smartphone.

## Requisiti

- Python 3.12–3.14; Python 3.14 è la versione prevista per il container di produzione;
- [uv](https://docs.astral.sh/uv/);
- Docker, facoltativo ma consigliato per usare PostgreSQL in locale.

## Avvio rapido con SQLite

Questa modalità è utile per verificare rapidamente l'interfaccia locale.

```bash
cp .env.example .env
uv sync --group dev
uv run python manage.py migrate
uv run python manage.py seed_demo --dry-run
uv run python manage.py seed_demo
uv run python manage.py runserver
```

Aprire `http://127.0.0.1:8000/`.

Per creare il primo amministratore:

```bash
uv run python manage.py createsuperuser
```

In sviluppo le email non vengono spedite: il loro contenuto e i link di verifica o
recupero password vengono mostrati nel terminale del server.

Se `DATABASE_URL` non è definito, la configurazione di sviluppo usa SQLite. SQLite non
verrà usato in produzione.

## Avvio con PostgreSQL e Docker

```bash
docker compose up -d --build
docker compose exec web python manage.py migrate
```

L'applicazione sarà disponibile su `http://127.0.0.1:8000/`.

Con `-d` i container restano avviati in background. Se il comando `exec` segnala che
il servizio `web` non è in esecuzione, controllare prima lo stato e i log:

```bash
docker compose ps
docker compose logs web
```

## Comandi di verifica

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy apps config
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py check
```

## Configurazione

Le variabili disponibili sono documentate in `.env.example`. Non inserire mai `.env`,
database, credenziali o file caricati nel repository.

In produzione sono obbligatori almeno:

- `DJANGO_SECRET_KEY`;
- `DATABASE_URL` PostgreSQL;
- `DJANGO_ALLOWED_HOSTS`;
- `DJANGO_CSRF_TRUSTED_ORIGINS`;
- configurazione SMTP per le email;
- `CLOUDINARY_URL` per l'archiviazione esterna delle immagini.

In sviluppo i file vengono salvati nella cartella locale `media/`, esclusa da Git e dal
contesto di build Docker. In produzione il backend `CloudinaryMediaStorage` usa l'SDK
ufficiale Cloudinary; nel database viene conservato solo l'identificativo del file.

## Health check

`GET /healthz/` restituisce:

```json
{"status": "ok"}
```

Se il database non è raggiungibile restituisce HTTP 503 senza esporre dettagli tecnici.

## Flussi account disponibili

- `/register/`: registrazione; l'account resta inattivo fino alla verifica email;
- `/register/resend/`: nuovo invio del link senza rivelare se l'account esiste;
- `/login/` e `/logout/`: accesso e uscita, con logout solo tramite richiesta POST;
- `/password-reset/`: recupero password;
- `/account/`: profilo personale;
- `/account/edit/`: modifica username, nome, cognome e lingua;
- `/account/password/`: cambio password per utenti autenticati;
- `/users/`: elenco pubblico ordinabile dei climber;
- `/users/<username>/`: profilo pubblico, senza email o dati riservati;
- `/statistics/`: statistiche collettive pubbliche del catalogo e delle ripetizioni.

Dopo cinque accessi falliti con la stessa combinazione username/IP, il login viene
bloccato per quindici minuti. Le soglie sono configurabili con
`LOGIN_FAILURE_LIMIT` e `LOGIN_LOCKOUT_MINUTES`.

## Catalogo disponibile

- `/walls/`: elenco pubblico delle pareti, ricerca e ordinamento;
- `/walls/<id>/`: dettaglio con vie attive, tipi e distribuzione dei gradi;
- `/routes/`: elenco pubblico con ricerca, parete, tipo, grado, stato e ordinamento;
- `/routes/<id>/`: dettaglio della via e route setter associati;
- `/routes/<id>/image/`: caricamento o sostituzione dell'unica immagine;
- `/routes/<id>/annotation/`: editor dell'annotazione modificabile;
- `/routes/<id>/image/delete/`: conferma di eliminazione per gli amministratori;
- `/ascents/new/`: registrazione di una ripetizione;
- `/ascents/<id>/edit/`: modifica della propria ripetizione;
- `/ascents/<id>/delete/`: eliminazione confermata della propria ripetizione;
- `/walls/new/` e `/walls/<id>/edit/`: gestione amministrativa delle pareti;
- `/routes/new/` e `/routes/<id>/edit/`: gestione delle vie per RouteSetter e Admin;
- `/management/`: riepilogo operativo e attività recente, riservato ad Admin.

Una parete può contenere contemporaneamente vie e boulder. Una via può avere nessuno,
uno o più route setter. Il grado ufficiale usa la scala francese da `4a` a `9c`; una via
contrassegnata come `Project` non ha ancora un grado ufficiale.

Ogni utente può registrare una sola ripetizione per via e successivamente modificarla o
eliminarla. La ripetizione contiene data, valutazione da 1 a 5, grado percepito francese
con decimale da 0 a 9 e informazione sui tentativi. Le date future e le combinazioni
incoerenti dei tentativi vengono rifiutate sia dai form sia dai vincoli del database.
Le ripetizioni sono pubbliche, come concordato, ma le email degli utenti non vengono
mostrate.

Gli elenchi mostrano per impostazione predefinita solo gli elementi attivi. Gli elementi
archiviati restano consultabili tramite il filtro di stato e possono essere ripristinati.
Per evitare perdite accidentali, la cancellazione permanente:

1. è disponibile solo agli amministratori;
2. richiede che l'elemento sia già archiviato;
3. richiede di digitare esattamente il nome dell'elemento;
4. viene bloccata se esistono dati collegati protetti.

Una via con ripetizioni non può quindi essere eliminata definitivamente. Deve restare
archiviata, preservando lo storico e le statistiche. Anche gli utenti con ripetizioni
sono protetti dalla cancellazione accidentale: per rimuoverli è necessaria una futura
procedura esplicita di anonimizzazione o cancellazione controllata.

## Ruoli

- `User`: consulta il catalogo e crea, modifica o elimina esclusivamente le proprie
  ripetizioni;
- `RouteSetter`: può creare, modificare, archiviare e ripristinare vie, ma non gestisce
  pareti, utenti o cancellazioni permanenti; può caricare, sostituire e annotare le
  immagini, mantiene le normali funzioni sulle proprie ripetizioni e non accede al
  Django Admin;
- `Admin`: accede al Django Admin e riceve tutti i permessi applicativi.

I gruppi vengono creati dalla migrazione e i permessi vengono sincronizzati dopo ogni
`migrate`. Il ruolo di un utente può essere modificato dal pannello amministrativo.

## Dashboard, audit e dati dimostrativi

La pagina pubblica `/statistics/` mostra il numero di vie attive, la distinzione tra vie
e boulder, i Project, il massimo grado ufficiale attivo, le distribuzioni per grado e
parete e le ripetizioni registrate negli ultimi dodici mesi. I mesi senza attività sono
mostrati esplicitamente; le vie archiviate non alterano le statistiche del catalogo
attivo, mentre le ripetizioni storiche restano conteggiate.

La pagina `/management/` è accessibile esclusivamente ad `Admin` e riunisce i conteggi
operativi, i collegamenti alle funzioni di gestione e le ultime venti attività
amministrative. Il registro completo è consultabile dal Django Admin ed è di sola
lettura: registra creazioni, modifiche, archiviazioni, ripristini, cancellazioni,
variazioni di ruolo e operazioni sulle immagini. Conserva identificativi tecnici e
stato non sensibile; non duplica password, email o nomi originali dei file.

Per popolare un ambiente locale con tre pareti, otto vie o boulder, tre utenti e otto
ripetizioni non sensibili:

```bash
uv run python manage.py seed_demo --dry-run
uv run python manage.py seed_demo
```

Il primo comando valida l'intera operazione e annulla la transazione. Il secondo applica
i dati. Il comando è ripetibile senza duplicati e agisce solo sui record riservati con
prefisso `[DEMO]` o username `demo-`; gli utenti demo usano indirizzi `example.invalid`,
non sono amministratori e hanno password inutilizzabili. Se uno username riservato è
già associato a un indirizzo diverso, il record reale viene saltato senza modificarlo.

## Immagini e annotazioni

Ogni via può avere al massimo un record `RouteImage`. Sono accettati JPEG, PNG e WebP
non animati fino a 8 MB, 12.000 pixel per lato e 36 megapixel complessivi. L'estensione,
il content type dichiarato e il contenuto effettivo vengono controllati nel backend.
Il nome salvato contiene un UUID e non riutilizza il nome originale fornito dall'utente.

L'annotazione JSON è versionata e validata anche dal server. Può contenere al massimo
100 marcatori e usa coordinate comprese tra 0 e 1. I tipi disponibili sono:

- partenza sinistra;
- partenza destra;
- movimento numerato automaticamente;
- top.

Partenze e top sono unici; i movimenti devono essere numerati consecutivamente. La
sostituzione dell'immagine azzera intenzionalmente i marcatori, perché le vecchie
coordinate potrebbero non corrispondere al nuovo file. Il file precedente viene rimosso
dallo storage solo dopo il commit del database. La cancellazione dell'immagine è
riservata ad `Admin`; un `RouteSetter` può correggere un file errato sostituendolo.

## Pubblicazione consigliata: Railway e Cloudinary

Railway è la scelta più semplice per questa applicazione perché può costruire il
`Dockerfile`, fornire PostgreSQL, eseguire un comando pre-deploy e controllare
`/healthz/`. Il piano gratuito è adatto soprattutto a prove e piccoli ambienti; per una
palestra reale va considerato un piccolo costo mensile e va impostato un limite di spesa.
Cloudinary può essere usato separatamente per le immagini, evitando di affidarsi al
filesystem effimero del container.

Procedura:

1. pubblicare il repository su GitHub e creare su Railway un progetto dal repository;
2. aggiungere al progetto un servizio PostgreSQL e collegare `DATABASE_URL` al servizio
   web;
3. creare un account Cloudinary, copiare `CLOUDINARY_URL` nel secret store di Railway e
   non inserirlo mai in Git o nei log;
4. configurare sul servizio web le variabili:
   `DJANGO_SETTINGS_MODULE=config.settings.production`, `DJANGO_SECRET_KEY`,
   `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `CLOUDINARY_URL` e i parametri
   SMTP descritti in `.env.example`;
5. impostare il pre-deploy command su `python manage.py migrate --noinput`;
6. lasciare come start command il `CMD` del Dockerfile oppure usare
   `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 60`;
7. impostare l'health check HTTP su `/healthz/`, generare il dominio pubblico e inserire
   quel dominio in `DJANGO_ALLOWED_HOSTS` e, con schema `https://`, in
   `DJANGO_CSRF_TRUSTED_ORIGINS`;
8. dopo il primo deploy eseguire una sola volta `python manage.py createsuperuser` dalla
   shell del servizio.

Prima di ogni rilascio eseguire localmente test, lint, type check e controllo delle
migrazioni. In produzione mantenere una sola replica finché il volume di traffico resta
quello previsto; le immagini sono già esterne e non richiedono un volume Railway.

### Backup e ripristino

Attivare backup regolari di PostgreSQL. In alternativa, pianificare un `pg_dump` cifrato
verso uno storage separato e provare periodicamente il ripristino su un database di test:

```bash
pg_dump --format=custom --no-owner --file=climbingside.dump "$DATABASE_URL"
createdb climbingside_restore_test
pg_restore --no-owner --dbname=climbingside_restore_test climbingside.dump
```

I backup del database non contengono i file Cloudinary, ma contengono i loro
identificativi e tutte le annotazioni. Per un ripristino completo va quindi mantenuta
anche la politica di backup/versionamento prevista dal piano Cloudinary scelto.
