# VTV Platforma — Lietotaju Plūsmas un Lietošanas Scenāriji

> Pārskats valdei — apraksta, kā platforma tiek izmantota ikdienas sabiedriskā transporta pārvaldībā.

---

## Platformas Kopsavilkums

VTV ir vienota sabiedriskā transporta operāciju pārvaldības platforma Rīgas pilsētas transportam. Tā aizstāj sadrumstalotus manuālus procesus (izklājlapas, neapstrādāti GTFS faili, telefona zvani) ar vienu tīmekļa CMS sistēmu, kas papildināta ar AI asistentu.

**Mērķa operators:** Rīgas Satiksme — 1 097 transportlīdzekļi, ~80 maršruti, ~1 500 pieturas.

---

## Lietotāju Lomas

| Loma | Kas | Piekļuves līmenis |
|------|-----|-------------------|
| **Administrators** | IT personāls, sistēmas vadītāji | Pilna piekļuve — visu datu pārvaldība, lietotāju vadība, GTFS imports/eksports |
| **Redaktors** | Grafiku plānotāji, maršrutu projektētāji | Maršrutu, grafiku, pieturu un dokumentu izveide un rediģēšana |
| **Dispečers** | Operāciju centra darbinieki | Operatīvais pārskats, AI asistents, reāllaika izsekošana |
| **Skatītājs** | Auditori, ārējās ieinteresētās puses | Tikai lasīšanas piekļuve visiem datiem |

---

## 1. Rīta Maiņas Sākums — Dispečera Darba Diena

### Scenārijs
Dispečers ierodas operāciju centrā plkst. 5:30 un atver VTV platformu, lai sagatavotu rīta maiņu.

### Plūsma

1. **Pieslēgšanās** — Ievada lietotājvārdu un paroli. Sistēma atpazīst dispečera lomu un parāda atbilstošo saskarni latviešu valodā.

2. **Paneļa pārskats** — Sākumlapā redz galvenos rādītājus: aktīvo maršrutu skaits, transportlīdzekļu statuss, šodienas notikumi kalendārā.

3. **Reāllaika karte** — Atver maršrutu lapu. Kartē redzami visi transportlīdzekļi, kas jau ir izbraukuši rīta reisā. Marķieri ir krāsoti pēc maršruta krāsas un atjaunojas ik pēc 10 sekundēm.
   - Redz, ka 3. maršruta autobuss ir aizkavējies — marķieris ir tālu aiz grafika pozīcijas.
   - Noklikšķina uz maršruta tabulas rindas, lai redzētu detalizētu informāciju.

4. **AI asistenta vaicājums** — Atver čata lapu un jautā: *"Kāds ir 3. maršruta autobusa pašreizējais statuss?"*
   - AI asistents atbild latviski ar reāllaika datiem: transportlīdzekļa pozīciju, kavējuma apmēru, nākamo pieturu.
   - Dispečers jautā tālāk: *"Vai ir pieejami rezerves šoferi rīta maiņai?"*
   - AI pārbauda šoferu pieejamību un atbild ar sarakstu.

5. **Dokumentu meklēšana** — Dispečerim jāpārbauda, kāda ir procedūra ceļa remonta gadījumā.
   - Jautā AI: *"Kāda ir maršruta novirzīšanas procedūra ceļa remonta laikā?"*
   - AI meklē augšupielādētajos dokumentos (SOP, noteikumi) un atbild ar konkrētu procedūru un atsauci uz avota dokumentu.

### Biznesa vērtība
Dispečers iegūst pilnu operatīvo ainu vienā ekrānā, nevis zvanot kolēģiem vai pārlūkojot vairākas sistēmas. AI asistents aizstāj manuālu datu meklēšanu.

---

## 2. Sezonas Grafiku Maiņa — Plānotāja Darbs

### Scenārijs
Maija sākumā plānotājs sagatavo vasaras grafiku maiņu, kas stājas spēkā 1. jūnijā. Vairākiem maršrutiem mainās reisu biežums un darba laiki.

### Plūsma

