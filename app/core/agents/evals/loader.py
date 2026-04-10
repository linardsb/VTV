"""YAML loader for synthetic agent eval cases (AI-7.1).

Parses ``app/core/agents/evals/cases/{transit,knowledge,vault}.yaml`` into
immutable :class:`EvalCase` objects. Mirrors the security posture of
:mod:`app.core.agents.skill_loader` exactly:

* ``yaml.safe_load`` only.
* Path sandbox via :meth:`pathlib.Path.is_relative_to` after
  :meth:`pathlib.Path.resolve` on both sides.
* Fail-open: any read/parse failure logs ``agent.evals.loader.<reason>``
  at WARNING and returns ``None``/``[]``. Never raises into callers — eval
  infra must not crash production code that imports it.
* No raw prompts logged at INFO; only file paths and counts.
"""

# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Final

import yaml

from app.core.agents.evals.schemas import EvalCase, QualityCriterion
from app.core.logging import get_logger

logger = get_logger(__name__)


_CASES_ROOT: Final[Path] = Path(__file__).parent / "cases"
_VALID_DOMAIN_NAMES: Final[tuple[str, ...]] = ("transit", "knowledge", "vault")


def _parse_yaml_mapping(raw: str) -> dict[str, Any] | None:
    """Parse YAML into a ``dict[str, Any]`` or return ``None`` on failure.

    Mirrors :func:`app.core.agents.skill_loader._parse_yaml_mapping`. Uses
    ``yaml.safe_load`` and rebuilds the result with ``str(key)`` so the
    downstream consumer always sees string-keyed data.
    """
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError:
        return None
    if not isinstance(parsed, dict):
        return None
    return {str(key): value for key, value in parsed.items()}


def _build_criteria(raw_list: object) -> tuple[QualityCriterion, ...] | None:
    """Coerce a YAML list into a tuple of :class:`QualityCriterion`.

    Returns ``None`` on any structural failure (not a list, items not
    dicts, or :class:`QualityCriterion` validation raises).
    """
    if not isinstance(raw_list, list):
        return None

    criteria: list[QualityCriterion] = []
    for item in raw_list:
        if not isinstance(item, dict):
            return None
        name_raw = item.get("name")
        desc_raw = item.get("description")
        if name_raw is None or desc_raw is None:
            return None
        try:
            criteria.append(QualityCriterion(name=str(name_raw), description=str(desc_raw)))
        except ValueError:
            return None
    return tuple(criteria)


def _build_case(raw: dict[str, Any], file_path: Path) -> EvalCase | None:
    """Coerce a raw mapping into an :class:`EvalCase` or log + return None."""
    case_id_raw = raw.get("id")
    case_id = str(case_id_raw) if case_id_raw is not None else "<unknown>"

    prompt_raw = raw.get("prompt")
    language_raw = raw.get("language")
    expected_domain_raw = raw.get("expected_domain")

    if prompt_raw is None or language_raw is None or expected_domain_raw is None:
        logger.warning(
            "agent.evals.loader.missing_required_field",
            path=str(file_path),
            case_id=case_id,
        )
        return None

    expected_tools_raw = raw.get("expected_tools", [])
    if not isinstance(expected_tools_raw, list):
        logger.warning(
            "agent.evals.loader.expected_tools_not_a_list",
            path=str(file_path),
            case_id=case_id,
        )
        return None
    expected_tools = tuple(str(t) for t in expected_tools_raw if t is not None)

    criteria = _build_criteria(raw.get("quality_criteria"))
    if criteria is None:
        logger.warning(
            "agent.evals.loader.invalid_quality_criteria",
            path=str(file_path),
            case_id=case_id,
        )
        return None

    notes_raw = raw.get("notes", "")
    notes = str(notes_raw) if notes_raw is not None else ""

    try:
        return EvalCase(
            id=str(case_id_raw),
            prompt=str(prompt_raw),
            language=str(language_raw),
            expected_domain=str(expected_domain_raw),
            expected_tools=expected_tools,
            quality_criteria=criteria,
            notes=notes,
        )
    except ValueError as exc:
        logger.warning(
            "agent.evals.loader.case_validation_failed",
            path=str(file_path),
            case_id=case_id,
            error=str(exc),
        )
        return None


