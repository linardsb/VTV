"""Business logic for agent skills."""

from __future__ import annotations

from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.shared.schemas import PaginatedResponse, PaginationParams
from app.skills.exceptions import SkillNotFoundError, SkillValidationError
from app.skills.models import AgentSkill
from app.skills.repository import SkillRepository
from app.skills.schemas import (
    TOKEN_BUDGET_CHARS,
    CategoryType,
    SkillCreate,
    SkillResponse,
    SkillUpdate,
)

logger = get_logger(__name__)


class SkillService:
    """Business logic for agent skills."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repository = SkillRepository(db)

    async def get_skill(self, skill_id: int) -> SkillResponse:
        logger.info("skills.fetch_started", skill_id=skill_id)
        skill = await self.repository.get(skill_id)
        if not skill:
            logger.warning("skills.fetch_failed", skill_id=skill_id, reason="not_found")
            raise SkillNotFoundError(f"Skill {skill_id} not found")
        logger.info("skills.fetch_completed", skill_id=skill_id)
        return SkillResponse.model_validate(skill)

    async def list_skills(
        self,
        pagination: PaginationParams,
        *,
        category: str | None = None,
        is_active: bool | None = None,
    ) -> PaginatedResponse[SkillResponse]:
        logger.info(
            "skills.list_started",
            page=pagination.page,
            page_size=pagination.page_size,
        )
        skills = await self.repository.find(
            offset=pagination.offset,
            limit=pagination.page_size,
            category=category,
            is_active=is_active,
        )
        total = await self.repository.count(category=category, is_active=is_active)
        items = [SkillResponse.model_validate(s) for s in skills]
        logger.info("skills.list_completed", result_count=len(items), total=total)
        return PaginatedResponse[SkillResponse](
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    async def create_skill(
        self, data: SkillCreate, created_by_id: int | None = None
    ) -> SkillResponse:
        logger.info("skills.create_started", name=data.name)
        existing = await self.repository.get_by_name(data.name)
        if existing:
            raise SkillValidationError(f"Skill with name '{data.name}' already exists")
        skill = await self.repository.create(data, created_by_id=created_by_id)
        logger.info("skills.create_completed", skill_id=skill.id)
        return SkillResponse.model_validate(skill)

    async def update_skill(self, skill_id: int, data: SkillUpdate) -> SkillResponse:
        logger.info("skills.update_started", skill_id=skill_id)
        skill = await self.repository.get(skill_id)
        if not skill:
            logger.warning("skills.update_failed", skill_id=skill_id, reason="not_found")
            raise SkillNotFoundError(f"Skill {skill_id} not found")
        if data.name is not None and data.name != skill.name:
            existing = await self.repository.get_by_name(data.name)
            if existing:
                raise SkillValidationError(f"Skill with name '{data.name}' already exists")
        skill = await self.repository.update(skill, data)
        logger.info("skills.update_completed", skill_id=skill.id)
        return SkillResponse.model_validate(skill)

    async def delete_skill(self, skill_id: int) -> None:
        logger.info("skills.delete_started", skill_id=skill_id)
        skill = await self.repository.get(skill_id)
        if not skill:
            logger.warning("skills.delete_failed", skill_id=skill_id, reason="not_found")
            raise SkillNotFoundError(f"Skill {skill_id} not found")
        await self.repository.delete(skill)
        logger.info("skills.delete_completed", skill_id=skill_id)

    async def get_active_skills_content(self) -> str:
        """Build combined skill text for agent injection, respecting TOKEN_BUDGET_CHARS.

        Returns:
            Formatted skills content string, or empty string if no active skills.
        """
        skills = await self.repository.list_active()
        if not skills:
            return ""

        parts: list[str] = ["AGENT SKILLS (always-available operational knowledge):\n"]
        total_chars = len(parts[0])
        loaded_count = 0

        for skill in skills:
            section = f"\n## {skill.name}\n{skill.content}\n"
            if total_chars + len(section) > TOKEN_BUDGET_CHARS:
                logger.warning(
                    "skills.budget_exceeded",
                    loaded_count=loaded_count,
                    skipped_name=skill.name,
                )
                break
            parts.append(section)
            total_chars += len(section)
            loaded_count += 1

        logger.info(
            "skills.context_built",
            skill_count=loaded_count,
            total_chars=total_chars,
        )
        return "".join(parts)

    async def seed_default_skills(self) -> list[AgentSkill]:
        """Seed default skills only when table is empty.

        Returns:
            List of created skills, or empty list if table already has data.
        """
        logger.info("skills.seed_started")
        count = await self.repository.count()
        if count > 0:
            logger.info("skills.seed_skipped", existing_count=count)
            return []

        created: list[AgentSkill] = []
        for skill_data in DEFAULT_SKILLS:
            data = SkillCreate(
                name=str(skill_data["name"]),
                description=str(skill_data["description"]),
                content=str(skill_data["content"]),
                category=cast(CategoryType, skill_data["category"]),
                is_active=bool(skill_data.get("is_active", True)),
                priority=int(skill_data.get("priority", 0)),
            )
            skill = await self.repository.create(data)
            created.append(skill)

        logger.info("skills.seed_completed", count=len(created))
        return created


DEFAULT_SKILLS: list[dict[str, str | int | bool]] = [
    {
        "name": "Operaciju Prioritizacija",
        "description": "ATC-inspired priority system for transit incident management",
        "category": "transit_ops",
        "priority": 90,
        "is_active": True,
        "content": (
            "INCIDENT PRIORITY LEVELS (adapted from Air Traffic Control):\n\n"
            "P1 - MAYDAY (Kritisks):\n"
            "- Pakalpojuma partraukums, kas skar 1000+ pasazierus\n"
            "- Liela avārija vai infrastrukturas bojajums\n"
            "- Vadītaja medicinska avārija brauciena laika\n"
            "- Darbiba: Nekavejoties aktivizet visus pieejamos resursus\n\n"
            "P2 - PAN (Steidzams):\n"
            "- Kavesanas >15 min galvenajos marsrutos\n"
            "- Vairaki transportlidzeklu bojajumi vienlaikus\n"
            "- Vadītaja veselibas problemas (ne brauciena laika)\n"
            "- Darbiba: Pieskirt rezerves resursus 10 min laika\n\n"
            "P3 - PRIORITY (Paaugstinats):\n"
            "- Viena transportlidzekla bojajums\n"
            "- Vadītaju trukums nākamajai mainai\n"
            "- Laika apstaklu bridinajums\n"
            "- Darbiba: Planot risinajumu 30 min laika\n\n"
            "P4 - ROUTINE (Ikdienas):\n"
            "- Grafiku pieprasijumi un parbaudes\n"
            "- Nelielas kavesanas <5 min\n"
            "- Datu kvalitates parbaudes\n"
            "- Darbiba: Apstradat standarta kartiba\n\n"
            "P5 - HOLDING (Gaida):\n"
            "- Ilgtermina planosana\n"
            "- Nesteidzama apkope\n"
            "- Statistikas parskati\n"
            "- Darbiba: Ieplānot nākamajai dienai/nedēlai"
        ),
    },
    {
        "name": "Marsrutu Traucejumu Protokols",
        "description": "Step-by-step route disruption response procedure",
        "category": "procedures",
        "priority": 80,
        "is_active": True,
        "content": (
            "MARSRUTU TRAUCEJUMU ATBILDES PROTOKOLS:\n\n"
            "1. NOVERTEJUMS (Assess):\n"
            "   - Izmantot query_bus_status lai noteiktu ietekmi\n"
            "   - Noteikt skarto marsrutu skaitu un pasazieru ietekmi\n"
            "   - Klasificet pec prioritates (skat. Operaciju Prioritizacija)\n\n"
            "2. RESURSU PARBAUDE (Resources):\n"
            "   - Izmantot check_driver_availability lai parauditu pieejamos vadītajus\n"
            "   - Parbadit rezerves transportlidzeklu statusu\n"
            "   - Noteikt tuvako depo ar pieejamiem resursiem\n\n"
            "3. NOTIKUMU REGISTRACIJA (Log):\n"
            "   - Izveidot operacionalo notikumu ar pilnu aprakstu\n"
            "   - Iekaļut: laiks, skartos marsrutus, pasazieru ietekmi\n"
            "   - Pievienot prioritates limeni un kategoriju\n\n"
            "4. PARVIRZISANA (Reroute):\n"
            "   - Analizet alternativos marsrutus\n"
            "   - Izmantot search_stops lai atrastu tuvakās pieturas\n"
            "   - Iesakat pagaidu marsrutu izmainas\n\n"
            "5. ESKALACIJA (Escalate):\n"
            "   - P1/P2: Nekavējoties zinot vadibai\n"
            "   - P3: Zinot ja nav atrisinats 30 min laika\n"
            "   - P4/P5: Iekļaut dienas parskātā\n\n"
            "6. APSTIPRINAJUMS (Resolve):\n"
            "   - Apstiprinat pakalpojuma atjaunosanu\n"
            "   - Atjaunot notikuma ierakstu ar risinajumu\n"
            "   - Dokumentet macibas turpmākai uzlabosanai"
        ),
    },
    {
        "name": "Mainas Nodosana",
        "description": "Dispatcher shift handover checklist for consistent operations",
        "category": "procedures",
        "priority": 70,
        "is_active": True,
        "content": (
            "MAINAS NODOSANAS KONTROLSARAKSTS:\n\n"
            "1. AKTĪVIE NOTIKUMI:\n"
            "   - Uzskaitit visus neatrisinatos notikumus\n"
            "   - Noradit prioritates limeni katram\n"
            "   - Aprakstit veiktas darbibas un gaidamos soļus\n\n"
            "2. MARSRUTU STATUSS:\n"
            "   - Marsruti ar kavesanam >5 min\n"
            "   - Marsruti ar izslugtiem transportlidzekliem\n"
            "   - Pagaidu marsrutu izmainas\n\n"
            "3. VADITAJU STATUSS:\n"
            "   - Vadītaji, kas tuvojas darba laika limitam\n"
            "   - Pieteiktas prombūtnes nākamajai mainai\n"
            "   - Vadītaji ar veselibas ierobezojumiem\n\n"
            "4. TRANSPORTLIDZEKLU STATUSS:\n"
            "   - Transportlidzekli apkope vai remonta\n"
            "   - Zemais degvielas/uzlades limenis\n"
            "   - Planota apkope nākamajām 24h\n\n"
            "5. AREJI FAKTORI:\n"
            "   - Laika apstaklu prognoze\n"
            "   - Planoti publiski pasakumi\n"
            "   - Celu buvdarbi vai slēgsanas\n\n"
            "6. GAIDOSIE UZDEVUMI:\n"
            "   - Nepabeigti administrativi uzdevumi\n"
            "   - Gaidami lenumi vai apstiprinajumi\n"
            "   - Plānoto parbaudi grafiki\n\n"
            "IENĀKOSAIS DISPECHERS: Apstiprinat informācijas saņemsanu (read-back)"
        ),
    },
    {
        "name": "GTFS Datu Kvalitate",
        "description": "GTFS import validation checks and data quality rules",
        "category": "reporting",
        "priority": 60,
        "is_active": True,
        "content": (
            "GTFS DATU KVALITATES PARBAUDES:\n\n"
            "STRUKTURALAS PARBAUDES:\n"
            "- Katram marsrutam jabut vismaz 1 reisam\n"
            "- stop_times jabut monotoni augosam stop_sequence\n"
            "- calendar jabut vismaz 30 dienu parklajumam\n"
            "- Nav bārenu ierakstu (reisi bez marsruta, pieturas bez reisiem)\n\n"
            "KOORDINATU VALIDACIJA (Riga):\n"
            "- Platums: 56.8 - 57.1 (N)\n"
            "- Garums: 23.9 - 24.4 (E)\n"
            "- Pieturas arpus si diapazona: bridinajums\n\n"
            "TEMPORALA VALIDACIJA:\n"
            "- departure_time >= arrival_time katrai pieturai\n"
            "- Stundas var parsnigt 24 (GTFS spec - nakts reisi)\n"
            "- Minutes < 60, Sekundes < 60\n"
            "- Brauciena ilgums: bridinajums ja >3h vienam reisam\n\n"
            "INTEGRITATES PARBAUDES:\n"
            "- Unikals (trip_id, stop_sequence) pāris\n"
            "- Unikals (calendar_id, date) pāris\n"
            "- FK atsauces: stop_id eksiste stops tabula\n"
            "- FK atsauces: route_id eksiste routes tabula\n\n"
            "IMPORTA DROSIBA:\n"
            "- ZIP faila limenis: 500MB maksimums\n"
            "- Kompresijas attieciba: max 100:1\n"
            "- Failu nosaukumu sanitizacija pret path traversal"
        ),
    },
    {
        "name": "Latviesu Terminu Paplasinajums",
        "description": "Extended Latvian transit terminology and abbreviations",
        "category": "glossary",
        "priority": 50,
        "is_active": True,
        "content": (
            "PAPLASINATA TERMINOLOGIJA:\n\n"
            "DISPECERU TERMINI:\n"
            "- dispechers / dispečere - dispatcher\n"
            "- maina - shift\n"
            "- rezerves autobuss - backup bus\n"
            "- depo - depot/garage\n"
            "- izbraukuma laiks - departure time\n"
            "- beigu pietura - terminal stop\n"
            "- starppieturu attālums - stop spacing\n"
            "- brauciena laiks - travel time\n"
            "- pasazieru plūsma - passenger flow\n\n"
            "INCIDENTU KODI:\n"
            "- AT - autobusu traucejums (bus disruption)\n"
            "- RS - reisa atcelšana (trip cancellation)\n"
            "- AS - avārijas situācija (emergency situation)\n"
            "- GTFS-RT - reāllaika datu plūsma (real-time data feed)\n"
            "- AVL - automātiskā transportlīdzekļu atrašanās vieta\n\n"
            "PASAZIERU PAZINOJUMI:\n"
            "- Ludzam atvainoties par sagadītajām neērtībām\n"
            "- Marsruts [X] šobrīd kursē ar kavēšanos\n"
            "- Lūdzu izmantojiet alternatīvo marsrutu [Y]\n"
            "- Pakalpojums ir atjaunots\n\n"
            "SAĪSINĀJUMI:\n"
            "- RS - Rigas Satiksme\n"
            "- AT - autotransports\n"
            "- VTV - Vienota Transporta Vadība\n"
            "- SIA - sabiedrība ar ierobežotu atbildību"
        ),
    },
]