1. **Esošā grafika pārskats** — Atver grafiku pārvaldības lapu, cilni "Kalendāri". Redz visus aktīvos servisa kalendārus:
   - `DARBA_DIENAS` — Pr-Pk, 2. janvāris līdz 31. maijam
   - `BRIVDIENAS` — Se-Sv, 2. janvāris līdz 31. maijam
   - `VASARA_DARBA_DIENAS` — Pr-Pk, 1. jūnijs līdz 31. augustam

2. **Jauna vasaras kalendāra izveide** — Noklikšķina "Izveidot kalendāru":
   - Servisa ID: `VASARA_2026`
   - Darba dienas: Pr, Ot, Tr, Ce, Pk (atzīmē)
   - Sākuma datums: 2026-06-01
   - Beigu datums: 2026-08-31
   - Saglabā.

3. **Svētku izņēmumu pievienošana** — Atver jauno kalendāru un pievieno izņēmumus:
   - `2026-06-23` (Līgo vakars) — tips: **Noņemts** (serviss nedarbojas)
   - `2026-06-24` (Jāņi) — tips: **Noņemts**
   - Tagad visi reisi, kas atsaucas uz `VASARA_2026`, automātiski izlaidīs šos datumus.

4. **Reisu pārskatīšana** — Pāriet uz cilni "Reisi". Filtrē pēc `VASARA_2026` kalendāra:
   - Pārbauda, vai visi plānotie vasaras reisi ir pareizi piesaistīti.
   - Noklikšķina uz konkrēta reisa, lai pārbaudītu pieturlaikus — katras pieturas ierašanās un atiešanas laiku.

5. **Vecā kalendāra noslēgšana** — Atver `DARBA_DIENAS` kalendāru un maina beigu datumu uz 2026-05-31, lai tas automātiski apstājas pirms vasaras grafika sākuma.

### Biznesa vērtība
Sezonas maiņa, kas iepriekš aizņēma nedēļu manuāla darba ar CSV failiem, tagad ir paveicama dažu stundu laikā ar pilnu audita pierakstu par izmaiņām.

---

## 3. Svētku Dienas Pārvaldība — Izņēmumu Scenārijs

### Scenārijs
18. novembris (Latvijas Proklamēšanas diena) iekrīt trešdienā. Plānotājam jānodrošina, ka darba dienu serviss nedarbojas, bet svētku serviss ir aktīvs.

### Plūsma

1. **Darba dienu kalendāra atvēršana** — Atver `DARBA_DIENAS` kalendāru grafiku pārvaldībā.

2. **Izņēmuma pievienošana** — Pievieno izņēmumu:
   - Datums: `2026-11-18`
   - Tips: **Noņemts** (serviss nedarbojas šajā datumā)
   - Visi darba dienu reisi automātiski izlaiž šo dienu.

3. **Svētku kalendāra atvēršana** — Atver `SVETKI` kalendāru.

4. **Servisa pievienošana** — Pievieno izņēmumu:
   - Datums: `2026-11-18`
   - Tips: **Pievienots** (serviss darbojas šajā datumā, kaut arī kalendārs to parasti neietver)
   - Svētku grafika reisi darbojas 18. novembrī.

5. **Pārbaude** — Filtrē reisus pēc datuma un pārliecinās, ka:
   - Darba dienu reisi nav redzami 18. novembrim
   - Svētku reisi ir aktīvi šajā datumā

### Biznesa vērtība
Viena svētku diena ietekmē simtiem reisu. Bez šīs sistēmas plānotājam būtu jārediģē katrs reiss atsevišķi. Ar kalendāra izņēmumiem — divas darbības, un viss ir pārvaldīts.

---

## 4. Jauna Maršruta Izveide — No Nulles Līdz Darbībai

### Scenārijs
Rīgas Satiksme atver jaunu autobusu maršrutu uz jaunbūvju rajonu. Redaktoram jāizveido maršruts, pieturas un grafiks sistēmā.

### Plūsma

1. **Maršruta izveide** — Atver maršrutu lapu, noklikšķina "Izveidot maršrutu":
   - Īsais nosaukums: `99`
   - Garais nosaukums: `Centrs - Mežaparks - Jauncienā`
   - Transporta veids: Autobuss
   - Maršruta krāsa: `#FF6B35` (oranža)
   - Aģentūra: Rīgas Satiksme
   - Statuss: Aktīvs