def parse_eval_file(path: Path) -> list[EvalCase] | None:
    """Parse one YAML eval file into a list of :class:`EvalCase` objects.

    Args:
        path: Absolute path to a ``{domain}.yaml`` eval file.

    Returns:
        A list of cases on success (possibly empty). Returns ``None`` if
        the whole file is unusable: read error, YAML parse error, top
        level not a dict, missing ``cases`` key, or ``cases`` not a list.
        Individual case validation errors are logged per-case but do
        NOT fail the whole file — bad cases are skipped and good ones
        returned.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        logger.warning("agent.evals.loader.read_failed", path=str(path), exc_info=True)
        return None

    parsed = _parse_yaml_mapping(raw)
    if parsed is None:
        logger.warning(
            "agent.evals.loader.yaml_parse_failed_or_not_mapping",
            path=str(path),
        )
        return None

    cases_raw = parsed.get("cases")
    if cases_raw is None:
        logger.warning("agent.evals.loader.missing_cases_key", path=str(path))
        return None
    if not isinstance(cases_raw, list):
        logger.warning("agent.evals.loader.cases_not_a_list", path=str(path))
        return None

    cases: list[EvalCase] = []
    for entry in cases_raw:
        if not isinstance(entry, dict):
            logger.warning("agent.evals.loader.case_not_a_mapping", path=str(path))
            continue
        coerced = {str(k): v for k, v in entry.items()}
        case = _build_case(coerced, path)
        if case is not None:
            cases.append(case)
    return cases


def load_eval_cases(
    domain: str,
    *,
    cases_root: Path | None = None,
) -> list[EvalCase]:
    """Load all cases for one domain from ``<cases_root>/<domain>.yaml``.

    Path-sandboxed via :meth:`pathlib.Path.is_relative_to`. Returns ``[]``
    on missing file or any failure (fail-open).

    Args:
        domain: Subdirectory name (``transit``, ``knowledge``, ``vault``).
        cases_root: Optional override; defaults to the package
            ``cases/`` directory.

    Returns:
        List of :class:`EvalCase` objects (possibly empty).
    """
    effective_root = cases_root if cases_root is not None else _CASES_ROOT
    if not effective_root.is_dir():
        return []

    try:
        root_resolved = effective_root.resolve()
    except OSError:
        logger.warning(
            "agent.evals.loader.resolve_failed",
            path=str(effective_root),
            exc_info=True,
        )
        return []

    domain_file = effective_root / f"{domain}.yaml"
    try:
        domain_resolved = domain_file.resolve()
    except OSError:
        logger.warning(
            "agent.evals.loader.resolve_failed",
            path=str(domain_file),
            exc_info=True,
        )
        return []

    if not domain_resolved.is_relative_to(root_resolved):
        logger.warning("agent.evals.loader.path_escaped", path=str(domain_file))
        return []

    if not domain_resolved.is_file():
        return []

    parsed = parse_eval_file(domain_resolved)
    if parsed is None:
        return []
    return parsed


def load_all_cases(
    *,
    cases_root: Path | None = None,
) -> dict[str, list[EvalCase]]:
    """Load all three domain files into a mapping keyed by domain name.

    Logs the per-domain count and total. Detects duplicate ``id`` values
    across the suite — duplicates are reported via the
    ``agent.evals.loader.duplicate_ids`` warning but kept in the result
    (loader is fail-open; the eval runner can decide whether to dedupe).

    Args:
        cases_root: Optional override; defaults to the package
            ``cases/`` directory.

    Returns:
        Mapping ``{"transit": [...], "knowledge": [...], "vault": [...]}``.
    """
    suite: dict[str, list[EvalCase]] = {}
    for domain in _VALID_DOMAIN_NAMES:
        suite[domain] = load_eval_cases(domain, cases_root=cases_root)

    counts = {domain: len(cases) for domain, cases in suite.items()}
    total = sum(counts.values())

    all_ids = [case.id for cases in suite.values() for case in cases]
    id_counts = Counter(all_ids)
    duplicates = sorted(case_id for case_id, count in id_counts.items() if count > 1)
    if duplicates:
        logger.warning(
            "agent.evals.loader.duplicate_ids",
            duplicates=duplicates,
        )

    logger.info(
        "agent.evals.loader.loaded",
        counts=counts,
        total=total,
        duplicate_count=len(duplicates),
    )
    return suite


__all__ = [
    "load_all_cases",
    "load_eval_cases",
    "parse_eval_file",
]
