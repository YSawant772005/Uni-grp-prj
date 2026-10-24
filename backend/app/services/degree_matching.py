"""Conservative matching of named Master's award titles.

The 98 registered titles and abbreviations come from the user's reference PDF.
A degree designation is NOT a specialization. When a program name does not
unambiguously identify its award, do not treat it as an exact match.
"""
from __future__ import annotations

import re

# (Canonical full degree title, accepted abbreviations)
_DEGREES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ('Master of Arts', ('MA',)), 
    ('Master of Science', ('MS', 'MSc',)), 
    ('Master of Research', ('MRes',)), 
    ('Master of Philosophy', ('MPhil',)), 
    ('Master of Studies', ('MSt',)), 
    ('Master of Letters', ('MLitt',)), 
    ('Master of Arts in Liberal Studies', ('MALS',)), 
    ('Master of Advanced Studies', ('MAS',)), 
    ('Master of Professional Studies', ('MPS',)), 
    ('Master of Applied Science', ('MAppSc',)), 
    ('Master of Science and Technology', ('MScTech',)), 
    ('Master of Business Administration', ('MBA',)), 
    ('Executive Master of Business Administration', ('EMBA',)), 
    ('Master in Management', ('MIM', 'MiM',)), 
    ('Master of Commerce', ('MCom',)), 
    ('Master of Accountancy', ('MAcc', 'MAcct',)), 
    ('Master of Finance', ('MFin',)), 
    ('Master of Financial Engineering', ('MFE',)), 
    ('Master of Financial Management', ('MFM',)), 
    ('Master of Management', ('MMgt',)), 
    ('Master of Human Resource Management', ('MHRM',)), 
    ('Master of International Business', ('MIB',)), 
    ('Master of Project Management', ('MPM',)), 
    ('Master of Entrepreneurship', ('MEnt',)), 
    ('Master of Science in Economics', ('MScEcon',)), 
    ('Master of Engineering', ('MEng',)), 
    ('Master of Technology', ('MTech',)), 
    ('Master of Computer Applications', ('MCA',)), 
    ('Master of Information Technology', ('MIT',)), 
    ('Master of Information Systems', ('MIS',)), 
    ('Master of Computer Science', ('MCS',)), 
    ('Master of Software Engineering', ('MSE',)), 
    ('Master of Architecture', ('MArch',)), 
    ('Master of Landscape Architecture', ('MLA',)), 
    ('Master of Urban Design', ('MUD',)), 
    ('Master of Urban Planning', ('MUP',)), 
    ('Master of Planning', ('MPlan',)), 
    ('Master of Construction Management', ('MConstrM',)), 
    ('Master of Design', ('MDes',)), 
    ('Master of Public Health', ('MPH',)), 
    ('Master of Health Administration', ('MHA',)), 
    ('Master of Health Science', ('MHSc',)), 
    ('Master of Science in Nursing', ('MSN',)), 
    ('Master of Nursing', ('MN',)), 
    ('Master of Nursing Management', ('MNM',)), 
    ('Master of Physiotherapy', ('MPT',)), 
    ('Master of Occupational Therapy', ('MOT',)), 
    ('Master of Pharmacy', ('MPharm',)), 
    ('Master of Clinical Pharmacy', ('MClinPharm',)), 
    ('Master of Dental Surgery', ('MDS',)), 
    ('Magister Chirurgiae / Master of Chirurgiae', ('MCh',)), 
    ('Master of Medicine', ('MMed',)), 
    ('Master of Medical Science', ('MMedSc',)), 
    ('Master of Optometry', ('MOptom',)), 
    ('Master of Veterinary Medicine', ('MVM',)), 
    ('Master of Veterinary Science', ('MVSc',)), 
    ('Master of Science in Public Health', ('MScPH',)), 
    ('Master of Laws', ('LLM',)), 
    ('Master of Comparative Law', ('MCL',)), 
    ('Master of Jurisprudence', ('MJur',)), 
    ('Master of Legal Studies', ('MLS',)), 
    ('Master of Public Administration', ('MPA',)), 
    ('Master of Public Policy', ('MPP',)), 
    ('Master of International Affairs', ('MIA',)), 
    ('Master of International Relations', ('MIR',)), 
    ('Master of Public and Social Administration', ('MPSA',)), 
    ('Master of Social Work', ('MSW',)), 
    ('Master of Criminology', ('MCrim',)), 
    ('Master of Development Studies', ('MDevS',)), 
    ('Master of Education', ('MEd',)), 
    ('Master of Teaching', ('MTeach',)), 
    ('Master of Arts in Teaching', ('MAT',)), 
    ('Master of Science in Education', ('MSEd',)), 
    ('Master of Fine Arts', ('MFA',)), 
    ('Master of Music', ('MMus',)), 
    ('Master of Performance', ('MPerf',)), 
    ('Master of Film', ('MFilm',)), 
    ('Master of Journalism', ('MJournalism',)), 
    ('Master of Communication', ('MComm',)), 
    ('Master of Divinity', ('MDiv',)), 
    ('Master of Theological Studies', ('MTS',)), 
    ('Master of Theology', ('MTh',)), 
    ('Master of Sacred Theology', ('STM',)), 
    ('Master of Science in Agriculture', ('MScAgr',)), 
    ('Master of Agriculture', ('MAg',)), 
    ('Master of Agribusiness', ('MAB',)), 
    ('Master of Forestry', ('MF',)), 
    ('Master of Environment', ('MEnv',)), 
    ('Master of Environmental Management', ('MEM',)), 
    ('Master of Environmental Studies', ('MES',)), 
    ('Master of Natural Resources', ('MNR',)), 
    ('Master of Marine Science', ('MMarSc',)), 
    ('Master of Science in Geographic Information Science', ('MScGIS',)), 
    ('Master of Library and Information Science', ('MLIS',)), 
    ('Master of Library Science', ('MLS',)), 
    ('Master of Information Management', ('MIM',)), 
    ('Master of Hospitality Management', ('MHM',)), 
    ('Master of Tourism Management', ('MTM',)), 
)


def _prefix_pattern(label: str) -> re.Pattern[str]:
    """Accept minor punctuation variations (M.Tech / M Tech / MTech)."""
    chars = [re.escape(c) for c in label if c.isalnum()]
    return re.compile(r"^\s*" + r"[\s.\-]*".join(chars) + r"(?=$|[^a-zA-Z0-9])", re.IGNORECASE)


_PREFIXES = tuple((title, _prefix_pattern(alias))
                  for title, abbreviations in _DEGREES
                  for alias in (title, *abbreviations))
_KNOWN_TITLES = {title for title, _ in _DEGREES}


def recognized_award(program_name: str) -> str | None:
    """Return only an unambiguous degree title detected at the start of the program."""
    matches = [(match.end(), title)
               for title, pattern in _PREFIXES
               if (match := pattern.match(program_name or ""))]
    if not matches:
        return None
    longest = max(size for size, _ in matches)
    winners = {title for size, title in matches if size == longest}
    return next(iter(winners)) if len(winners) == 1 else None


def is_known_award(title: str) -> bool:
    return title in _KNOWN_TITLES


def exact_award_match(selected_title: str, program_name: str) -> bool:
    return is_known_award(selected_title) and recognized_award(program_name) == selected_title