2. **Pieturu izveide** — Pāriet uz pieturu lapu:
   - Atver karti un noklikšķina uz kartes, lai novietotu jauno pieturu.
   - Ievada nosaukumu: "Jaunciema iela"
   - GTFS ID: `jaunciema_01`
   - Atrašanās vietas tips: Pietura
   - Ratiņkrēslu pieejamība: Pieejams
   - Atkārto katrai pieturai maršrutā (~15 pieturas).

3. **Kalendāra piesaiste** — Atver grafiku pārvaldību:
   - Izveido jaunu kalendāru `MARSRUTS_99` vai piesaista esošo `DARBA_DIENAS`.

4. **Reisu izveide** — Cilnē "Reisi" izveido katru reisu:
   - Maršruts: 99
   - Kalendārs: `DARBA_DIENAS`
   - Virziens: Turpceļš / Atpakaļceļš
   - Galapunkts: "Jaunciema iela" / "Centrs"
   - Pieturlaiki tiek pievienoti caur GTFS importu vai manuāli.

5. **GTFS eksports** — Kad viss ir gatavs, eksportē GTFS ZIP failu integrācijai ar Google Maps un citām pasažieru informācijas sistēmām.

### Biznesa vērtība
Jauna maršruta izveide no nulles — ar pieturu kartēšanu, grafiku un reisu plānošanu — ir pilnībā paveicama platformā bez ārējiem rīkiem.

---

## 5. GTFS Datu Atjaunināšana — Regulārais Imports

### Scenārijs
Rīgas Satiksme katru nedēļu publicē atjauninātu GTFS datu kopu. Administratoram jāimportē jaunākie dati, nesabojājot esošos pielāgojumus.

### Plūsma

1. **Datu lejupielāde** — GTFS ZIP fails ir pieejams Rīgas Satiksmes atvērtajos datos: `https://saraksti.rigassatiksme.lv/riga/gtfs.zip`

2. **Importa cilne** — Atver grafiku pārvaldībā cilni "Imports un validācija".

3. **Faila augšupielāde** — Velk un nomet GTFS ZIP failu augšupielādes zonā. Sistēma parsē 7 standarta GTFS failus:
   - `agency.txt` — transporta aģentūras
   - `routes.txt` — maršruti
   - `stops.txt` — pieturas (neimportē šeit — pieturām ir atsevišķa pārvaldība)
   - `calendar.txt` — servisa kalendāri
   - `calendar_dates.txt` — kalendāra izņēmumi
   - `trips.txt` — reisi
   - `stop_times.txt` — pieturlaiki

4. **Importa rezultāti** — Sistēma ziņo: cik ierakstu izveidoti, atjaunināti, izlaisti un kļūdas. Izmanto apvienošanas/upsert stratēģiju — esošie manuālie pielāgojumi netiek pārrakstīti.

5. **Validācija** — Palaiž validācijas pārbaudi, lai atklātu problēmas: trūkstošas atsauces, nederīgi datumu diapazoni, bāreņu pieturlaiki.

### Biznesa vērtība
GTFS atbilstība ir obligāta integrācijai ar Google Maps, Apple Maps un ES pasažieru informācijas sistēmām. Regulārs imports nodrošina, ka dati ir aktuāli ar minimālu manuālo darbu.

---

## 6. Reāllaika Operatīvā Uzraudzība

### Scenārijs
Dispečers uzrauga rīta sastrēgumstundu. Vairāki autobusi ir aizkavējušies satiksmes sastrēguma dēļ Brīvības ielā.

### Plūsma

1. **Kartes pārskats** — Maršrutu lapā karte rāda visus aktīvos transportlīdzekļus reāllaikā. Marķieri ir krāsoti pēc maršruta un atjaunojas ik pēc 10 sekundēm.

2. **Kavējumu identificēšana** — Dispečers pamana, ka 18. trolejbusa marķieri ir sastrēgumā Brīvības ielas posmā — vairāki transportlīdzekļi atrodas tuvu viens otram, nevis vienmērīgi izkliedēti.

