# Rīgas pilsētas autobusu pārvaldības CMS — Galvenais plāns

**Projekts:** CMS Webportāls Rīgas Satiksme autobusu operācijām
**Versija:** 1.0 | **Datums:** 2026-02-11
**Piepūles līmenis:** DETERMINED | **Analīzes dziļums:** 6 paralēli aģenti, ~300k tokeni pētījumam

---

## Satura rādītājs

1. [Kopsavilkums](#1-kopsavilkums)
   - 1.5 [Produkta stratēģija — Kāpēc RS faktiski par to maksātu](#15-produkta-stratēģija--kāpēc-rs-faktiski-par-to-maksātu) *(iekļ. Finanšu ietekmes analīzi)*
     - [Pieņēmumu stresa testa rezultāti](#pieņēmumu-stresa-testa-rezultāti)
     - [Trīs lietas, kurām jābūt pareizām](#trīs-lietas-kurām-jābūt-pareizām)
     - [Pārskatītā izlaides secība](#pārskatītā-izlaides-secība)
     - [Finanšu ietekme — Ko RS ietaupa](#155-finanšu-ietekme--ko-rs-ietaupa)
     - [Kopējā finanšu ietekmes kopsavilkums](#f-kopējā-finanšu-ietekmes-kopsavilkums)
2. [Pētījuma rezultāti](#2-pētījuma-rezultāti)
   - 2.2.1 [Konkurences priekšrocību sintēze](#221-konkurences-priekšrocību-sintēze--ko-mēs-ņemam-no-katra)
   - 2.2.2 [Kāpēc RS to iegādātos](#222-kāpēc-rīgas-satiksme-to-iegādātos)
   - 2.2.3 [Uzticamības arhitektūra](#223-uzticamības-arhitektūra)
3. [Pārskatītā arhitektūra](#3-pārskatītā-arhitektūra)
4. [Tehnoloģiju steks](#4-tehnoloģiju-steks)
5. [Datubāzes shēma](#5-datubāzes-shēma)
6. [API dizains](#6-api-dizains)
7. [UI/UX dizains](#7-uiux-dizains)
8. [AI aģenta dizains](#8-ai-aģenta-dizains)
9. [Reāllaika izsekošana](#9-reāllaika-izsekošana)
10. [Ieviešanas ceļvedis](#10-ieviešanas-ceļvedis)
11. [Risku reģistrs](#11-risku-reģistrs)
12. [ISC verifikācija](#12-isc-verifikācija)
13. [5 kritiskie jautājumi pirms ieviešanas](#5-kritiskie-jautājumi-pirms-ieviešanas)

---

## 1. Kopsavilkums

### Ko mēs veidojam

**Vienotu CMS webportālu** Rīgas pilsētas autobusu operāciju pārvaldībai — maršrutiem, sarakstiem, autobusiem un vadītājiem — ar reāllaika izsekošanas karti un AI asistentu dispečeriem. Sistēma patērē un rada GTFS-atbilstošus datus, integrējas ar Rīgas Satiksme esošo infrastruktūru un atbilst ES/GDPR regulām.

### Galvenie arhitektūras lēmumi (pēc analīzes)

Seši paralēli analīzes virzieni (Padomes debates, First Principles, RedTeam stresa tests, konkurences analīze, Rīgas sabiedriskā transporta pētījums, tehnoloģiju steka pārskats) konverģēja uz šīm kritiskajām korekcijām sākotnējam priekšlikumam:

| Sākotnējais priekšlikums | Pārskatītais lēmums | Pamatojums |
|---|---|---|
| Next.js + FastAPI mikroservisi | **Modulārs monolīts Next.js** | 20 tehnoloģijas samazinātas līdz 12. Viena valoda, viena izpildlaika vide. |
| Prisma ORM | **Drizzle ORM** | Iebūvēts PostGIS atbalsts. Prisma prasa neapstrādātu SQL visiem telpiskajiem vaicājumiem. |
| Mapbox GL JS | **MapLibre GL JS + pašmitinātas flīzes** | Novērš atkarību no pārdevēja un $250+/mēnesī izmaksu risku. |
| PostgreSQL + PostGIS + TimescaleDB | **PostgreSQL + PostGIS uz Supabase** | TimescaleDB priekšlaicīgs 100 transportlīdzekļiem (20 ieraksti/sek ir triviāli). |
| Redis Pub/Sub + SSE | **Polling 1. fāzē, SSE 2. fāzē** | Redis nav nepieciešams ~100 transportlīdzekļiem vienā instancē. |
| Claude Opus 4.6 AI aģents no 1. dienas | **Nav AI 1. fāzē. Tikai konsultatīvs Sonnet 4.5 2. fāzē** | $60-90/mēnesī API izmaksas. Vispirms uzbūvēt labu UI, pievienot AI, kad dispečera problēmpunkti validēti. |
| Google OR-Tools maršrutu optimizācija | **Pilnībā izņemts** | Pilsētas autobusu maršruti ir fiksēti. OR-Tools atrisina VRP dinamiskam maršrutēšanai, ne fiksēto maršrutu tranzītam. |
| 2 valodas (TypeScript + Python) | **Tikai TypeScript** | Novērš Python/FastAPI. Viena valoda, viena ekosistēma. |

### Budžets

| Komponente | Mēneša izmaksas |
|---|---|
| Supabase Pro (PostgreSQL + PostGIS + Auth + Realtime) | $25 |
| Railway / Fly.io (Next.js mitināšana) | $5-20 |
| MapLibre + OpenFreeMap flīzes | $0 |
| Upstash Redis (2. fāze+, ja nepieciešams) | $0-10 |
| Claude API (2. fāze+, konsultatīvais režīms) | $30-60 |
| Domēns + SSL | $1-2 |
| **Kopā 1. fāze** | **$31-47/mēnesī** |
| **Kopā 2. fāze+** | **$61-117/mēnesī** |

### Termiņš (AI-paātrināts)

> **3x paātrinājums salīdzinājumā ar tradicionālo izstrādi.** Kodēšanas šaurā vieta novērsta — termiņu tagad nosaka cilvēka pārbaude, ārējo servisu iestatīšana un reālās pasaules testēšana.

| Fāze | Ilgums | Komanda | Rezultāti |
|---|---|---|---|
| **1. fāze: Pamata CMS** | 2-3 nedēļas | Claude Opus 4.6 + cilvēka pārbaude | Auth, GTFS imports/eksports, maršruta/pieturas/saraksta CRUD, statiska karte |
| **2. fāze: Reāllaika operācijas** | 2-3 nedēļas | Claude Opus 4.6 + cilvēka pārbaude | Reāllaika izsekošana (SSE), autoparka pārvaldība, vadītāju pārvaldība, analītika |
| **3. fāze: Inteliģence** | 2-3 nedēļas | Claude Opus 4.6 + cilvēka pārbaude | AI asistents (konsultatīvs), sarakstu ieteikumi, NeTEx/SIRI, uzlaboti paneļi |
| **Kopā** | **6-9 nedēļas** | | **Lejup no 24 nedēļām (tradicionāli) — 62-75% samazinājums** |

**Fāžu sadalījums (kas aizņem laiku):**
- ~20% kodēšana (Opus 4.6 — stundas, ne nedēļas)
- ~30% cilvēka pārbaude, testēšana un iterācija
- ~25% integrācijas testēšana ar reāliem GTFS datiem un ārējiem servisiem
- ~25% izvietošana, konfigurācija un UX uzlabojumi

---

## 1.5 Produkta stratēģija — Kāpēc RS faktiski par to maksātu

> *First Principles analīzes rezultāts (Opus 4.6). Apstrīd katru pieņēmumu par produkta dzīvotspēju.*

### Galvenā atziņa

**Šis nav "tranzīta CMS." Šī ir atbilstības-centrēta integrācijas slānis** vidēja izmēra Eiropas tranzīta aģentūrām, pārdots modulāri zem iepirkumu sliekšņiem, būvēts uz atvērtā koda pamatu un validēts caur kopīgi finansētiem pilotprojektiem.

RS nemaksās, lai aizstātu to, kas darbojas. Viņi maksās, lai:
1. **Atbilstu** — NeTEx/SIRI ir ES mandāts ar termiņiem un sekām
2. **Integrētu** — viņu GPS, plānošanas, maksājumu un pasažieru informācijas sistēmas nesadarbojas
3. **Optimizētu** — 1,097 transportlīdzekļi × pat 2-3% sarakstu uzlabojums = simtiem tūkstošu eiro ietaupījumu gadā

### Pieņēmumu stresa testa rezultāti

| # | Pieņēmums | Spriedums | Stratēģiskā ietekme |
|---|---|---|---|
| 1 | RS maksātu par jaunu CMS | **MODIFY** (Modificēt) | Viņi maksā, lai integrētu un atbilstu, ne lai aizstātu. Pozicionēt kā pārklājumu, ne aizstājēju. |
| 2 | Maza komanda var konkurēt ar $1.3B uzņēmumiem | **REJECT as stated** (Noraidīt kā formulēts) | Nekonkurēt ar funkcijām. Konkurēt ar **atbilstību**: Latvijas konteksts, ES atbilstība, iepirkumu vienkāršība, cena. |
| 3 | AI pievienot patiešām vērtību | **MODIFY** (Modificēt) | Tikai 2 vietās: ierašanās prognoze (Swiftly to pierādīja) un sarakstu optimizācija (Optibus to pierādīja). Viss pārējais ir parastā programmatūra ar godīgu marķēšanu. |
| 4 | Atvērtā koda pozicionēšana uzvar | **MODIFY** (Modificēt) | Cenas pieejamība un auditējamība uzvar. "Atvērtais kods" ir līdzeklis, ne pārdošanas ziņojums. Sākt ar "zemākas izmaksas, nav atkarības, ES-atbilstošs." |
| 5 | Tehniskā pārākuma nozīme iepirkumos | **REJECT** (Noraidīt) | Iepirkuma atbilstība, cena un references ir svarīgākas. Būvēt, lai izturētu katru atzīmi, tad uzvarēt ar cenu + vietējo klātbūtni. |
| 6 | Produkts mērogojams ārpus Rīgas | **MODIFY** (Modificēt) | Mērogojams uz vidēja izmēra CEE aģentūrām (Tallina, Viļņa, Bratislava, Ļubļana) 5-7 gadu ceļā. Ne Rietumeiropa. |

### Trīs lietas, kurām jābūt pareizām

**1. NeTEx/SIRI atbilstība ir ķīļa produkts — ne plānošana, ne AI, ne panelis.**
- Tā ir vienīgā problēma ar ārēju termiņu un juridiskām sekām
- Tā ir pietiekami šaura mazai komandai, lai būvētu labi
- Tā rada pamatu: kad jūs apstrādājat visus RS operacionālos datus atbilstības izvadei, jūs kļūstat par integrācijas slāni. No turienes paplašināties uz plānošanu, analītiku, AI.
- Lielākie spēlētāji (Trapeze, INIT) sapako NeTEx/SIRI €500K+ platformās. Patstāvīgs atbilstības risinājums ir patiešām diferencēts.

**2. Iegūt maksas pilotprojektu pirms pilna produkta būvēšanas.**
- RS nebūs pirmais klients nepārbaudītam produktam. Bet viņi varētu piedalīties kopīgi finansētā pilotprojektā.
- Latvijai ir pieeja ES Strukturālajiem fondiem, CEF (Connecting Europe Facility) transporta digitalizācijai un Horizon Europe.
- Pārredzams, ES kopīgi finansēts pilotprojekts ar publicētiem rezultātiem ir pretstatā aizkulišu darījumiem — kritiski pēc-korupcijas kontekstā.
- Būvēt *kopā ar* RS, ne *priekš* RS. Tas rada produktu, kas patiešām atbilst, referenci un ieņēmumus no pirmās dienas.

**3. Cena zem atvērtā konkursa sliekšņa. Strukturēt kā modulāru SaaS.**
- Virs **€143,000**: RS jāveic pilns ES mēroga konkurss (12-18 mēneši, Trapeze/INIT iesniegs piedāvājumu, jūs zaudēsiet uz referencēm)
- Zem **€42,000**: Vienkāršotas iepirkuma procedūras
- Strukturēt kā neatkarīgus moduļus, katru iepērkamu zem sliekšņiem:

| Modulis | Cena | Iepirkums |
|---|---|---|
| NeTEx/SIRI atbilstības barotne | €2,500/mēnesī (€30K/gadā) | Zem vienkāršotā sliekšņa |
| Reāllaika operāciju panelis | €2,000/mēnesī (€24K/gadā) | Zem vienkāršotā sliekšņa |
| Sarakstu pārvaldība + GTFS | €2,500/mēnesī (€30K/gadā) | Zem vienkāršotā sliekšņa |
| AI plānošanas asistents | €1,500/mēnesī (€18K/gadā) | Zem vienkāršotā sliekšņa |
| **Pilna platforma** | **€8,500/mēnesī (€102K/gadā)** | Zem pilna ES konkursa sliekšņa |

RS var sākt ar vienu moduli un paplašināties. Mēneša norēķini nozīmē, ka viņi var atcelt, ja tas nedarbojas. Pēc-skandāla organizācijai **atgriezeniskums ir funkcija.**

### Pārskatītā izlaides secība

```
0. fāze: PILOTPROJEKTS (1-4 nedēļas)
├── Pieiet RS ar NeTEx/SIRI atbilstības piedāvājumu
├── Piedāvāt ES kopīgi finansētu pilotprojektu (CEF vai Strukturālie fondi)
├── Būvēt NeTEx barotnes ģeneratoru no viņu esošajiem GTFS datiem
├── Piegādāt darboties atbilstības moduli → PIRMĀ REFERENCE
└── Ieņēmumi no pirmās dienas (pat ja subsidēti)

1. fāze: PAPLAŠINĀT (5-12 nedēļas)
├── Pievienot GTFS pārvaldību + sarakstu redaktoru virs atbilstības slāņa
├── Integrācija ar esošajām RS GPS barotnēm
├── Statiskas kartes vizualizācija (MapLibre)
└── RS tagad izmanto platformu katru dienu

2. fāze: PADZIĻINĀT (13-20 nedēļas)
├── Reāllaika izsekošanas pārklājums (patērē GTFS-RT, neaizstāj AVL)
├── Dispečera panelis ar autoparka statusu
├── Vadītāju pārvaldība (GDPR-atbilstoša)
└── RS redz operacionālu vērtību ārpus atbilstības

3. fāze: INTELIĢENCE (21-28 nedēļas)
├── AI ierašanās prognozes (kur Swiftly pierādīja vērtību)
├── AI sarakstu ieteikumi (kur Optibus pierādīja vērtību)
├── Uzlabota analītika un ziņošana
└── RS ir atkarīga no platformas ikdienas operācijām

4. fāze: MĒROGOT (7+ mēnesis)
├── Piedāvāt Tallinai (līdzīgs konteksts, ģeogrāfisks tuvums)
├── Piedāvāt Viļņai, Kauņai
├── Izmantot Baltijas references CEE paplašināšanai
└── 5-7 gadu ceļš uz 10-20 aģentūrām
```

### Konkurences pozīcija pēc šīs analīzes

**Pirms (naivs):** "Mēs būvējam lētāku Trapeze"
**Pēc (stratēģisks):** "Mēs esam vienīgais ES-atbilstības-centrētais integrācijas slānis ar cenām vidēja izmēra CEE tranzīta aģentūrām"

Aizsardzības grāvis nav tehniskā pārākuma. Aizsardzības grāvis ir:
1. **Iepirkuma atbilstība** — modulāras cenas zem konkursu sliekšņiem
2. **Integrācijas pieeja** — uzlabo esošās sistēmas, neaizstāj tās
3. **Ģeogrāfiskais fokuss** — Latvijas/Baltijas/CEE ekspertīze, kas trūkst uzņēmumu pārdevējiem
4. **Atbilstības specializācija** — NeTEx/SIRI kā ieejas punkts, ne pārdomāts
5. **Pārredzamība** — audita celiņi, eksportējami dati, atvērtā koda pamati (pēc-korupcijas pārdošanas punkts)

### 1.5.5 Finanšu ietekme — Ko RS ietaupa

> Balstoties uz apstiprinātiem RS finanšu datiem: €167.4M darbības izmaksas (2023), 115.9M pasažieri (2024), €35.4M biļešu ieņēmumi, 1,097 transportlīdzekļi, ~€155M pilsētas subsīdija. Avoti: RS oficiālie ziņojumi, BNN, Rīgas pašvaldības budžeta dokumenti.

#### A. Tiešie izmaksu ietaupījumi (sarakstu optimizācija)

Optibus gadījumu pētījumi rāda **5-10% autoparka samazinājumu** un **5% samazinājumu vadītāju maiņās** caur AI plānošanu. RS mērogā:

| Rādītājs | RS pašlaik (aprēķināts) | Konservatīvs (2%) | Mērens (5%) | Optimistisks (10%) |
|---|---|---|---|---|
| Autoparka izmantošana (1,097 transportlīdzekļi) | Bāzes līnija | 22 transportlīdzekļi atbrīvoti | 55 transportlīdzekļi atbrīvoti | 110 transportlīdzekļi atbrīvoti |
| Darbības izmaksas uz transportlīdzekli/gadā¹ | ~€152K | — | — | — |
| **Autoparka ietaupījumi/gadā** | — | **€3.3M** | **€8.4M** | **€16.7M** |
| Tukšgaitas km samazinājums² | ~15% bāzes līnija | -1.5% punkti | -3% punkti | -5% punkti |
| **Degvielas ietaupījumi/gadā³** | — | **€680K** | **€1.4M** | **€2.3M** |
| Vadītāju maiņu optimizācija | ~3,500 darbinieki | 1% stundu ietaupījums | 3% stundu ietaupījums | 5% stundu ietaupījums |
| **Darbaspēka izmaksu ietaupījumi/gadā⁴** | — | **€840K** | **€2.5M** | **€4.2M** |

¹ €167.4M ÷ 1,097 transportlīdzekļi = ~€152K/transportlīdzeklis/gadā
² Tipisks Eiropas pilsētas tranzīts tukšgaita: 10-15%. RS aprēķināts 15% no ~80M transportlīdzekļu-km/gadā = 12M tukšgaitas km
³ Par €0.85/km dīzeļdegvielas izmaksām (Eiropas vidējās, 50L/100km × €1.70/L)
⁴ Vidējā Latvijas transporta nozares alga ~€1,685/mēnesī bruto (2024). Ar darba devēja izmaksām: ~€2,000/mēnesī.

| Scenārijs | Kopējie tiešie ietaupījumi/gadā |
|---|---|
| **Konservatīvs (2%)** | **€4.8M** |
| **Mērens (5%)** | **€12.3M** |
| **Optimistisks (10%)** | **€23.2M** |

#### B. Ieņēmumu pieaugums (labāka punktualitāte → vairāk braucēju)

Swiftly gadījumu pētījumi: WMATA sasniedza **6.2% sistēmas mēroga punktualitātes pieaugumu**, Oulu (Somija) **20%+ uzlabojums**. Labāka uzticamība → lielāks pasažieru skaits → vairāk biļešu ieņēmumu.

| Rādītājs | Pašlaik | Ar platformu |
|---|---|---|
| Gada pasažieri | 115.9M | — |
| Vidējā biļetes cena/pasažieris⁵ | €0.31 | — |
| Punktualitātes uzlabojums | Bāzes līnija | +5-15% OTP |
| Pasažieru skaita pieaugums no labāka servisa⁶ | — | +1-3% |
| **Papildu pasažieri/gadā** | — | **1.2M - 3.5M** |
| **Papildu biļešu ieņēmumi/gadā** | — | **€370K - €1.1M** |
| **Papildu subsīdijas pamatojums⁷** | — | **€1.7M - €5.0M** |

⁵ €35.4M biļešu ieņēmumi ÷ 115.9M pasažieri = €0.31/pasažieris (zems dēļ mēneša biļetēm, studentu/senioru atlaidēm)
⁶ Nozares prakses noteikums: 1% OTP uzlabojums ≈ 0.3-0.5% pasažieru skaita pieaugums
⁷ RS saņem €155M pilsētas subsīdiju. Augstāks pasažieru skaits stiprina argumentu par uzturētu/palielinātu subsīdiju pie ~€1.34/pasažieris

#### C. Izvairītās izmaksas (ko RS nav jāiztērē)

| Izmaksu kategorija | Uzņēmuma alternatīva | Mūsu platforma | **RS ietaupa** |
|---|---|---|---|
| CAD/AVL + plānošanas komplekts (Trapeze/INIT) | €500K-2M iestatīšana + €100-400K/gadā | €102K/gadā (pilna platforma) | **€400K-1.9M 1. gadā** |
| Gada apkope (uzņēmums) | €100-400K/gadā pastāvīgi | Iekļauts SaaS | **€100-300K/gadā** |
| NeTEx/SIRI atbilstības konsultants | €50-150K vienreizējs + pastāvīgi | Iebūvēts | **€50-150K** |
| Manuāla GTFS barotnes uzturēšana⁸ | ~1 FTE = €24K/gadā | Automatizēts | **€24K/gadā** |
| Dispečera procesa neefektivitāte⁹ | ~2 FTE ekvivalenta izšķērdēšana | Racionalizēts | **€48K/gadā** |
| IT infrastruktūra (uzņēmuma serveri) | €30-80K/gadā | Mākoņa SaaS | **€30-80K/gadā** |

⁸ RS pašlaik uztur GTFS barotni manuāli. Automatizācija ietaupa ~1 pilna laika ekvivalentu.
⁹ Aprēķināts: dispečeri manuāli savieno atvienotas sistēmas, kopē datus starp rīkiem.

| Kategorija | 1. gada ietaupījumi | Gada pastāvīgie |
|---|---|---|
| **Izvairīta uzņēmuma programmatūra** | **€400K - €1.9M** | **€100-300K** |
| **Izvairītas atbilstības izmaksas** | **€50-150K** | **€20-50K** |
| **Automatizēti manuālie procesi** | **€72-102K** | **€72-102K** |

#### D. ES finansējuma iespējas (pieejamais kapitāls)

| Fonds | Latvijas piešķīrums (2021-2027) | Atbilstība | Reālistisks RS |
|---|---|---|---|
| **CEF Transport** | €25.8B ES mērogā (Latvija saņēma €928M Rail Baltica) | ITS digitalizācija atbilst | €200K-1M uz projekta pieteikumu |
| **ES Strukturālie fondi** | €5.4B kopā Latvijas piešķīrums | Transports + digitālā transformācija | €500K-2M konkurētspējīgs piedāvājums |
| **Atveseļošanas un noturības mehānisms** | €365.3M Latvija digitālā transformācija | Viedā pilsēta / publiskie pakalpojumi | €100K-500K |
| **Horizon Europe** | Atvērti konkursi | Inovācija transportā | €200K-1M konsorcijs |
| **ERAF (Reģionālā attīstība)** | Daļa no €5.4B strukturālajiem | Pilsētas ilgtspējīgs transports | €300K-1M |

**Reālistisks ES kopīgā finansējuma scenārijs:**
- Pilotprojekts: €100-300K no CEF/Strukturālajiem fondiem (sedz 50-70% attīstības)
- RS kopīgi finansē atlikušos 30-50%
- RS efektīvās izmaksas pilotam: **€50-150K** (pret €500K-2M uzņēmuma alternatīvai)

#### E. Izvairīts atbilstības risks

| Risks | Sekas | Varbūtība bez platformas | Finanšu iedarbība |
|---|---|---|---|
| NeTEx/SIRI neatbilstība | ES pārkāpuma procedūras | Vidējs-Augsts | €5K-50K/dienā soda maksājumi |
| GDPR pārkāpums (vadītāju GPS dati) | DPA sods | Vidējs | Līdz 4% no ieņēmumiem = **€7.3M** |
| Pazemināta ES finansējuma atbilstība | Samazināta konkurētspēja transporta dotācijām | Augsts | **€500K-5M** zaudētā finansējumā |
| Pasažieru informācijas kvalitātes plaisa | Braucēji pāriet uz automašīnām, pasažieru skaits krītas | Vidējs | **€1-3M/gadā** zaudētās biļetes + subsīdija |

#### F. Kopējā finanšu ietekmes kopsavilkums

| Kategorija | Konservatīvs/gadā | Mērens/gadā | Optimistisks/gadā |
|---|---|---|---|
| Sarakstu optimizācijas ietaupījumi | €4.8M | €12.3M | €23.2M |
| Ieņēmumu pieaugums (pasažieru skaits) | €2.1M | €3.5M | €6.1M |
| Izvairītas uzņēmuma izmaksas | €572K | €1.1M | €2.3M |
| ES kopīgais finansējums (amortizēts) | €50K | €150K | €300K |
| Atbilstības riska samazinājums | €100K | €500K | €2M |
| **KOPĒJĀ GADA VĒRTĪBA** | **€7.6M** | **€17.6M** | **€33.9M** |
| **Platformas izmaksas** | **€102K/gadā** | **€102K/gadā** | **€102K/gadā** |
| **ROI** | **74:1** | **172:1** | **332:1** |

> **Piedāvājums vienā rindā:** Par €102K/gadā (0.06% no darbības budžeta), RS iegūst €7.6-33.9M ietaupījumos, ieņēmumu pieaugumā un riska samazināšanā — **74x-332x atdeve no ieguldījuma.**

**Svarīgas atrunas:**
- Konservatīvais scenārijs pieņem tikai 2% optimizācijas uzlabojumu (Optibus sasniedz 5-10%)
- Ieņēmumu pieaugums ir atkarīgs no biļešu politikas un subsīdijas struktūras
- ES finansējums prasa konkurētspējīgus pieteikumus (nav garantēts)
- Pilni ietaupījumi prasa 2.-3. fāzes funkcijas (sarakstu optimizācija, AI prognozes)
- Sarakstu optimizācijas ietaupījumi pieņem, ka RS jau nav līdzvērtīgas programmatūras

## 2. Pētniecības rezultāti

### 2.1 Rīgas Satiksme — pašreizējais stāvoklis

| Rādītājs | Vērtība |
|---|---|
| Kopējais parks | 1 097 transportlīdzekļi (476 autobusi, 354 trolejbusi, 267 tramvaji) |
| Autobusu maršruti | ~60 maršruti |
| GTFS plūsma | **Pieejama**: `saraksti.rigassatiksme.lv/gtfs.zip` |
| SIRI API | **Pieejams**: `saraksti.rigassatiksme.lv/siri-stop-departures.php?stopid=STOPID` |
| Esošās tehnoloģijas | GPS izsekošana, APC, e-talonu maksājumi, WiFi, Papercast e-ink displēji |
| Iepirkums | Plānoti 100 jauni trolejbusi + 24 jauni tramvaji |
| Infrastruktūra | Tramvaja līnijas Nr. 7 pagarinājums tiks atklāts 2026. gada maijā |
| Regulējums | Sabiedriskā transporta pakalpojumu likums (2007) + ES PSO regula |

**Kritiski svarīgs atklājums:** Rīgas Satiksme jau izmanto GPS izsekošanu un publicē GTFS plūsmas. Šis CMS ir **integrācijas un pārvaldības slānis** virs esošās infrastruktūras, nevis tās aizstājējs.

### 2.2 Konkurences ainava

| Sistēma | Tips | Stiprā puse | Trūkums |
|---|---|---|---|
| **Optibus** ($1.3B) | Scheduling SaaS | Labākā AI/ML plānošana, GenAI noteikumi | Nav dispečerizācijas, nav izsekošanas |
| **Swiftly** | Analytics SaaS | Labākās prognozes, GTFS-RT līderis | Tikai analītika, nav pārvaldības |
| **Trapeze** | Pilna CAD/AVL | Pilnīga dispečerizācijas sistēma | Mantota UI, dārga |
| **INIT** | Pilna sistēma | Labākā apkalpes/tarifu pārvaldība | Ļoti dārga |
| **Clever Devices** | CAD/AVL | Traucējumu pārvaldība | Orientēta uz Ziemeļameriku |
| **OneBusAway** | Open-source | Pasažieriem domāta, white-label | Nav biroja pārvaldības |
| **OpenTripPlanner** | Open-source | Maršruta plānošana, NeTEx atbalsts | Tikai API, nav dispečerizācijas |

**Tirgus spraga, kuru mēs aizpildām:** Neeksistē pieejama, integrēta, ES atbilstoša (NeTEx/SIRI) sabiedriskā transporta pārvaldības platforma vidēja lieluma Eiropas aģentūrām (50-500 transportlīdzekļi). Komerciālie risinājumi maksā $500-2,000+/mēnesī. Open-source rīki ir sadrumstaloti.

### 2.2.1 Konkurences priekšrocību sintēze — ko pārņemam no katra

Stratēģija nav pārspēt $1.3B kompānijas. Tā ir **izvēlēties labākās idejas no katra konkurenta** un piegādāt tās kā vienotu, pieejamu, Rīgai pielāgotu platformu.

| No konkurenta | Ko pārņemam | Kā to īstenojam |
|---|---|---|
| **Optibus** — GenAI noteikumi | Dabiskās valodas plānošanas vaicājumi | Claude AI palīgs saprot "parādi visus 22. maršruta reisus, kas kavējas darba dienās" — nav vajadzīgs SQL. 3. fāze. |
| **Optibus** — AI grafiku analīze | Salīdzinošā analīze "Kas mainījās?" | AI rīks salīdzina divas grafiku versijas, izceļ atšķirības, novērtē ietekmi. 3. fāze. |
| **Swiftly** — Vairāku avotu GPS apvienošana | Patērējam visas pieejamas RS datu plūsmas | Uztver GTFS-RT transportlīdzekļu pozīcijas + SIRI API + jebkurus papildu AVL datus, ko RS atklāj. Vienota karte. 2. fāze. |
| **Swiftly** — Pārklājuma pieeja | Uzlabot, nevis aizstāt esošās sistēmas | CMS darbojas virs RS esošās GPS, e-talonu un GTFS infrastruktūras. Nulles traucējumi pašreizējām darbībām. |
| **Trapeze** — IDS lēmumu atbalsts | AI atbalstīta incidentu reakcija | Kad konstatēta kavēšanās, AI iesaka: pārvirzīt, aizkavēt, īsināt vai ekspresmaršrutu. Dispečers apstiprina ar vienu klikšķi. 3. fāze. |
| **Trapeze** — NeTEx/SIRI native | ES atbilstība no arhitektūras | NeTEx eksports + SIRI plūsmas ģenerēšana iebūvēta datu modelī, nevis pievienota papildus. 3. fāze. |
| **INIT** — Apkalpes pārvaldība | Vadītāju maiņu piešķiršana ar GDPR | Pseidonimizēti vadītāju ieraksti, maiņu kalendārs, transportlīdzekļu piešķiršana. Atbilst Latvijas Datu aizsardzības likumam. 2. fāze. |
| **INIT** — Integrēta plānošana | Grafiks → dispečerizācija → izsekošana | Vienota datu plūsma: izveidot grafiku → piešķirt transportlīdzekļus → izsekot izpildi → ziņot par atbilstību. Nav datu silosi. |
| **Clever Devices** — Traucējumu pārvaldība | Pakalpojumu brīdinājumu kaskādes sistēma | Izveidot brīdinājumu → automātiski atjaunina GTFS-RT plūsmu → paziņo Moovit/Google Maps → izceļ dispečera pultī. 2. fāze. |
| **OneBusAway** — Atvērto datu ētika | GTFS/GTFS-RT/NeTEx plūsmas publicētas | Katra datu izmaiņa automātiski ģenerē atjauninātas plūsmas. Moovit, Google Maps, Transit App vienmēr aktuāli. |
| **OpenTripPlanner** — Maršruta plānošana | Saite uz esošo RS maršruta plānotāju | Nepārbūvējam maršruta plānošanu. Saite uz `saraksti.rigassatiksme.lv` un datu pieejamība OTP integrācijai. |

### 2.2.2 Kāpēc Rīgas Satiksme to iegādātos

**Pircēja izpratne:**
- Pašvaldības uzņēmums, pēc korupcijas skandāla — **iepirkumu pārredzamība** ir svarīga
- €300M parāds — **izmaksu jutīgums** ir ekstrēms, bet viņi joprojām tērē modernizācijai (100 jauni trolejbusi, 24 tramvaji)
- 3 500 darbinieki — lēmumi tiek pieņemti caur komitejām, nevis vienu pircēju
- Jau ir darbojošās pamatsistēmas — viņiem vajag **uzlabojumus, nevis revolūciju**
- ES atvērto datu priekšgalā — viņi rūpējas par **standartu atbilstību**

**Piedāvājums RS:**

| RS sāpju punkts | Kā mēs to risināt | Konkurenti nevar, jo |
|---|---|---|
| **Nav vienotas darbību skatījuma** — GPS, grafiki, flotes dati atsevišķās sistēmās | Viena ekrāna dispečera pults, apvienojot karti, grafika atbilstību, flotes statusu, brīdinājumus | Optibus/Swiftly sedz tikai fragmentus; Trapeze/INIT maksā €500K+ |
| **GTFS plūsmas uzturēšana ir manuāla** | Auto-ģenerēta GTFS/GTFS-RT no grafika redaktora. Rediģēt grafiku → plūsmas atjauninās uzreiz | Open-source rīki prasa manuālu eksportu. Komercrīki ir slēgti. |
| **ES atbilstības spiediens** (NeTEx/SIRI mandāts) | Natīvs NeTEx eksports + SIRI plūsma no tā paša datu modeļa. Nav vajadzīgi konversijas rīki. | Optibus neatbalsta NeTEx. Swiftly ir tikai GTFS. |
| **Jaunās flotes integrācija** (100 trolejbusi, 24 tramvaji, ūdeņraža transportlīdzekļi) | Transportlīdzekļu pārvaldība ar tipam specifisko izsekošanu (akumulatora līmenis elektriskiem, ūdeņradis kurināmā šūnām) | Mantotās sistēmas veidotas tikai dīzeļa autobusiem |
| **Izmaksas** — uzņēmumu sistēmas piedāvā €100K-500K+ | SaaS par **€500-1,500/mēnesī** (vai pašmitināts par vēl mazāk). Nav aparatūras. Nav vairāku gadu bloķēšanas. | Trapeze, INIT, Clever Devices prasa uzņēmumu līgumus |
| **Latviešu valoda + vietējais konteksts** | Pilnīgi LV/EN divvalodu UI. Saprot Rīgas ģeogrāfiju, RS maršruta numerāciju, vietējos noteikumus. | Visi konkurenti ir angliski pirmie ar vispārīgu lokalizāciju |
| **Pēc korupcijas pārredzamība** | Pilnīga audita pēda. Katra izmaiņa reģistrēta ar lietotāju, laika zīmogu, iemeslu. Open-source kodols. | Īpašumtiesību sistēmas ir melnās kastes |

### 2.2.3 Uzticamības arhitektūra

Sabiedriskā transporta aģentūrai uzticamība nav funkcija — tā ir viss produkts. Dispečeri nevar atļauties, ka sistēma pārtrūkst maksimālās slodzes laikā.

**1. līmenis: Pamata uzticamība (1. fāze)**
| Pasākums | Īstenošana |
|---|---|
| **Bezsaistes dispečera skats** | Service worker kešatmiņā pēdējās zināmās transportlīdzekļu pozīcijas + grafiks. Karte darbojas bezsaistē ar kešotām mozaīkām. |
| **Nulles dīkstāves izvietojumi** | Vercel priekšskatījums → ražošanas pārnese. Nav uzturēšanas logu. |
| **Automātiskas datu rezerves kopijas** | Supabase ikdienas rezerves kopijas + tūlītējas atjaunošanas punkts (iekļauts Pro plānā) |
| **Ievades validācija katrā robežā** | Zod shēmas uz tRPC, GTFS validācija importējot, dezinficēti AI izvadi |
| **Veselības uzraudzība** | `/api/health` galapunkts + Uptime Robot (bezmaksas) → Slack/e-pasta brīdinājumi |

**2. līmenis: Darbības uzticamība (2. fāze)**
| Pasākums | Īstenošana |
|---|---|
| **Novecojušu datu noteikšana** | Transportlīdzekļu marķieri kļūst pelēki pēc 60s bez atjauninājuma. Dispečers redz "pēdējo reizi redzēts" laika zīmogu. |
| **Pakāpeniska degradācija** | Ja Redis nedarbojas → pāriet uz aptauju. Ja Claude API nedarbojas → paslēpt AI paneli, dispečerizācija darbojas normāli. |
| **Savienojuma atjaunošana** | SSE auto-atkārtots savienojums ar eksponenciālo atteikšanos. Nav pazaudētu pozīciju. |
| **Ātruma ierobežošana** | Uz lietotāju un uz IP ātruma ierobežojumi visos galapunktos. GPS uzņemšana ierobežota uz ierīci. |
| **Audita pēda** | Katra datu mutācija reģistrēta: kas, kas, kad, iepriekšējā vērtība. Nemainīga žurnāla tabula. |

**3. līmenis: Uzņēmuma uzticamība (3. fāze)**
| Pasākums | Īstenošana |
|---|---|
| **SLA informācijas panelis** | Iekšējā metriku lapa, rādot darbības laiku, atbildes laikus, plūsmas svaigumu |
| **Anomāliju noteikšana** | AI atzīmē neparastus modeļus: "22. maršrutam nav ziņojošu transportlīdzekļu — iespējama plūsmas problēma" |
| **Datu integritātes pārbaudes** | Nakts darbs validē GTFS izvadi pret MobilityData validatoru |
| **Katastrofas atjaunošanas plāns** | Dokumentēts RTO < 1 stunda. Datubāzes atjaunošana + atkārtota izvietošana no git. |
| **Iespiešanās testēšana** | Pirmslaišanas drošības audits SSE autentifikācijai, GPS uzņemšanai, admin galapunktiem |

### 2.2.4 Konkurences pozicionēšanas kopsavilkums

```
                        PIEEJAMS ←─────────────────→ DĀRGS
                            │                              │
              SADRUMSTALOTS │    ★ MŪSU POZĪCIJA          │
              (open-source) │    Vienots + Pieejams       │
                   │        │    + ES atbilstošs          │
                   ▼        │                              │
    ┌─────────────────────┐ │                              │
    │ OTP + OneBusAway    │ │                              │
    │ + TransitClock      │ │                              │
    │ (Bezmaksas, bet 3   │ │                              │
    │  rīki, nav dispatch,│ │                              │
    │  nav UI)            │ │                              │
    └─────────────────────┘ │                              │
                            │                              │
    ┌──────────────┐        │         ┌────────────────┐   │
    │ Swiftly      │        │         │ Trapeze        │   │
    │ (Tikai       │        │         │ (Pilna CAD/AVL │   │
    │  analītika)  │        │         │  Mantota UI)   │   │
    └──────────────┘        │         └────────────────┘   │
    ┌──────────────┐        │         ┌────────────────┐   │
    │ Optibus      │        │         │ INIT           │   │
    │ (Tikai       │        │         │ (Pilna sistēma │   │
    │  plānošana)  │        │         │  €500K+)       │   │
    └──────────────┘        │         └────────────────┘   │
    │                       │                              │
              DAĻĒJS ────────┼──────────────── PILNS        │
              (viena         │              (pilnas ops)    │
               funkcija)     │                              │
```

**Mūsu priekšrocība:** Vienīgā platforma, kas vienlaikus ir:
1. **Pieejama** (€500-1,500/mēnesī pret €100K+ uzņēmumiem)
2. **Pilnīga** (grafiks + dispečerizācija + izsekošana + AI vienā rīkā)
3. **ES natīva** (NeTEx/SIRI no pirmās dienas, nevis konvertēta no GTFS)
4. **Rīgai specifiska** (latviešu UI, RS plūsmas integrācija, vietējo normatīvo aktu zināšanas)
5. **Pārredzama** (atvērta audita pēda, eksportējami dati, nav piegādātāja bloķēšanas)

### 2.3 RedTeam galvenie atklājumi

Identificētas 18 ievainojamības. 5 nozīmīgākās pēc smaguma pakāpes:

| # | Atklājums | Smagums | Mazināšana |
|---|---|---|---|
| 1 | 20 tehnoloģijas / 2 valodas ir KRITISKA sarežģītība | KRITISKS | Samazināts līdz 12 tehnoloģijas / 1 valoda |
| 2 | GDPR nav arhitektūrā (GPS = personas dati ES) | KRITISKS | Privātums pēc dizaina no 1. dienas |
| 3 | SSE autentifikācijas plaisa (EventSource nav pielāgotu galveņu) | KRITISKS | Cookie autentifikācija ar httpOnly |
| 4 | Apjoms ir 6 mēnešu projekts, nevis 4 nedēļas | KRITISKS | Pakāpeniska piegāde ar 8 nedēļu cikliem |
| 5 | AI aģents var atrisināt nepareizu problēmu fiksētiem maršrutiem | AUGSTS | Atlikt uz 2. fāzi, validēt ar dispečeriem |

### 2.4 Pirmā principa spriedums

| Pieņēmums | Spriedums |
|---|---|
| Vajadzīgs pielāgots CMS | **MODIFY** (Modificēt) — būvēt integrācijas informācijas paneli, nevis pilnu CMS |
| Next.js ir pareizs | **KEEP** (Saglabāt) — padome un tehnoloģiju pētījums apstiprina, ka App Router ir gatavs ražošanai |
| PostGIS vajadzīgs | **MODIFY** (Modificēt) — sākt ar vienkāršu PostGIS uz Supabase, nevis TimescaleDB |
| AI aģents būtisks | **REJECT for MVP** (Noraidīt MVP) — pievienot 2. fāzē pēc dispečeru validācijas |
| Pielāgots real-time | **MODIFY** (Modificēt) — vispirms patērēt esošās GTFS-RT/AVL plūsmas |
| GTFS atbilstība | **KEEP** (Saglabāt) — Rīga publicē GTFS, ES to nosaka |
| $50-150/mēnesī | **ACHIEVABLE** (Sasniedzams) — ar vienkāršotu steku ($31-47 1. fāze) |
| OR-Tools | **REJECT** (Noraidīt) — fiksētiem maršrutiem nav vajadzīgs VRP risinātājs |
| TimescaleDB | **REJECT** (Noraidīt) — 20 raksti/sek ir triviāli standarta PostgreSQL |

---

## 3. Pārskatītā arhitektūra

### 3.1 Sistēmas arhitektūras diagramma

```
┌──────────────────────────────────────────────────────────────────┐
│                        KLIENTI                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────────┐ │
│  │  Dispečera   │  │   Admin     │  │  Publiskais grafika      │ │
│  │  panelis     │  │   portāls   │  │  skatītājs (Nākotne)     │ │
│  └──────┬───────┘  └──────┬──────┘  └───────────┬──────────────┘ │
│         │                 │                      │                │
└─────────┼─────────────────┼──────────────────────┼────────────────┘
          │                 │                      │
          ▼                 ▼                      ▼
┌──────────────────────────────────────────────────────────────────┐
│              NEXT.JS 15 APP ROUTER (MODULĀRS MONOLĪTS)           │
│                                                                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │ Maršruti │ │ Grafiki  │ │  Flote   │ │  GTFS    │            │
│  │  modulis │ │  modulis │ │  modulis │ │  modulis │            │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │Izsekošana│ │    AI    │ │   Auth   │ │ Ziņojumi │            │
│  │  modulis │ │  modulis │ │  modulis │ │  modulis │            │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘            │
│                                                                   │
│  ┌────────────────────────────────────────────────────┐          │
│  │              tRPC v11 API slānis                    │          │
│  │  (Tipu drošas procedūras + SSE abonēšana)           │          │
│  └────────────────────────────────────────────────────┘          │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  Drizzle ORM │  │  Auth.js v5  │  │  MapLibre    │           │
│  │  (PostGIS)   │  │  (RBAC)      │  │  (Klients)   │           │
│  └──────┬───────┘  └──────────────┘  └──────────────┘           │
└─────────┼────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────┐
│                     DATU SLĀNIS                                   │
│                                                                   │
│  ┌─────────────────────────────┐  ┌────────────────────────────┐ │
│  │    Supabase PostgreSQL      │  │    Upstash Redis           │ │
│  │    + PostGIS paplašinājums  │  │    (tikai 2. fāze+)        │ │
│  │                             │  │    - SSE izplatīšana        │ │
│  │    - GTFS saskaņota shēma   │  │    - Pozīciju kešatmiņa     │ │
│  │    - Transportlīdzekļu poz. │  │                             │ │
│  │    - Telpisko indeksu       │  └────────────────────────────┘ │
│  │    - Lietotāju/auth dati    │                                 │
│  └─────────────────────────────┘                                 │
│                                                                   │
│  ┌─────────────────────────────┐  ┌────────────────────────────┐ │
│  │  Ārējie datu avoti          │  │  Claude API (2. fāze+)     │ │
│  │  - RS GTFS plūsma           │  │  - Sonnet 4.5 (primārais)  │ │
│  │  - SIRI pieturvietu atiet   │  │  - Haiku 4.5 (vienkāršs)   │ │
│  │  - GPS aparatūra (AVL)      │  │  - Tikai konsultatīvais    │ │
│  └─────────────────────────────┘  └────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 Moduļu robežas

```
src/
├── app/                          # Next.js App Router lapas
│   ├── (auth)/                   # Auth lapas (login, register)
│   ├── (dashboard)/              # Aizsargāts informācijas paneļa izkārtojums
│   │   ├── routes/               # Maršruta pārvaldības lapas
│   │   ├── schedules/            # Grafika/sarakstu lapas
│   │   ├── stops/                # Pieturu pārvaldības lapas
│   │   ├── fleet/                # Transportlīdzekļu pārvaldība (2. fāze)
│   │   ├── drivers/              # Vadītāju pārvaldība (2. fāze)
│   │   ├── tracking/             # Tiešraides kartes panelis (2. fāze)
│   │   ├── reports/              # Analītika (2. fāze)
│   │   └── assistant/            # AI palīgs (3. fāze)
│   ├── api/                      # tRPC + GTFS galapunkti
│   │   ├── trpc/[trpc]/          # tRPC apstrādātājs
│   │   ├── gtfs/                 # GTFS imports/eksports
│   │   └── positions/            # GPS uzņemšana (2. fāze)
│   └── layout.tsx                # Saknes izkārtojums
├── server/                       # Servera puses loģika
│   ├── trpc/                     # tRPC maršrutētāji
│   │   ├── routes.ts
│   │   ├── schedules.ts
│   │   ├── stops.ts
│   │   ├── fleet.ts              # 2. fāze
│   │   ├── drivers.ts            # 2. fāze
│   │   ├── tracking.ts           # 2. fāze
│   │   └── assistant.ts          # 3. fāze
│   ├── gtfs/                     # GTFS import/eksport loģika
│   │   ├── importer.ts
│   │   ├── exporter.ts
│   │   └── validator.ts
│   ├── tracking/                 # Real-time izsekošana (2. fāze)
│   │   ├── ingestion.ts
│   │   ├── broadcast.ts
│   │   └── geofence.ts
│   └── ai/                       # AI aģents (3. fāze)
│       ├── agent.ts
│       ├── tools.ts
│       └── prompts.ts
├── components/                   # React komponenti
│   ├── map/                      # MapLibre komponenti
│   ├── tables/                   # Datu tabulas (Tanstack)
│   ├── forms/                    # Formu komponenti
│   └── ui/                       # Shadcn/ui komponenti
├── db/                           # Drizzle shēma + migrācijas
│   ├── schema/
│   │   ├── gtfs.ts               # GTFS saskaņotas tabulas
│   │   ├── fleet.ts              # Transportlīdzekļu/vadītāju tabulas
│   │   ├── tracking.ts           # Pozīciju vēsture
│   │   └── auth.ts               # Lietotāju/lomu tabulas
│   └── migrations/
├── lib/                          # Koplietotie rīki
│   ├── gtfs/                     # GTFS parsēšanas rīki
│   ├── geo/                      # Ģeotelpisko rīki (Turf.js)
│   └── i18n/                     # LV/EN tulkojumi
└── public/                       # Statiskie resursi
    └── map-styles/               # MapLibre stila JSON
```

---

## 4. Tehnoloģiju steks

### 4.1 Galīgais steks (12 tehnoloģijas, 1 valoda)

| Slānis | Tehnoloģija | Versija | Pamatojums |
|---|---|---|---|
| **Valoda** | TypeScript | 5.x | Viena valoda novērš Python/FastAPI sarežģītību |
| **Ietvars** | Next.js | 15.x | Ražošanai gatavs App Router. Server Components CRUD lapām. |
| **UI komponenti** | Shadcn/ui + Tailwind v4 | Jaunākā | CSS mainīgo tēmas aģentūras zīmolam. Nav ietvara bloķēšanas. |
| **Datu tabulas** | TanStack Table | v8 | Servera puses meklēšana, filtrēšana, lappušu numerācija maršruta/grafika sarakstiem |
| **API** | tRPC v11 | 11.x | Tipu droša API + SSE abonēšana real-time (2. fāze) |
| **ORM** | Drizzle ORM | Jaunākā | **Natīvs PostGIS point tipa atbalsts.** Labāks nekā Prisma telpiskajam. |
| **Datubāze** | PostgreSQL + PostGIS | 16+ | Supabase pārvaldīta. GTFS saskaņota shēma ar telpiskajiem indeksiem. |
| **Kartes** | MapLibre GL JS | 4.x | Open-source Mapbox atdalījums. Pašmitinātas mozaīkas caur OpenFreeMap. $0/mēnesī. |
| **Auth** | Auth.js v5 | 5.x | Pašmitināts RBAC. Datu suverenitāte pašvaldības valdībai. |
| **Kešatmiņa** | Upstash Redis | Serverless | Tikai 2. fāze+. SSE izplatīšana + pozīciju kešatmiņa. Bezmaksas līmenis sākumam. |
| **AI** | Claude API (Sonnet 4.5) | Jaunākā | Tikai 2. fāze+. Konsultatīvais režīms ar izdevumu ierobežojumiem. |
| **Mitināšana** | Railway / Fly.io | - | $5-20/mēnesī Next.js. Docker izvietošana. |

### 4.2 Kas tika skaidri noņemts un kāpēc

| Noņemts | Kāpēc |
|---|---|
| Python / FastAPI | Vienas valodas politika. Novērš 2. ekosistēmu. |
| Google OR-Tools | Fiksētiem autobusu maršrutiem nav vajadzīgs VRP risinātājs. Izmantot OSRM apbraucamiem ceļiem. |
| TimescaleDB | 20 raksti/sek ir triviāli. Standarta PostgreSQL ar particionēšanu pietiek. |
| Prisma ORM | Nav natīva PostGIS atbalsta. Drizzle ir iebūvēti ģeometrijas tipi. |
| Mapbox GL JS | Piegādātāja bloķēšana + izmaksu risks. MapLibre ir API saderīgs un bezmaksas. |
| Redis (1. fāze) | Iekš-procesa pub/sub apstrādā 100 transportlīdzekļus vienā instancē. |
| Claude API (1. fāze) | Vispirms izveidot labu UI. Validēt dispečeru vajadzības pirms AI pievienošanas. |
| Monorepo rīki | Viens repo ar tīru mapes struktūru. 2-3 dev komandai nav vajadzīgs Turborepo. |

---

## 5. Datubāzes shēma

### 5.1 GTFS saskaņotā pamata shēma (Drizzle ORM)

```typescript
// db/schema/gtfs.ts — Pamata GTFS tabulas

// Aģentūras (transporta operatori)
export const agencies = pgTable('agencies', {
  id: text('id').primaryKey(),                    // GTFS agency_id
  name: text('name').notNull(),                   // "Rīgas Satiksme"
  url: text('url'),
  timezone: text('timezone').default('Europe/Riga'),
  lang: text('lang').default('lv'),
  phone: text('phone'),
});

// Maršruti (autobusu līnijas)
export const routes = pgTable('routes', {
  id: text('id').primaryKey(),                    // GTFS route_id
  agencyId: text('agency_id').references(() => agencies.id),
  shortName: text('short_name'),                  // "22"
  longName: text('long_name'),                    // "Jugla - Centrs"
  type: integer('type').default(3),               // 3 = Autobuss
  color: text('color'),                           // "FF0000"
  textColor: text('text_color'),
  description: text('description'),
  // Iekšējie lauki (ārpus GTFS)
  isActive: boolean('is_active').default(true),
  createdAt: timestamp('created_at').defaultNow(),
  updatedAt: timestamp('updated_at').defaultNow(),
});

// Pieturas (autobusu pieturas ar ģeolokāciju)
export const stops = pgTable('stops', {
  id: text('id').primaryKey(),                    // GTFS stop_id
  name: text('name').notNull(),
  nameLv: text('name_lv'),                        // Latviešu nosaukums
  lat: doublePrecision('lat').notNull(),
  lon: doublePrecision('lon').notNull(),
  // PostGIS ģeometrija telpiskajiem vaicājumiem
  geom: geometry('geom', { type: 'point', srid: 4326 }),
  code: text('code'),                             // Pieturas kods pasažieriem
  locationType: integer('location_type').default(0),
  wheelchairBoarding: integer('wheelchair_boarding').default(0),
  // Iekšējie lauki
  shelter: boolean('shelter').default(false),
  bench: boolean('bench').default(false),
  display: boolean('electronic_display').default(false),
}, (table) => ({
  geomIdx: index('stops_geom_idx').using('gist', table.geom),
  latLonIdx: index('stops_lat_lon_idx').on(table.lat, table.lon),
}));

// Kalendārs (pakalpojumu modeļi)
export const calendar = pgTable('calendar', {
  serviceId: text('service_id').primaryKey(),
  monday: boolean('monday').notNull(),
  tuesday: boolean('tuesday').notNull(),
  wednesday: boolean('wednesday').notNull(),
  thursday: boolean('thursday').notNull(),
  friday: boolean('friday').notNull(),
  saturday: boolean('saturday').notNull(),
  sunday: boolean('sunday').notNull(),
  startDate: text('start_date').notNull(),        // YYYYMMDD formāts
  endDate: text('end_date').notNull(),
});

// Kalendāra datumi (izņēmumi: svētku dienas, īpaši notikumi)
export const calendarDates = pgTable('calendar_dates', {
  serviceId: text('service_id').references(() => calendar.serviceId),
  date: text('date').notNull(),                   // YYYYMMDD
  exceptionType: integer('exception_type').notNull(), // 1=pievienots, 2=noņemts
}, (table) => ({
  pk: primaryKey({ columns: [table.serviceId, table.date] }),
}));

// Reisi (konkrēts brauciens pa maršrutu)
export const trips = pgTable('trips', {
  id: text('id').primaryKey(),                    // GTFS trip_id
  routeId: text('route_id').references(() => routes.id),
  serviceId: text('service_id').references(() => calendar.serviceId),
  headsign: text('headsign'),                     // "Centrs"
  directionId: integer('direction_id'),           // 0 vai 1
  blockId: text('block_id'),                      // Transportlīdzekļa bloks
  shapeId: text('shape_id'),
  wheelchairAccessible: integer('wheelchair_accessible').default(0),
});

// Pieturu laiki (faktiskie grafika dati)
export const stopTimes = pgTable('stop_times', {
  tripId: text('trip_id').references(() => trips.id),
  stopId: text('stop_id').references(() => stops.id),
  arrivalTime: text('arrival_time').notNull(),    // HH:MM:SS (var pārsniegt 24:00)
  departureTime: text('departure_time').notNull(),
  stopSequence: integer('stop_sequence').notNull(),
  pickupType: integer('pickup_type').default(0),
  dropOffType: integer('drop_off_type').default(0),
}, (table) => ({
  pk: primaryKey({ columns: [table.tripId, table.stopSequence] }),
  tripIdx: index('stop_times_trip_idx').on(table.tripId),
  stopIdx: index('stop_times_stop_idx').on(table.stopId),
}));

// Formas (maršruta ģeometrija kā kodēti polilīnijas)
export const shapes = pgTable('shapes', {
  id: text('id').primaryKey(),                    // GTFS shape_id
  encodedPolyline: text('encoded_polyline'),      // Google kodēta polilīnija
  geom: geometry('geom', { type: 'linestring', srid: 4326 }),
}, (table) => ({
  geomIdx: index('shapes_geom_idx').using('gist', table.geom),
}));
```

### 5.2 Flotes un darbību shēma (2. fāze)

```typescript
// db/schema/fleet.ts

export const vehicles = pgTable('vehicles', {
  id: text('id').primaryKey(),
  registrationNumber: text('registration_number').unique(),
  type: text('type').notNull(),                   // 'bus', 'trolleybus', 'tram'
  make: text('make'),
  model: text('model'),
  year: integer('year'),
  capacity: integer('capacity'),
  isAccessible: boolean('is_accessible').default(false),
  status: text('status').default('active'),       // active, maintenance, retired
  gpsDeviceId: text('gps_device_id'),
});

export const drivers = pgTable('drivers', {
  id: text('id').primaryKey(),
  // GDPR: pseidonimizēts identifikators, nevis īstais vārds
  employeeCode: text('employee_code').unique().notNull(),
  licenseCategory: text('license_category'),
  licenseExpiry: date('license_expiry'),
  status: text('status').default('active'),
  // Nav personas datu — saistīts caur HR sistēmu
});

// db/schema/tracking.ts — Transportlīdzekļu pozīcijas (2. fāze)

export const vehiclePositions = pgTable('vehicle_positions', {
  id: serial('id').primaryKey(),
  vehicleId: text('vehicle_id').references(() => vehicles.id),
  tripId: text('trip_id').references(() => trips.id),
  lat: doublePrecision('lat').notNull(),
  lon: doublePrecision('lon').notNull(),
  bearing: real('bearing'),
  speed: real('speed'),
  timestamp: timestamp('timestamp', { withTimezone: true }).notNull(),
  // Atvasināti lauki
  scheduleAdherence: integer('schedule_adherence_seconds'),
  congestionLevel: text('congestion_level'),
}, (table) => ({
  vehicleTimeIdx: index('vp_vehicle_time_idx').on(table.vehicleId, table.timestamp),
  timestampIdx: index('vp_timestamp_idx').on(table.timestamp),
}));

// Pašreizējo transportlīdzekļu pozīciju kešatmiņa (tikai jaunākās)
export const currentPositions = pgTable('current_positions', {
  vehicleId: text('vehicle_id').primaryKey().references(() => vehicles.id),
  tripId: text('trip_id'),
  routeId: text('route_id'),
  lat: doublePrecision('lat').notNull(),
  lon: doublePrecision('lon').notNull(),
  bearing: real('bearing'),
  speed: real('speed'),
  timestamp: timestamp('timestamp', { withTimezone: true }).notNull(),
  status: text('status').default('in_service'),
  updatedAt: timestamp('updated_at').defaultNow(),
});
```

### 5.3 Auth shēma

```typescript
// db/schema/auth.ts — Auth.js v5 saderīga

export const users = pgTable('users', {
  id: text('id').primaryKey(),
  email: text('email').unique().notNull(),
  name: text('name'),
  role: text('role').default('viewer'),           // admin, dispatcher, editor, viewer
  hashedPassword: text('hashed_password'),
  createdAt: timestamp('created_at').defaultNow(),
});

// Lomas: admin (pilna piekļuve), dispatcher (izsekošana + darbības),
//        editor (maršruti/grafiki), viewer (tikai lasīšana)
```

---

## 6. API dizains

### 6.1 tRPC maršrutētāju katalogs

```
routes.router
├── routes.list          GET    — Visu maršrutu saraksts ar filtriem
├── routes.getById       GET    — Iegūt maršrutu ar pieturām un formu
├── routes.create        MUTATION — Izveidot jaunu maršrutu
├── routes.update        MUTATION — Atjaunināt maršruta detaļas
├── routes.delete        MUTATION — Dzēst maršrutu (tikai admin)
└── routes.getShape      GET    — Iegūt maršruta ģeometriju kartei

schedules.router
├── schedules.getByRoute GET    — Iegūt sarakstu maršrutam
├── schedules.getTrips   GET    — Iegūt reisus pakalpojumu dienai
├── schedules.createTrip MUTATION — Pievienot reisu grafikam
├── schedules.updateStopTimes MUTATION — Rediģēt pieturu laikus
├── schedules.cloneService MUTATION — Klonēt grafika modeli
└── schedules.getCalendar GET   — Iegūt pakalpojumu kalendāru

stops.router
├── stops.list           GET    — Visu pieturu saraksts ar telpisku filtru
├── stops.nearby         GET    — Pieturas rādiusā (PostGIS ST_DWithin)
├── stops.getById        GET    — Iegūt pieturu ar atiešanām
├── stops.create         MUTATION — Izveidot pieturu ar koordinātām
├── stops.update         MUTATION — Atjaunināt pieturas detaļas
└── stops.search         GET    — Pilna teksta meklēšana pēc nosaukuma

gtfs.router
├── gtfs.import          MUTATION — Importēt GTFS ZIP failu
├── gtfs.export          GET    — Ģenerēt un lejupielādēt GTFS ZIP
├── gtfs.validate        GET    — Validēt pašreizējos datus pret GTFS specifikāciju
└── gtfs.status          GET    — Pēdējā importa statuss + datu svaigums

fleet.router (2. fāze)
├── fleet.vehicles.list  GET    — Transportlīdzekļu saraksts ar statusu
├── fleet.vehicles.assign MUTATION — Piešķirt transportlīdzekli reisam
└── fleet.vehicles.updateStatus MUTATION — Mainīt transportlīdzekļa statusu

tracking.router (2. fāze)
├── tracking.positions   SUBSCRIPTION — SSE straume transportlīdzekļu pozīcijām
├── tracking.ingest      MUTATION — Saņemt GPS datus no transportlīdzekļiem
└── tracking.history     GET    — Vēsturiskās pozīcijas atskaņošanai

assistant.router (3. fāze)
├── assistant.chat       MUTATION — Nosūtīt ziņu AI aģentam
└── assistant.suggestions GET   — Iegūt proaktīvus AI ieteikumus
```

### 6.2 GTFS galapunkti (REST)

```
POST  /api/gtfs/import    — Augšupielādēt GTFS ZIP, parsēt, validēt, importēt
GET   /api/gtfs/export    — Ģenerēt GTFS ZIP no datubāzes
GET   /api/gtfs/feed.zip  — Publiska GTFS plūsmas lejupielāde
GET   /api/gtfs-rt/vehicle-positions  — GTFS-Realtime VehiclePosition (2. fāze)
GET   /api/gtfs-rt/trip-updates       — GTFS-Realtime TripUpdate (2. fāze)
```

## 7. UI/UX Dizains

### 7.1 Izkārtojuma Struktūra (Vairāku Paneļu Vadības Panelis)

```
┌─────────────────────────────────────────────────────────────────┐
│  [Logo]  Rīgas Sabiedriskā Transporta CMS  🔍 Meklēt...  🔔 Brīdinājumi  👤   │
├──────┬──────────────────────────────────────────┬───────────────┤
│      │                                          │               │
│  📍  │      GALVENĀ SATURA ZONA                 │  DETAĻU       │
│Marš. │                                          │  PANELIS      │
│      │  (Karte / Tabula / Forma / Kalendārs)    │               │
│  📅  │                                          │  (Izvēlētā    │
│Saraks│                                          │   elementa    │
│      │                                          │   info,       │
│  🚌  │                                          │   rediģēšanas │
│Flote │                                          │   forma,      │
│      │                                          │   AI čats)    │
│  👤  │                                          │               │
│Vadī. │                                          │               │
│      │                                          │               │
│  📊  │                                          │               │
│Atskai│                                          │               │
│      │                                          │               │
├──────┴──────────────────────────────────────────┴───────────────┤
│  Statusa Josla: 🟢 42 reisā  🟡 3 aizkavēti  🔴 1 brīdinājums │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Galvenās Lapas

**Maršrutu Pārvaldība (`/routes`)**
- Kreisā puse: Filtrējams maršrutu saraksts (Tanstack Table) ar krāsu paraugiem
- Centrs: MapLibre karte, kas parāda izvēlēto maršruta līniju + pieturas
- Labā puse: Maršruta detaļu panelis (nosaukums, īsais nosaukums, tips, rediģēšanas forma)
- Darbība: Klikšķis uz maršruta → izcelšana uz kartes → pieturu rādīšana secībā

**Sarakstu Redaktors (`/schedules`)**
- Sarakstu režģis: Rindas = reisi, Kolonnas = pieturas, Šūnas = laiki
- Kalendāra atlasītājs: Pakalpojuma modelis (darba diena/nedēļas nogale/svētki)
- Laika-attāluma diagramma (Marey diagramma) vizuālai pārbaudei
- Rediģēšana vietā ar konfliktu noteikšanu

**Tiešraides Izsekošana (`/tracking`) — 2. Fāze**
- Pilnekrāna MapLibre karte ar transportlīdzekļu marķieriem
- Transportlīdzekļu marķieri: maršruta numurs + krāsā kodēta precizitātes aura
- Klikšķis uz transportlīdzekļa → sānjosla ar detaļām (maršruts, vadītājs, ETA, ātrums)
- Apakšējā josla: maršruta laika līnija / intervālu skats
- Krāsu kodējums: 🟢 laikā, 🟡 1-5 min kavēšanās, 🔴 >5 min kavēšanās

**AI Asistents (`/assistant`) — 3. Fāze**
- Čata saskarne labajā sānjoslā
- Tikai lasīšanas vaicājumi: "Kuri autobusi kavējas?", "Parādīt 22. maršruta statusu"
- Nav rakstīšanas operāciju caur AI — tikai ieteikumi ar apstiprināt/noraidīt
- Tokenu lietojuma skaitītājs redzams dispečeriem

### 7.3 Krāsu Kodēšanas Standarti

| Krāsa | Nozīme |
|---|---|
| 🟢 Zaļā `#22c55e` | Laikā / Normāls / Aktīvs |
| 🟡 Dzintara `#f59e0b` | Neliela kavēšanās (1-5 min) / Brīdinājums |
| 🔴 Sarkanā `#ef4444` | Liela kavēšanās (>5 min) / Brīdinājums |
| 🔵 Zilā `#3b82f6` | Informatīvs / Izvēlēts |
| ⚪ Pelēkā `#6b7280` | Ārpus ekspluatācijas / Neaktīvs / Novecojuši dati |

### 7.4 Internacionalizācija

- **Primārā:** Latviešu (LV)
- **Sekundārā:** Angļu (EN)
- Izmantot `next-intl` i18n vajadzībām
- GTFS dati glabāti ar gan `name`, gan `name_lv` laukiem
- UI valodas atlasītājs lietotāja profilā

---

## 8. AI Aģenta Dizains (3. Fāze)

### 8.1 Arhitektūra: Tikai Konsultatīvais Režīms

```
┌──────────────────────────────────────────────────┐
│               DISPEČERA SASKARNE                  │
│                                                   │
│  "Kuri autobusi kavējas?"                         │
│           │                                       │
│           ▼                                       │
│  ┌────────────────────────────┐                  │
│  │   VAICĀJUMU KLASIFIKATORS   │                  │
│  │  (Haiku 4.5 — ātrs/lēts)    │                  │
│  └────────────┬───────────────┘                  │
│               │                                   │
│  Vienkāršs ───┤──── Sarežģīts                     │
│               │                                   │
│  ┌────────────▼───────────────┐                  │
│  │   VAICĀJUMU IZPILDĪTĀJS     │                  │
│  │  (Sonnet 4.5 — līdzsvarots) │                  │
│  │                              │                  │
│  │  Rīki:                       │                  │
│  │  - query_bus_status          │                  │
│  │  - get_route_schedule        │                  │
│  │  - get_ridership_data        │                  │
│  │  - check_driver_availability │                  │
│  │  - search_stops              │                  │
│  │                              │                  │
│  │  TIKAI LASĪŠANA. Nav mutāciju.│                  │
│  └────────────┬───────────────┘                  │
│               │                                   │
│               ▼                                   │
│  ┌────────────────────────────┐                  │
│  │     ATBILDE + IETEIKUMS     │                  │
│  │  "3 autobusi kavējas >5 min:│                  │
│  │   22. maršruts, 7. maršruts,│                  │
│  │   15. maršruts.              │                  │
│  │   [Skatīt Kartē] [Noraidīt]"│                  │
│  └────────────────────────────┘                  │
└──────────────────────────────────────────────────┘
```

### 8.2 Izmaksu Kontrole

| Kontrole | Ieviešana |
|---|---|
| **Modeļu maršrutēšana** | Haiku 4.5 ($1/$5/MTok) klasifikācijai, Sonnet 4.5 ($3/$15/MTok) loģikai |
| **Uzvedņu kešatmiņa** | Kešot sistēmas uzvedni + rīku definīcijas (0.1x izmaksas pie kešatmiņas trāpījumiem) |
| **Tokenu budžets** | Stingrs limits uz lietotāju dienā (piem., 50 vaicājumi/lietotājs/dienā) |
| **Tērēšanas limits** | Stingrs limits Anthropic kontam ($100/mēnesī) |
| **Rezerves variants** | Kad API nav pieejams → parādīt "AI asistents nav tiešsaistē. Izmantojiet meklēšanu." |

### 8.3 Rīki (Tikai Lasīšana)

```typescript
const tools = [
  {
    name: 'query_bus_status',
    description: 'Iegūt autobusu pašreizējo statusu (kavēti, laikā, ārpus ekspluatācijas)',
    parameters: { routeId: 'optional', status: 'optional' }
  },
  {
    name: 'get_route_schedule',
    description: 'Iegūt konkrēta maršruta sarakstu/grafiku',
    parameters: { routeId: 'required', date: 'optional' }
  },
  {
    name: 'search_stops',
    description: 'Meklēt pieturas pēc nosaukuma vai tuvuma',
    parameters: { query: 'optional', lat: 'optional', lon: 'optional', radius: 'optional' }
  },
  {
    name: 'get_adherence_report',
    description: 'Iegūt precizitātes rādītājus',
    parameters: { routeId: 'optional', dateRange: 'optional' }
  },
  {
    name: 'check_driver_availability',
    description: 'Pārbaudīt, kuri vadītāji ir pieejami norīkojumiem',
    parameters: { date: 'required', shiftType: 'optional' }
  },
];
// NAV rakstīšanas rīku. AI nevar izveidot, atjaunināt vai dzēst neko.
```

---

## 9. Reāllaika Izsekošana (2. Fāze)

### 9.1 Datu Plūsma

```
GPS Aparatūra (Autobuss)
    │
    │  HTTP POST /api/positions
    │  {vehicleId, lat, lon, speed, bearing, timestamp}
    │  (Autentificēts ar ierīces sertifikātu)
    │
    ▼
┌──────────────────────────┐
│  GPS Ievadīšanas Galapunkts│
│                           │
│   1. Ievades validācija   │
│   2. Attāluma filtrs      │  (Izlaist, ja pārvietojies < 10m)
│   3. Rakstīt DB           │  (vehicle_positions + current_positions)
│   4. Pārraidīt caur SSE   │  (Procesa iekšējā pub/sub → tRPC abonements)
└──────────────────────────┘
    │
    │  tRPC SSE abonements
    │  (tracking.positions)
    │
    ▼
┌──────────────────────────┐
│  MapLibre Vadības Panelis │
│                           │
│   - GeoJSON avota slānis  │
│   - Simbolu slāņa marķieri│
│   - 5 sekunžu atjaunināšanas cikls │
│   - Krāsā kodēta precizitāte │
└──────────────────────────┘
```

### 9.2 Esošo Plūsmu Izmantošana

Pirms pielāgotas GPS ievadīšanas būvniecības, izmantot Rīgas Satiksmes esošos datus:

```typescript
// Aptaujāt SIRI pieturvietu atiešanas API katras 30 sekundes
const pollSiriDepartures = async (stopId: string) => {
  const response = await fetch(
    `https://saraksti.rigassatiksme.lv/siri-stop-departures.php?stopid=${stopId}`
  );
  return response.json();
};

// Importēt GTFS plūsmu sarakstu datiem
const importGtfsFeed = async () => {
  const zip = await fetch('https://saraksti.rigassatiksme.lv/gtfs.zip');
  // Parsēt CSV failus, validēt, masveida ievietot datubāzē
};
```

### 9.3 Novecojušu Datu Apstrāde

| Nosacījums | Attēlojums | Darbība |
|---|---|---|
| Pozīcija < 30s veca | Normāls marķieris | — |
| Pozīcija 30-120s veca | Pelēks marķieris + "Pēdējoreiz redzēts pirms X sek" | — |
| Pozīcija > 120s veca | Spoku marķieris + brīdinājuma ikona | Brīdināt dispečeru |
| Nav saņemta nekāda pozīcija | Slēpts no kartes | Parādīt "neizsekotu transportlīdzekļu" sarakstā |

---

## 10. Ieviešanas Ceļvedis

### 1. Fāze: Pamata CMS (1.-8. Nedēļa)

```
1.-2. Nedēļa: Pamats
├── Inicializēt Next.js 15 + TypeScript projektu
├── Konfigurēt Drizzle ORM + Supabase PostgreSQL
├── Iestatīt Auth.js v5 ar lomu balstītu piekļuvi
├── Ieviest tRPC v11 pamata maršrutētāju
├── Konfigurēt Tailwind v4 + Shadcn/ui
├── Iestatīt MapLibre GL JS ar OpenFreeMap flīzēm
├── ** SPIKE: Drizzle + PostGIS telpisko vaicājumu pierādījuma koncepcija **
└── Docker + GitHub Actions CI/CD

3.-4. Nedēļa: GTFS Imports & Datu Modelis
├── GTFS ZIP parsētājs (agencies, routes, stops, trips, stop_times, calendar, shapes)
├── Masveida importa konveijers ar validāciju
├── GTFS eksports (ģenerēt derīgu ZIP no datubāzes)
├── GTFS datu integritātes pārbaudes
└── Aizpildīt datubāzi ar Rīgas Satiksmes GTFS plūsmu

5.-6. Nedēļa: Maršrutu & Pieturu Pārvaldība
├── Maršrutu saraksta lapa (Tanstack Table, filtri, meklēšana)
├── Maršruta detaļu lapa ar kartes vizualizāciju
├── Maršruta CRUD (izveidot, rediģēt, dzēst ar apstiprinājumu)
├── Pieturu saraksts ar tuvuma meklēšanu
├── Pieturu pārvaldība ar kartes balstītu koordinātu atlasītāju
├── Maršruta līnijas attēlošana uz MapLibre kartes
└── Pieturu secības redaktors maršrutiem

7.-8. Nedēļa: Sarakstu Redaktors & Uzlabojumi
├── Sarakstu režģa skats (reisi × pieturas)
├── Pakalpojuma kalendāra pārvaldība (darba diena/nedēļas nogale/svētki)
├── Kalendāra izņēmumu redaktors (svētki, notikumi)
├── Sarakstu validācija (konfliktu noteikšana, GTFS atbilstība)
├── GTFS eksporta pārbaude
├── i18n (LV/EN) visam UI tekstam
├── Pamata meklēšana un filtrēšana visām entītijām
└── Testēšana, kļūdu labošana, dokumentācija

REZULTĀTS: Darbojošās CMS, kur dispečeri var skatīt un rediģēt
maršrutus, pieturas un sarakstus. GTFS imports no Rīgas Satiksmes.
```

### 2. Fāze: Tiešraides Operācijas (9.-16. Nedēļa)

```
9.-10. Nedēļa: Transportlīdzekļu & Vadītāju Pārvaldība
├── Transportlīdzekļu inventāra CRUD
├── Vadītāju pārvaldība (pseidonimizēta, GDPR saderīga)
├── Transportlīdzeklis-reisa norīkojums
├── Vadītājs-transportlīdzekļa norīkojums
└── Apkopes statusa izsekošana

11.-12. Nedēļa: Reāllaika Izsekošana
├── GPS ievadīšanas API galapunkts (autentificēts)
├── Transportlīdzekļa pozīcijas glabāšana (pašreizējā + vēsturiskā)
├── Procesa iekšējā pub/sub pozīciju pārraidei
├── tRPC SSE abonements tiešraides pozīcijām
├── MapLibre reāllaika transportlīdzekļu marķieri (simbolu slānis)
├── Transportlīdzekļa detaļu sānjosla pie klikšķa
└── Novecojušu datu indikatori

13.-14. Nedēļa: Operatīvais Vadības Panelis
├── Flotes statusa pārskats (ekspluatācijā, kavēti, ārpus ekspluatācijas skaiti)
├── Precizitātes rādītāji
├── Maršruta precizitātes uzraudzība
├── Pamata brīdinājumu/paziņojumu sistēma
├── Sarakstu precizitātes aprēķins
└── Pievienot Upstash Redis SSE izkliedi (ja nepieciešams)

15.-16. Nedēļa: Analītika & Atskaites
├── Pasažieru skaita datu attēlošana (no APC, ja pieejams)
├── Precizitātes diagrammas (Shadcn/ui diagrammas)
├── Vēsturisko pozīciju atskaņošana uz kartes
├── Eksportēt atskaites (CSV/PDF)
├── GTFS-Realtime VehiclePosition plūsmas ģenerēšana
└── Testēšana, nostiprinašana, GDPR audits

REZULTĀTS: Tiešraides izsekošanas vadības panelis, kas parāda reāllaika
autobusu pozīcijas. Flotes un vadītāju pārvaldība. Pamata analītika.
```

### 3. Fāze: Inteliģence (17.-24. Nedēļa)

```
17.-18. Nedēļa: AI Asistenta Pamats
├── Claude API integrācija (Sonnet 4.5 primārais, Haiku 4.5 maršrutēšana)
├── Rīku definīcijas (5 tikai lasīšanas rīki)
├── Uzvedņu inženierija ar sabiedriskā transporta jomas kontekstu
├── Čata UI sānjoslā
├── Uzvedņu kešatmiņa sistēmas uzvednei + rīkiem
└── Tokenu budžeta un tērēšanas limita ieviešana

19.-20. Nedēļa: AI Uzlabojumi & Ieteikumi
├── Proaktīva kavēšanās brīdināšana
├── Sarakstu precizitātes analīze
├── Dabiskās valodas meklēšana visās entītijās
├── Sarunu vēstures pārvaldība
└── Rezerves UI, kad API nav pieejams

21.-22. Nedēļa: ES Standartu Atbilstība
├── NeTEx eksporta iespēja (ES prasība)
├── SIRI reāllaika informācijas plūsma
├── GTFS-Realtime TripUpdate plūsma
├── Datu validācija pret ES standartiem
└── Pieejamības atbilstība (WCAG 2.1 AA)

23.-24. Nedēļa: Paplašinātas Funkcijas & Palaišana
├── Paplašināti vadības paneļa izkārtojumi (paralēli maršruti)
├── Tastatūras īsinājumtaustiņi dispečera darbplūsmai
├── Veiktspējas optimizācija (Server Components, kešatmiņa)
├── Drošības nostiprinašana (frekvences ierobežošana, ievades validācija)
├── Slodzes testēšana (100+ transportlīdzekļi)
├── GDPR Datu Aizsardzības Ietekmes Novērtējums (ar juridisko konsultantu)
└── Produkcijas izvietošana

REZULTĀTS: Pilnīgi funkcionalā sabiedriskā transporta pārvaldības CMS ar AI
asistentu, ES standartu atbilstību un produkcijas nostiprinašanu.
```

---

## 11. Risku Reģistrs

| # | Risks | Varbūtība | Ietekme | Mazināšana |
|---|---|---|---|---|
| 1 | Drizzle + PostGIS integrācija neizdodas | Vidēja | Augsta | 1. nedēļas izpēte. Rezerves variants: raw SQL + Kysely. |
| 2 | Mapbox-uz-MapLibre kartes kvalitātes atšķirība | Zema | Vidēja | Testēt ar Rīgas datiem 1. nedēļā. Flīzes no OpenFreeMap. |
| 3 | GDPR pārkāpums no GPS izsekošanas | Augsta | Kritiska | Privātums pēc dizaina. Iesaistīt Latvijas DVI advokātu pirms 2. fāzes. |
| 4 | Claude API izmaksas pārsniedz budžetu | Vidēja | Vidēja | Stingrs tērēšanas limits ($100/mēnesī). Modeļu maršrutēšana (Haiku vienkāršiem). |
| 5 | Rīgas Satiksmes GTFS plūsmas formāts mainās | Zema | Augsta | Validēt importā. Brīdināt par shēmas neatbilstību. |
| 6 | SSE savienojumu limiti zem slodzes | Zema | Vidēja | HTTP/2 nepieciešams. Viena abonenta izkliedes modelis. |
| 7 | Darbības apjoma paplašināšanās pāri 24 nedēļu plānam | Augsta | Augsta | Strikti fāžu vārti. Nav 2. fāzes funkciju 1. fāzē. |
| 8 | Vasaras laika apstrādes kļūdas | Vidēja | Vidēja | Visi laika zīmogi UTC. Europe/Riga laika zona tikai attēlošanā. |
| 9 | GPS signāla zudums Vecrīgā | Vidēja | Vidēja | Dead reckoning. Novecojušu datu vizuālie indikatori. |
| 10 | Auth.js v5 sarežģītība RBAC | Vidēja | Vidēja | Vienkāršs lomu enum (4 lomas). JWT + middleware modelis. |

---

## 12. ISC Pārbaude

### Atjauninātais ISC Status (Pēc THINK Fāzes)

| # | Kā Izskatās Ideālais Stāvoklis | Avots | Status |
|---|---|---|---|
| 1 | Maršrutu CRUD ar kartes rediģēšanu | EXPLICIT | ⏳ 1. fāze |
| 2 | Sarakstu pārvaldība ar kalendāru | EXPLICIT | ⏳ 1. fāze |
| 3 | Pieturu pārvaldība ar ģeolokāciju | EXPLICIT | ⏳ 1. fāze |
| 4 | Flotes/transportlīdzekļu pārvaldība | EXPLICIT | ⏳ 2. fāze |
| 5 | Vadītāju pārvaldība (GDPR saderīga) | EXPLICIT | ⏳ 2. fāze |
| 6 | Lomu balstīta piekļuve (4 lomas) | IMPLICIT | ⏳ 1. fāze |
| 7 | Tiešraides karte ar transportlīdzekļu pozīcijām | EXPLICIT | ⏳ 2. fāze |
| 8 | AI asistents (konsultatīvs, tikai lasīšana) | EXPLICIT | ⏳ 3. fāze |
| 9 | GTFS imports/eksports | INFERRED | ⏳ 1. fāze |
| 10 | GTFS-Realtime plūsmas ģenerēšana | INFERRED | ⏳ 2. fāze |
| 11 | Latviešu valodas atbalsts | EXPLICIT | ⏳ 1. fāze |
| 12 | GDPR privātums pēc dizaina | IMPLICIT | ⏳ 2. fāze |
| 13 | ES NeTEx/SIRI atbilstība | IMPLICIT | ⏳ 3. fāze |
| 14 | $31-117/mēnesī budžets | INFERRED | ✅ Validēts |
| 15 | 12 tehnoloģijas, 1 valoda | INFERRED | ✅ Validēts |
| 16 | Posmots ceļvedis (3 × 8 nedēļas) | EXPLICIT | ✅ Dokumentēts |
| 17 | Arhitektūras diagrammas | IMPLICIT | ✅ Dokumentēts |
| 18 | Datubāzes shēma | IMPLICIT | ✅ Dokumentēts |
| 19 | API katalogs | IMPLICIT | ✅ Dokumentēts |
| 20 | UI maketi | IMPLICIT | ✅ Dokumentēts |

### Kas Tika Apzināti Izslēgts

| Funkcija | Iemesls | Kad Pārskatīt |
|---|---|---|
| Google OR-Tools | Fiksēti maršruti neneprasa VRP risinātāju | Ja tiek pievienots pieprasījumu balstīts transports |
| TimescaleDB | 20 ieraksti/sek to neattaisno | Kad flote pārsniedz 500 transportlīdzekļus |
| Mikropakalpojumi | 2-3 izstrādātāju komanda nevar uzturēt | Kad komanda aug līdz 6+ |
| WebSockets | SSE pietiek vienvirzienam | Ja nepieciešams divvirzienu vadītāju čats |
| Publiskā pasažieru karte | Darbības apjoms ierobežots operatora CMS | Kad tiek pieprasītas pasažieriem orientētas funkcijas |
| Biļešu pārvaldība | Esošā e-talons sistēma to apstrādā | Kad nepieciešama biļešu integrācija |

---

## 5 Kritiski Jautājumi Pirms Ieviešanas

1. **Vai Rīgas Satiksme ir esošs AVL API papildus publiskajam GTFS-RT?** Ja jā, 2. fāzes izsekošana ievērojami vienkāršojas — mēs izmantojam viņu plūsmu, nevis būvējam pielāgotu GPS ievadīšanu.
2. **Kas ir galvenie lietotāji — dispečeri, plānotāji vai vadītāji?** Intervēt faktiskos darbiniekus, lai validētu 2.-3. fāzes funkcijas un atbilstoši prioritizētu UI darbplūsmas.
3. **Izvietošanas mērķis — mākonis (Railway/Vercel) vai uz vietas?** Izmaksu aprēķinos pieņemts mākonis; pašvaldības infrastruktūra uz vietas ievērojami maina arhitektūru.
4. **GDPR — iesaistīt Latvijas datu aizsardzības konsultantu pirms 2. fāzes GPS izsekošanas.** Vadītāja atrašanās vietas dati ir personas dati saskaņā ar GDPR. Datu Aizsardzības Ietekmes Novērtējums (DPIA) ir juridiski nepieciešams pirms apstrādes sākšanas.
5. **Būvēt pret pirkt analīze pret Swiftly/Optibus cenām.** Iegūt faktiskus piedāvājumus, lai validētu, ka pielāgota būvniecība ir pamatota pret SaaS alternatīvām par $6,000-12,000/gadā.

---

*Ģenerēts ar THE ALGORITHM DETERMINED piepūles līmenī*
*6 paralēlie analīzes aģenti | ~300k tokenu pētījums sintezēts*
*Council Debate + First Principles + RedTeam + Competitive Analysis + Riga Research + Tech Stack Review*
