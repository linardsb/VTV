# SOP & File Automation Plan

## Overview

Automate two key operational bottlenecks:
1. **Document ingestion** - Eliminate manual file uploads via automated watchers and scrapers
2. **SOP generation** - Use LLM to draft, update, and maintain Standard Operating Procedures from operational data

Both systems integrate with the existing RAG knowledge base (`app/knowledge/`) and agent tools.

## Part 1: Automated Document Ingestion

### 1.1 Shared Folder Watcher (Priority: #1)

**What**: Monitor a local/network directory for new files. When a file appears, automatically ingest it into the knowledge base with domain classification.

**Architecture**:
```
/data/knowledge-inbox/
  transit/          # Auto-tagged domain: transit
  hr/               # Auto-tagged domain: hr
  legal/            # Auto-tagged domain: legal
  safety/           # Auto-tagged domain: safety
  general/          # Auto-classified by LLM
```

**Implementation**:
```python
# app/knowledge/automation/folder_watcher.py

class FolderWatcher:
    """Watch configured directories for new documents and auto-ingest."""

    def __init__(self, settings: Settings, knowledge_service: KnowledgeService):
        self.inbox_path = settings.KNOWLEDGE_INBOX_PATH  # e.g., "/data/knowledge-inbox"
        self.poll_interval = 60  # seconds
        self.supported_extensions = {".pdf", ".docx", ".txt", ".eml", ".png", ".jpg", ".xlsx", ".csv"}

    async def scan_and_ingest(self) -> list[str]:
        """Scan inbox directories and ingest new files."""
        ingested: list[str] = []
        for domain_dir in Path(self.inbox_path).iterdir():
            if not domain_dir.is_dir():
                continue
            domain = domain_dir.name  # Folder name = domain tag
            for file_path in domain_dir.iterdir():
                if file_path.suffix.lower() in self.supported_extensions:
                    await self.knowledge_service.ingest_document(
                        file=file_path,
                        domain=domain if domain != "general" else await self._auto_classify(file_path),
                        language=await self._detect_language(file_path),
                    )
                    file_path.rename(file_path.parent / "processed" / file_path.name)
                    ingested.append(str(file_path))
        return ingested
```

**Scheduling**: APScheduler interval job, runs every 60 seconds.
**Cost**: $0/month (all local processing).
**Effort**: 1 day.
**Human time saved**: ~2 hrs/week (currently manual uploads).

### 1.2 Email Inbox Monitor (Priority: #3)

**What**: Poll a shared mailbox (e.g., `documents@vtv.lv`) for emails with attachments. Extract attachments and email body, ingest into knowledge base.

**Architecture**:
```
IMAP Mailbox (documents@vtv.lv)
  -> Fetch unread emails
  -> Extract attachments (PDF, DOCX, XLSX)
  -> Extract email body as text document
  -> Auto-classify domain from subject + body
  -> Ingest all parts into knowledge base
  -> Mark email as read / move to "Processed" folder
```

**Implementation**:
```python
# app/knowledge/automation/email_monitor.py

class EmailMonitor:
    """Poll IMAP mailbox for document attachments."""

    def __init__(self, settings: Settings):
        self.imap_host = settings.KNOWLEDGE_IMAP_HOST
        self.imap_user = settings.KNOWLEDGE_IMAP_USER
        self.imap_password = settings.KNOWLEDGE_IMAP_PASSWORD
        self.poll_interval = 300  # 5 minutes

    async def check_inbox(self) -> list[str]:
        """Fetch unread emails and ingest attachments."""
        # Connect via IMAP (aioimaplib for async)
        # Fetch UNSEEN messages
        # For each message:
        #   - Extract text body -> ingest as "email" source_type
        #   - Extract attachments -> ingest with detected source_type
        #   - Auto-classify domain from subject line keywords
        #   - Mark as SEEN
```