3. **Detaļu pārbaude** — Noklikšķina uz maršruta tabulā, lai redzētu:
   - Reisu skaits maršrutā
   - Kalendāra piederība
   - Galapunkti un virzieni

4. **AI vaicājums** — Čatā jautā: *"Cik lielā mērā 18. trolejbuss šodien kavējas?"*
   - AI analizē GTFS-RT datus un atbild: vidējais kavējums, visvairāk ietekmētie reisi, salīdzinājums ar parasto darbību.

5. **Lēmuma pieņemšana** — Balstoties uz datiem, dispečers pieņem lēmumu:
   - Izsauc papildu transportlīdzekli no depo
   - Vai gaida situācijas uzlabošanos

### Biznesa vērtība
Dispečers redz visa tīkla stāvokli vienā skatā, nevis zvana katram šoferim. Kavējumi ir redzami acumirklī, nevis pēc pasažieru sūdzībām.

---

## 7. Dokumentu un Zināšanu Pārvaldība

### Scenārijs
Jauns noteikums par minimālo reisu intervālu stājas spēkā. Administratoram jāaugšupielādē dokuments un jānodrošina, ka tas ir pieejams visiem darbiniekiem.

### Plūsma

1. **Dokumenta augšupielāde** — Atver dokumentu lapu, noklikšķina "Augšupielādēt":
   - Faila izvēle: `2026_reisu_intervala_noteikums.pdf`
   - Nosaukums: "Minimālā reisu intervāla noteikums 2026"
   - Apraksts: "Jaunie noteikumi par minimālo intervālu starp reisiem visos pilsētas maršrutos"
   - Valoda: Latviešu
   - Domēns: Noteikumi

2. **Automātiska apstrāde** — Sistēma automātiski:
   - Izvilina tekstu no PDF
   - Sadala gabalos (chunks) AI meklēšanai
   - Izveido vektoru iegulšanas (embeddings) meklēšanas indeksam

3. **Dokumenta pārskats** — Pēc apstrādes noklikšķina uz dokumenta, lai pārbaudītu:
   - Statuss: "Apstrādāts"
   - Gabalu skaits: 47
   - Satura priekšskatījums — izvērsams sadaļas ar izvilkto tekstu

4. **AI meklēšana darbībā** — Jebkurš darbinieks tagad čatā var jautāt:
   - *"Kāds ir minimālais reisu intervāls 3. maršrutam?"*
   - AI atrod atbildi augšupielādētajā dokumentā un atbild ar atsauci uz avotu.

5. **Dokumenta lejupielāde** — Jebkurš darbinieks var lejupielādēt oriģinālo PDF failu tieši no platformas.

### Biznesa vērtība
Noteikumi un procedūras ir pieejami sekundes laikā caur AI asistentu, nevis meklējot e-pastos vai papīra arhīvos. Jaunie darbinieki var ātri atrast nepieciešamo informāciju.

---

## 8. Pieturu Tīkla Pārvaldība

### Scenārijs
Redaktors saņem uzdevumu pievienot 5 jaunas pieturas jaunajam maršrutam un pārbaudīt esošo pieturu precizitāti.

### Plūsma

1. **Kartes pārskats** — Atver pieturu lapu ar karti. Visas esošās pieturas redzamas kā marķieri. Gala pieturas (pirmā un pēdējā maršrutā) ir atzīmētas ar atšķirīgiem marķieriem.

2. **Tuvāko pieturu meklēšana** — Ievada koordinātas vai adresi, lai atrastu tuvākās esošās pieturas. Sistēma aprēķina attālumu (Haversine formula) un parāda rezultātus.

3. **Jaunas pieturas izveide** — Noklikšķina uz kartes vietā, kur vajadzīga jauna pietura:
   - Nosaukums: "Skanstes iela"
   - GTFS ID: `skanstes_01`
   - Atrašanās vietas tips: Pietura
   - Ratiņkrēslu pieejamība: Pieejams
   - Apraksts: "Pie Skanstes biroju centra"

4. **Pozīcijas korekcija** — Velk marķieri uz karti, lai precīzi novietotu pieturu. Koordinātas atjaunojas automātiski.

