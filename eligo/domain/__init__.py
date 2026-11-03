"""Lapisan Domain Murni (Domain Layer) Eligo.

Lapisan ini memuat seluruh entitas bisnis, objek nilai (value objects), enumerasi,
fungsi kalkulasi murni, algoritma pengurutan mandiri (Merge Sort), serta protokol abstraksi
repositori.

Batasan Arsitektur Keras (Architectural Invariants):
    - ZERO DEPENDENCY: Dilarang keras mengimpor pustaka pihak ketiga (termasuk `rich`).
    - PURE LOGIC: Tidak boleh melakukan operasi file I/O, database I/O, atau network I/O.
    - DETERMINISTIK: Seluruh perhitungan skor dan sorting harus menghasilkan keluaran
      yang identik untuk masukan data yang sama (bebas efek samping).
"""

from eligo.domain.exceptions import (
    BusinessRuleViolationError,
    CorruptBackupError,
    CsvImportError,
    CsvParsingError,
    EligoError,
    ErrorCode,
    ImportAbortedError,
    IntegrityError,
    PersistenceError,
    QuotaCalculationError,
    RowError,
    ValidationError,
)
from eligo.domain.models import (
    Accreditation,
    Achievement,
    AchievementLevel,
    AppConfig,
    EligibilityStatus,
    Major,
    RankingResult,
    SchoolProfile,
    SchoolType,
    SortKey,
    Student,
    Subject,
    TkaStatus,
)
from eligo.domain.repositories import (
    ConfigRepository,
    SchoolRepository,
    StudentRepository,
)

__all__ = [
    # Enumerasi
    "SchoolType",
    "Accreditation",
    "TkaStatus",
    "AchievementLevel",
    "EligibilityStatus",
    # Dataclass Entitas & Value Objects
    "Subject",
    "Achievement",
    "Major",
    "SchoolProfile",
    "Student",
    "RankingResult",
    "SortKey",
    "AppConfig",
    # Exceptions & Error Handling
    "EligoError",
    "ValidationError",
    "QuotaCalculationError",
    "BusinessRuleViolationError",
    "IntegrityError",
    "PersistenceError",
    "CorruptBackupError",
    "CsvImportError",
    "CsvParsingError",
    "ImportAbortedError",
    "RowError",
    "ErrorCode",
    # Protokol Repositori
    "SchoolRepository",
    "StudentRepository",
    "ConfigRepository",
]
