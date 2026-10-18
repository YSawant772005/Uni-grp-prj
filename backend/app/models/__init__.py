"""All ORM models in dependency order so Alembic sees the full metadata."""
from app.db.base import Base
from app.models import catalogue, evidence, finance, identity, ops, recommendation, reference  # noqa: F401
from app.models.catalogue import (  # noqa: F401
    AdmissionRequirement,
    Campus,
    Program,
    ProgramFee,
    ProgramIntake,
    University,
)
from app.models.evidence import (  # noqa: F401
    FactEvidence,
    FactRecord,
    FactReviewEvent,
    FactVersion,
    Source,
    SourceDocument,
)
from app.models.finance import (  # noqa: F401
    CostScenario,
    CostScenarioItem,
    FundingOpportunity,
    LivingCostFact,
    LoanScenario,
    OfficialRuleResource,
    ProgramOutcomeEvidence,
    RoiScenario,
    Scholarship,
    ScholarshipEligibilityRule,
    ScholarshipProgramLink,
)
from app.models.identity import (  # noqa: F401
    AuditEvent,
    ProfileCountryPreference,
    ProfilePriority,
    Role,
    StudentProfile,
    User,
    UserRole,
)
from app.models.ops import IngestionJob, IngestionJobItem  # noqa: F401
from app.models.recommendation import (  # noqa: F401
    Comparison,
    RecommendationItem,
    RecommendationRuleset,
    RecommendationRun,
    RequirementEvaluation,
    SavedProgram,
)
from app.models.reference import City, Country, Field  # noqa: F401

__all__ = ["Base"]