5. **Filtrēšana** — Filtrē pieturas pēc:
   - Atrašanās vietas tipa (pietura, stacija, ieeja/izeja)
   - Aktīvā/neaktīvā statusa
   - Nosaukuma meklēšana

### Biznesa vērtība
Vizuālā kartēšana novērš kļūdas, ko izklājlapas slēpj — nepareizi novietotas pieturas, robus pārklājumā, dublikātus.

---

## 9. Maršrutu Pārvaldība un Analītika

### Scenārijs
Administrators pārvalda pilnu maršrutu katalogu — ~80 maršruti ar autobusiem, trolejbusiem un tramvajiem.

### Plūsma

1. **Maršrutu saraksts** — Tabula ar visiem maršrutiem: numurs, nosaukums, transporta veids, aktīvā/neaktīvā statuss. Servera puses lapošana apstrādā lielu datu apjomu.

2. **Filtrēšana un meklēšana** — Filtrē pēc:
   - Transporta veida (autobuss, trolejbuss, tramvajs)
   - Aktīvā statusa
   - Meklē pēc maršruta numura vai nosaukuma

3. **Maršruta detaļas** — Noklikšķina uz maršruta, lai redzētu:
   - GTFS maršruta ID
   - Aģentūra
   - Maršruta krāsa (vizuāls priekšskatījums)
   - Kārtošanas secība
   - Aktīvā/neaktīvā statuss
   - Izveides un atjaunināšanas laiki

4. **Maršruta rediģēšana** — Maina maršruta parametrus:
   - Nosaukuma korekcija
   - Krāsas maiņa kartei
   - Statusa maiņa (aktīvs → neaktīvs, piemēram, sezonas maršrutam)

5. **Transportlīdzekļu izsekošana kartē** — Kartē redzami visi aktīvie transportlīdzekļi, krāsoti pēc maršruta krāsas. Atbalsta vairākus GTFS-RT avotus (Rīga, Jūrmala, Pierīga, ATD).

### Biznesa vērtība
Vienots pārskats par visu maršrutu tīklu ar reāllaika operatīvajiem datiem vienā skatā.

---

## 10. AI Asistenta Iespējas — Pilns Pārskats

### Kas var izmantot
Visi autentificētie lietotāji (izņemot skatītāja lomu).

### Pieejamie AI rīki (10 kopā)

| Kategorija | Rīki | Iespējas |
|-----------|------|----------|
| Transports (5) | Autobusu statuss, maršrutu grafiki, pieturu meklēšana, punktualitātes atskaites, šoferu pieejamība | Vaicā visus transporta operatīvos datus |
| Zināšanu bāze (1) | Dokumentu meklēšana | RAG meklēšana augšupielādētajos dokumentos |
| Obsidian (4) | Krātuves vaicājumi, piezīmju pārvaldība, mapju pārvaldība, masveida operācijas | Personīgā/komandas zināšanu pārvaldība |

### Tipiski vaicājumi

**Operatīvie:**
- *"Kāds ir 18. trolejbusa pašreizējais statuss?"*
- *"Vai kāds autobuss šodien kavējas vairāk par 10 minūtēm?"*
- *"Parādi 3. maršruta grafiku darba dienās."*

**Pieturu informācija:**
- *"Kādas pieturas atrodas 500 metru rādiusā no Brīvības ielas?"*
- *"Parādi pieturas nosaukuma meklēšanā — Mežaparks."*

**Dokumentu meklēšana:**
- *"Kāda ir procedūra maršruta novirzīšanai ceļa remonta laikā?"*
- *"Kāds ir minimālais reisu intervāls saskaņā ar jaunajiem noteikumiem?"*

**Analītika:**
- *"Kāda ir 2. maršruta punktualitāte šonedēļ?"*
- *"Kuri maršruti visvairāk kavējas rīta sastrēgumstundā?"*

### Drošības ierobežojums
Visi transporta rīki ir **tikai lasīšanai**. AI var vaicāt un ziņot, bet nevar izveidot, mainīt vai dzēst transporta datus. **AI konsultē — cilvēki pieņem lēmumus.**