**New dependencies**: `aioimaplib` for async IMAP.
**New config vars**: `KNOWLEDGE_IMAP_HOST`, `KNOWLEDGE_IMAP_USER`, `KNOWLEDGE_IMAP_PASSWORD`, `KNOWLEDGE_IMAP_FOLDER`.
**Scheduling**: APScheduler interval job, runs every 5 minutes.
**Cost**: $0/month.
**Effort**: 1.5 days.
**Human time saved**: ~3 hrs/week (forwarding/uploading email attachments).

### 1.3 Web Scraper for Regulations (Priority: #4)

**What**: Periodically scrape Latvian transport regulations, EU directives, and municipal announcements. Detect changes and re-ingest updated documents.

**Sources**:

| Source | URL Pattern | Content Type | Frequency |
|--------|-------------|-------------|-----------|
| Latvian law portal | likumi.lv (transport section) | HTML | Weekly |
| EU transport regulations | eur-lex.europa.eu (Reg. 1370/2007, 561/2006) | PDF/HTML | Monthly |
| Riga municipality | riga.lv/transport | HTML | Weekly |
| CKAN transit datasets | data.gov.lv (transport category) | CSV/JSON/PDF | Weekly |
| Rigas Satiksme announcements | rigassatiksme.lv | HTML | Daily |

**Implementation**:
```python
# app/knowledge/automation/web_scraper.py

class RegulationScraper:
    """Scrape and ingest regulatory documents from configured sources."""

    sources: list[ScraperSource] = [
        ScraperSource(
            name="likumi_transport",
            url="https://likumi.lv/ta/tema/transports",
            content_type="html",
            domain="legal",
            schedule="weekly",
        ),
        # ... additional sources
    ]

    async def scrape_source(self, source: ScraperSource) -> list[str]:
        """Fetch, extract, and ingest content from a web source."""
        # 1. Fetch URL with httpx
        # 2. Parse HTML with beautifulsoup4
        # 3. Extract text content
        # 4. Hash content to detect changes (skip if unchanged)
        # 5. Ingest into knowledge base with source URL as metadata
```

**Change detection**: SHA-256 hash of extracted text, stored in `document.metadata_json`. Skip re-ingestion if hash matches.
**New dependencies**: `beautifulsoup4`, `lxml`.
**Scheduling**: APScheduler cron jobs (daily/weekly/monthly per source).
**Cost**: $0/month.
**Effort**: 2 days.
**Human time saved**: ~4 hrs/month (manual regulation tracking).

### 1.4 GTFS Documentation Auto-Sync (Priority: #5)

**What**: When GTFS static data is refreshed (currently 24h TTL in `static_cache.py`), automatically extract and ingest documentation about route changes, new stops, schedule updates.

**Architecture**:
```
GTFS Static Cache refresh (existing)
  -> Compare new vs old route/stop data
  -> Generate human-readable changelog
  -> Ingest changelog as "transit" domain document
  -> Agent can answer "What routes changed this week?"
```

**Implementation**:
```python
# app/knowledge/automation/gtfs_sync.py

class GTFSSyncMonitor:
    """Generate and ingest knowledge documents from GTFS data changes."""

    async def on_cache_refresh(self, old_data: StaticGTFS, new_data: StaticGTFS) -> None:
        """Compare GTFS versions and ingest change summary."""
        changes = self._diff_gtfs(old_data, new_data)
        if changes:
            changelog = self._format_changelog(changes)
            await self.knowledge_service.ingest_document(
                content=changelog,
                domain="transit",
                source_type="text",
                metadata={"source": "gtfs_sync", "date": date.today().isoformat()},
            )

    def _diff_gtfs(self, old: StaticGTFS, new: StaticGTFS) -> list[GTFSChange]:
        """Detect route additions, removals, stop changes, schedule shifts."""
        # Compare routes: added/removed/renamed
        # Compare stops: added/removed/relocated
        # Compare schedules: frequency changes, time shifts
```

**Cost**: $0/month.
**Effort**: 1.5 days.
**Integration**: Hook into `StaticGTFSCache.refresh()` callback.

## Part 2: Automated SOP Generation

