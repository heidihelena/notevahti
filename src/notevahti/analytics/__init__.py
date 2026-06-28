"""Stage-1 evidence analytics for NoteVahti.

This subpackage is SEPARATE from the deterministic validation core. It computes reportable agreement
and (later) discrimination/calibration statistics for the open empirical question — does the
validity flag predict true abstraction errors? — so a Stage-1 study can be reported against
TRIPOD+AI.

These are standard statistics, not a NoteVahti contribution, and they produce *evidence*, never a
guarantee. Functions are deterministic: any resampling takes an explicit integer seed.
"""

from .agreement import OrdinalAgreement, ordinal_agreement
from .discrimination import (
    FlagDiscrimination,
    ScoreDiscrimination,
    flag_discrimination,
    score_discrimination,
)

__all__ = [
    "FlagDiscrimination",
    "OrdinalAgreement",
    "ScoreDiscrimination",
    "flag_discrimination",
    "ordinal_agreement",
    "score_discrimination",
]