### Biznesa vērtība
Dabiskās valodas saskarne aizstāj manuālu navigāciju pa vairākām sistēmām. Dispečers dabū atbildi sekundes laikā, nevis minūtēs.

---

## 11. Drošība un Piekļuves Kontrole

### Piekļuves matrica

| Funkcija | Administrators | Redaktors | Dispečers | Skatītājs |
|----------|---------------|-----------|-----------|-----------|
| Maršruti — skatīt | Jā | Jā | Jā | Jā |
| Maršruti — veidot/rediģēt/dzēst | Jā | Jā | Nē | Nē |
| Pieturas — skatīt | Jā | Jā | Jā | Jā |
| Pieturas — veidot/rediģēt/dzēst | Jā | Jā | Nē | Nē |
| Grafiki — skatīt | Jā | Jā | Jā | Jā |
| Grafiki — veidot/rediģēt/dzēst | Jā | Jā | Nē | Nē |
| GTFS imports | Jā | Jā | Nē | Nē |
| Dokumenti — skatīt/lejupielādēt | Jā | Jā | Jā | Jā |
| Dokumenti — augšupielādēt/dzēst | Jā | Jā | Nē | Nē |
| AI asistents | Jā | Jā | Jā | Nē |
| Lietotāju pārvaldība | Jā | Nē | Nē | Nē |

### Drošības pasākumi
- Paroļu šifrēšana ar bcrypt
- Aizsardzība pret brutāla spēka uzbrukumiem: 5 neveiksmīgi mēģinājumi = 15 minūšu bloķēšana
- Ātruma ierobežojumi visiem API galapunktiem
- Drošības galvenes (CSP, HSTS, X-Frame-Options DENY)
- Sesiju autentifikācija ar Auth.js v5

---

## 12. Daudzvalodība

### Atbalstītās valodas
- **Latviešu (lv)** — Primārā valoda, pilns UI tulkojums ar pareizām diakritiskajām zīmēm
- **Angļu (en)** — Sekundārā valoda starptautiskajām ieinteresētajām pusēm

### Kā darbojas
- Valodas pārslēgs sānjoslā (LV | EN)
- Viss lietotājam redzamais teksts ir tulkots (142+ atslēgas katrā lokālē)
- Datumi, skaitļi un laiki formatēti atbilstoši lokālei
- AI asistents nosaka valodu un atbild atbilstoši

---

## Pielikums: Tehnoloģiju Kopsavilkums

| Komponents | Tehnoloģija | Statuss |
|-----------|-----------|--------|
| CMS priekšgals | Next.js 16, React 19, Tailwind CSS v4, shadcn/ui | Produkcijā |
| Aizmugures API | FastAPI, SQLAlchemy 2.0 (async), PostgreSQL 18 | Produkcijā |
| AI aģents | Pydantic AI, 10 rīki, straumēšana (SSE) | Produkcijā |
| Vektoru meklēšana | pgvector (PostgreSQL paplašinājums) | Produkcijā |
| Reāllaika kešatmiņa | Redis 7 | Produkcijā |
| Kartes | Leaflet + OpenStreetMap | Produkcijā |
| Izvietošana | Docker Compose (6 servisi, nginx reverss proksis) | Produkcijā |
| LLM nodrošinātājs | Maināms — pašlaik Anthropic Claude, pārslēdzams uz lokālu Ollama bez API izmaksām | Konfigurējams |

---

## Nākotnes Attīstība (Pēc MVP)

| Fāze | Funkcionalitāte | Aptuvens laiks |
|------|-----------------|----------------|
| 1. fāze | PostGIS telpiskās vaicājumi, visu Latvijas GTFS datu imports, WebSocket straumēšana | ~4 nedēļas |
| 2. fāze | Visu Latvijas pilsētu transporta dati (Daugavpils, Jūrmala, Pierīga), vilcienu izsekošana | ~4 nedēļas |
| 3. fāze | GPS izsekošana ar telefoniem (OwnTracks), aparatūras GPS (Teltonika), ceļojumu plānotājs | ~8 nedēļas |
| 4. fāze | ML prognozēšana (kavējumi, pasažieru noslodze), anomāliju atklāšana, publiskais API | Turpinās |