### 2.1 Incident-to-SOP Pipeline (Priority: #2)

**What**: Analyze incident reports and automatically draft SOPs for recurring patterns. When similar incidents occur 3+ times, generate a draft SOP and save to Obsidian vault for human review.

**Architecture**:
```
Incident Reports (ingested documents, domain="operations")
  -> LLM clusters similar incidents
  -> Identifies recurring patterns (3+ occurrences)
  -> Generates draft SOP with:
     - Trigger conditions
     - Step-by-step response
     - Escalation criteria
     - Contact information
  -> Saves to Obsidian vault: SOPs/drafts/{topic}.md
  -> Notifies dispatcher via agent: "New SOP draft for review"
```

**Implementation**:
```python
# app/knowledge/automation/sop_generator.py

class SOPGenerator:
    """Generate SOP drafts from incident patterns."""

    async def analyze_incidents(self) -> list[SOPDraft]:
        """Search for incident clusters and generate SOP drafts."""
        # 1. Search knowledge base for recent incidents
        incidents = await self.knowledge_service.search(
            query="incident report",
            domain="operations",
            limit=100,
        )

        # 2. Use LLM to cluster similar incidents
        clusters = await self._cluster_incidents(incidents)

        # 3. For clusters with 3+ incidents, generate SOP draft
        drafts: list[SOPDraft] = []
        for cluster in clusters:
            if cluster.count >= 3:
                draft = await self._generate_sop(cluster)
                drafts.append(draft)

        return drafts

    async def _generate_sop(self, cluster: IncidentCluster) -> SOPDraft:
        """Use LLM to draft a SOP from incident cluster."""
        prompt = f"""Based on these {cluster.count} similar incidents,
        create a Standard Operating Procedure.

        Incidents:
        {cluster.summaries}

        Generate a SOP with:
        1. Title and scope
        2. Trigger conditions (when to use this SOP)
        3. Step-by-step response procedure
        4. Escalation criteria and contacts
        5. Recovery/normalization steps
        6. Lessons learned from past incidents

        Format as Markdown with frontmatter tags."""

        # Call LLM and return structured SOP
```

**LLM cost per SOP**: ~$0.05 (2K input tokens + 1K output).
**Scheduling**: Weekly analysis run (APScheduler cron, Sunday 02:00).
**Vault integration**: Uses existing `obsidian_manage_notes` tool to create draft notes.
**Effort**: 2 days.
**Human time saved**: ~8 hrs/month (manual SOP writing from incident patterns).

### 2.2 Regulation Change Detection (Priority: #6)

**What**: When a regulation document is re-ingested with changes, automatically identify which existing SOPs may be affected and flag them for review.

**Architecture**:
```
Regulation Updated (detected by web scraper hash change)
  -> Extract changed sections
  -> Search existing SOPs in Obsidian vault
  -> LLM identifies SOPs affected by the change
  -> Creates review task notes in vault: Reviews/{date}-regulation-impact.md
  -> Agent can report: "3 SOPs need review due to regulation update"
```

**Implementation**:
```python
# app/knowledge/automation/regulation_monitor.py

class RegulationChangeMonitor:
    """Detect regulation changes and flag affected SOPs."""

    async def on_regulation_updated(self, doc_id: int, old_hash: str, new_hash: str) -> None:
        """Analyze regulation change impact on existing SOPs."""
        # 1. Fetch old and new document chunks
        old_chunks = await self.repo.get_chunks_by_document(doc_id, version="previous")
        new_chunks = await self.repo.get_chunks_by_document(doc_id)

        # 2. Identify changed sections via text diff
        changes = self._diff_chunks(old_chunks, new_chunks)

        # 3. Search Obsidian SOPs for related procedures
        affected_sops = await self._find_affected_sops(changes)

        # 4. Generate impact report
        report = await self._generate_impact_report(changes, affected_sops)

        # 5. Save to Obsidian vault
        await self.obsidian_client.create_note(
            path=f"Reviews/{date.today().isoformat()}-regulation-impact.md",
            content=report,
        )
```

