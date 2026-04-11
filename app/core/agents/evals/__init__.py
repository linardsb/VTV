"""Agent eval framework (AI-7.x)."""

from app.core.agents.evals.judge import LLMJudge
from app.core.agents.evals.regression import (
    check_regression,
    generate_baseline,
    read_baseline,
    write_baseline,
)
from app.core.agents.evals.runner import EvalRunner, EvalTrace
from app.core.agents.evals.schemas import (
    BaselineReport,
    CriterionBaseline,
    JudgeVerdict,
    RegressionFinding,
    RegressionReport,
    SuiteJudgement,
)

__all__ = [
    "BaselineReport",
    "CriterionBaseline",
    "EvalRunner",
    "EvalTrace",
    "JudgeVerdict",
    "LLMJudge",
    "RegressionFinding",
    "RegressionReport",
    "SuiteJudgement",
    "check_regression",
    "generate_baseline",
    "read_baseline",
    "write_baseline",
]