**LLM cost per analysis**: ~$0.10 (larger context for diff analysis).
**Scheduling**: Triggered by web scraper when content hash changes.
**Effort**: 2 days.
**Human time saved**: ~4 hrs/month (manual regulation tracking).

### 2.3 Shift Handover Note Generation (Priority: #2)

**What**: At shift change times, automatically generate a handover summary from operational data: current delays, active incidents, vehicle issues, weather alerts.

**Architecture**:
```
Shift Change Time (06:00, 14:00, 22:00)
  -> Query bus status (all routes) via agent tool
  -> Query active incidents from knowledge base
  -> Query weather (external API or manual input)
  -> Query vehicle maintenance status
  -> LLM generates structured handover note
  -> Save to Obsidian vault: Handovers/{date}-{shift}.md
  -> Agent can brief incoming dispatcher
```

**Implementation**:
```python
# app/knowledge/automation/handover_generator.py

class HandoverGenerator:
    """Generate shift handover notes from operational data."""

    SHIFT_TIMES = ["06:00", "14:00", "22:00"]

    async def generate_handover(self, shift: str) -> str:
        """Compile operational data into a handover note."""
        # 1. Get current transit status
        bus_status = await self._get_current_delays()

        # 2. Get active incidents (last 8 hours)
        incidents = await self.knowledge_service.search(
            query="incident active today",
            domain="operations",
            limit=10,
        )

        # 3. Get vehicle alerts
        vehicle_alerts = await self._get_vehicle_alerts()

        # 4. Generate handover note via LLM
        note = await self._compose_handover(
            shift=shift,
            delays=bus_status,
            incidents=incidents,
            vehicles=vehicle_alerts,
        )

        # 5. Save to Obsidian
        today = date.today().isoformat()
        await self.obsidian_client.create_note(
            path=f"Handovers/{today}-{shift}.md",
            content=note,
        )

        return note
```

**LLM cost per handover**: ~$0.03 (1K input + 500 output tokens).
**Monthly cost**: ~$2.70 (3 shifts x 30 days x $0.03).
**Scheduling**: APScheduler cron at 05:55, 13:55, 21:55 (5 min before shift change).
**Effort**: 2 days.
**Human time saved**: ~15 hrs/month (manual handover note compilation across 15 dispatchers).

### 2.4 Template-Based SOP Scaffolding (Priority: #7)

**What**: When a dispatcher types "create SOP for [topic]" in the agent chat, auto-generate a SOP scaffold using templates and existing knowledge base content.

**Architecture**:
```
Dispatcher: "Create SOP for handling bus breakdown on Brivibas iela"
  -> Agent recognizes SOP creation intent
  -> Searches knowledge base for related content
  -> Loads SOP template from Obsidian vault (Templates/sop-template.md)
  -> LLM fills template with context-specific content
  -> Creates draft in Obsidian: SOPs/drafts/bus-breakdown-brivibas.md
  -> Returns preview to dispatcher for review
```

**Implementation**: New agent tool function registered in `agent.py`.
**LLM cost per SOP**: ~$0.05.
**Effort**: 1 day (leverages existing tools).
**Human time saved**: ~2 hrs/month.

## Part 3: Scheduler Architecture

### APScheduler Integration

All automation jobs run via APScheduler, integrated into the FastAPI lifespan.

```python
# app/knowledge/automation/scheduler.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

class AutomationScheduler:
    """Manage all knowledge base automation jobs."""

    def __init__(self, settings: Settings):
        self.scheduler = AsyncIOScheduler()
        self.settings = settings

    def configure_jobs(self) -> None:
        """Register all automation jobs."""
        # Folder watcher - every 60s
        if self.settings.KNOWLEDGE_INBOX_PATH:
            self.scheduler.add_job(
                self.folder_watcher.scan_and_ingest,
                trigger=IntervalTrigger(seconds=60),
                id="folder_watcher",
                name="Knowledge Inbox Watcher",
            )

        # Email monitor - every 5 min
        if self.settings.KNOWLEDGE_IMAP_HOST:
            self.scheduler.add_job(
                self.email_monitor.check_inbox,
                trigger=IntervalTrigger(minutes=5),
                id="email_monitor",
                name="Email Document Monitor",
            )

        # Web scraper - daily at 03:00
        self.scheduler.add_job(
            self.web_scraper.scrape_all,
            trigger=CronTrigger(hour=3, minute=0),
            id="web_scraper",
            name="Regulation Scraper",
        )

        # Shift handover - 5 min before each shift
        for hour in [5, 13, 21]:
            self.scheduler.add_job(
                self.handover_generator.generate_handover,
                trigger=CronTrigger(hour=hour, minute=55),
                id=f"handover_{hour}",
                name=f"Shift Handover {hour+1}:00",
                kwargs={"shift": f"{hour+1:02d}:00"},
            )

        # SOP incident analysis - weekly Sunday 02:00
        self.scheduler.add_job(
            self.sop_generator.analyze_incidents,
            trigger=CronTrigger(day_of_week="sun", hour=2),
            id="sop_analysis",
            name="Weekly SOP Analysis",
        )

    def start(self) -> None:
        self.scheduler.start()

    def shutdown(self) -> None:
        self.scheduler.shutdown(wait=False)
```

### FastAPI Lifespan Integration

```python
# app/main.py (lifespan addition)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing startup
    automation = AutomationScheduler(get_settings())
    automation.configure_jobs()
    automation.start()
    yield
    automation.shutdown()
    # ... existing cleanup
```

### Configuration

New environment variables:

```bash
# .env.example additions

# Automation - Folder Watcher
KNOWLEDGE_INBOX_PATH=/data/knowledge-inbox  # Empty = disabled
KNOWLEDGE_INBOX_POLL_SECONDS=60

# Automation - Email Monitor
KNOWLEDGE_IMAP_HOST=              # Empty = disabled
KNOWLEDGE_IMAP_USER=
KNOWLEDGE_IMAP_PASSWORD=
KNOWLEDGE_IMAP_FOLDER=INBOX

# Automation - Web Scraper
KNOWLEDGE_SCRAPER_ENABLED=false
KNOWLEDGE_SCRAPER_SOURCES=likumi,eurlex,riga,ckan,rs  # Comma-separated

# Automation - Handover Notes
KNOWLEDGE_HANDOVER_ENABLED=false
KNOWLEDGE_HANDOVER_SHIFTS=06:00,14:00,22:00

# Automation - SOP Generation
KNOWLEDGE_SOP_ANALYSIS_ENABLED=false
KNOWLEDGE_SOP_MIN_INCIDENTS=3  # Minimum cluster size to trigger SOP draft
```

## Cost Analysis

### Monthly Operating Costs

| Component | LLM Cost | Infra Cost | Total |
|-----------|----------|------------|-------|
| Folder watcher | $0 | $0 | $0 |
| Email monitor | $0 | $0 | $0 |
| Web scraper | $0 | $0 | $0 |
| GTFS sync | $0 | $0 | $0 |
| Auto-domain tagging | ~$0.10 | $0 | $0.10 |
| Handover notes (90/mo) | ~$2.70 | $0 | $2.70 |
| SOP analysis (4/mo) | ~$0.80 | $0 | $0.80 |
| Regulation monitoring | ~$0.40 | $0 | $0.40 |
| SOP scaffolding (10/mo) | ~$0.50 | $0 | $0.50 |
| **Total** | **~$4.50** | **$0** | **~$4.50** |

### Human Time Savings

| Task | Current Manual Time | Automated | Savings |
|------|-------------------|-----------|---------|
| Document uploads | 2 hrs/week | Folder watcher | 8 hrs/month |
| Email attachment processing | 3 hrs/week | Email monitor | 12 hrs/month |
| Regulation tracking | 4 hrs/month | Web scraper | 4 hrs/month |
| Shift handover compilation | 30 min/shift x 15 dispatchers | Auto-generated | 15 hrs/month |
| SOP writing from incidents | 2 hrs/SOP x 4/month | Auto-drafted | 8 hrs/month |
| **Total** | | | **~47 hrs/month** |

**ROI**: $4.50/month automation cost vs ~47 hours/month human time saved.
At average dispatcher hourly rate (~EUR 15/hr), that's ~EUR 705/month value for EUR 4.50 cost.

## Implementation Priority Order

| # | Feature | Effort | Impact | Dependencies |
|---|---------|--------|--------|-------------|
| 1 | Folder watcher | 1 day | High - zero-friction ingestion | `apscheduler` dependency |
| 2 | Shift handover notes | 2 days | High - saves 15 hrs/month | LLM provider, Obsidian vault |
| 3 | Incident-to-SOP pipeline | 2 days | High - saves 8 hrs/month | LLM provider, Obsidian vault |
| 4 | Email monitor | 1.5 days | Medium - saves 12 hrs/month | `aioimaplib`, IMAP credentials |
| 5 | Web scraper | 2 days | Medium - regulatory compliance | `beautifulsoup4`, `lxml` |
| 6 | Regulation change detector | 2 days | Medium - proactive SOP updates | Web scraper (#5) |
| 7 | GTFS doc sync | 1.5 days | Low-Medium - route change awareness | Static cache hook |
| 8 | SOP scaffolding tool | 1 day | Low - on-demand convenience | Existing agent tools |

**Total effort**: ~13 days for the full automation suite.

**Recommended MVP**: Items #1, #2, #3 (5 days total) deliver the highest value:
- Folder watcher eliminates manual uploads entirely
- Handover notes save the most cumulative human time (15 hrs/month across all dispatchers)
- SOP generation creates the most valuable knowledge artifacts

## New Dependencies

```bash
# Required for automation features
uv add apscheduler        # Async job scheduler (all features)
uv add aioimaplib         # Async IMAP client (email monitor)
uv add beautifulsoup4     # HTML parsing (web scraper)
uv add lxml               # Fast HTML/XML parser (web scraper)
```

## Directory Structure

```
app/knowledge/
├── automation/
│   ├── __init__.py
│   ├── scheduler.py           # APScheduler setup and job registration
│   ├── folder_watcher.py      # Directory monitoring and auto-ingestion
│   ├── email_monitor.py       # IMAP inbox polling
│   ├── web_scraper.py         # Regulation scraping with change detection
│   ├── gtfs_sync.py           # GTFS change documentation
│   ├── handover_generator.py  # Shift handover note generation
│   ├── sop_generator.py       # Incident-to-SOP pipeline
│   ├── regulation_monitor.py  # Regulation change impact analysis
│   └── tests/
│       ├── test_folder_watcher.py
│       ├── test_email_monitor.py
│       ├── test_web_scraper.py
│       ├── test_handover_generator.py
│       └── test_sop_generator.py
├── # ... existing knowledge base files
```

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Scraper blocked by website | Respect robots.txt, add User-Agent, rate limit requests |
| IMAP credentials leaked | Store in env vars, never in code, Docker secrets in production |
| LLM generates incorrect SOPs | All SOPs are DRAFTS requiring human review before activation |
| Scheduler job failure | Structured logging + error recovery, skip and retry next cycle |
| Large file ingestion blocks event loop | `asyncio.to_thread()` for CPU-bound work (already used in knowledge base) |
| Duplicate document ingestion | Content hashing deduplication before ingestion |

## Success Metrics

- **Ingestion automation rate**: % of documents auto-ingested vs manually uploaded (target: >80%)
- **SOP coverage**: % of recurring incidents with matching SOPs (target: >60%)
- **Handover completeness**: Dispatcher satisfaction with auto-generated notes (target: >4/5)
- **Regulation freshness**: Days between regulation change and knowledge base update (target: <7 days)
- **False positive rate**: % of auto-generated SOPs rejected during review (target: <20%)
