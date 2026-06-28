"""Deterministic, offline synthetic lung-cancer MDT corpus generator for NoteVahti.

The three modalities mirror Heidi's real NTOG tools (field sets/sections/options taken from the live
pages, June 2026):
  - free text          -> ntog.org/mdt.html              (open-text MDT form)   — fi, sv, nb, da, is, en
  - semistructured_en  -> ntog.org/mdt-structured-mini.html (labelled sections)  — English
  - structured_en      -> ntog.org/mdt-structured-v3_1.html (coded key:value)    — English

Why template-based, not an LLM: a validation harness needs a KNOWN ground truth *with exact source
spans*. This generator builds each note by concatenation and records the precise char span of every
gold value it inserts — the oracle a provenance test requires. Seeded, so fully reproducible and
PHI-free by construction.

Each case carries fields {name: {value, span, canonical, field_type}}: `value` is the localized
surface form present in the note (for provenance); `canonical` is the controlled value (for
cross-language / cross-modality agreement). Staging codes, PD-L1 and driver alterations are written
in their conventional (English/universal) form even in Nordic notes, as in real practice.

Output wording matches the documented field STRUCTURE of the tools, not a byte-captured summary
string (the summaries are JS-generated). Synthetic only; native clinical review recommended.

Usage:  PYTHONPATH=src python3 scripts/gen_corpus.py --n 500 --out corpus
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import re
import zlib

# --------------------------------------------------------------------------- clinical schema

HISTOLOGIES = ["adenocarcinoma", "squamous cell carcinoma", "small cell carcinoma", "nsclc_nos"]
T_BY_SIZE = [(10, "T1a"), (20, "T1b"), (30, "T1c"), (50, "T2a"), (70, "T2b"), (99, "T3")]
N_STAGES = ["N0", "N1", "N2", "N3"]
DRIVERS = [
    "EGFR exon 19 deletion",
    "EGFR L858R",
    "ALK rearrangement",
    "ROS1 rearrangement",
    "BRAF V600E",
    "KRAS G12C",
    "MET exon 14 skipping",
    "RET fusion",
    "none",
]
TARGETABLE = {
    "EGFR exon 19 deletion",
    "EGFR L858R",
    "ALK rearrangement",
    "ROS1 rearrangement",
    "BRAF V600E",
    "MET exon 14 skipping",
    "RET fusion",
}
PDL1_TPS = [0, 1, 5, 20, 50, 80, 90]


def _t_from_size(size_mm: int, t4: bool) -> str:
    if t4:
        return "T4"
    for hi, t in T_BY_SIZE:
        if size_mm <= hi:
            return t
    return "T3"


def _stage_group(t: str, n: str, m: str) -> str:
    if m in ("M1a", "M1b"):
        return "IVA"
    if m == "M1c":
        return "IVB"
    tnum = {"T1a": 1, "T1b": 1, "T1c": 1, "T2a": 2, "T2b": 2, "T3": 3, "T4": 4}[t]
    if n == "N3":
        return "IIIC" if tnum >= 3 else "IIIB"
    if n == "N2":
        return "IIIB" if tnum >= 3 else "IIIA"
    if n == "N1":
        return "IIIA" if tnum == 4 else "IIB"
    return {1: "IA", 2: "IB", 3: "IIB", 4: "IIIA"}[tnum] if t != "T2b" else "IIA"


def _intent(case: dict) -> str:
    if case["ps"] >= 3:
        return "best supportive care"
    g = case["stage_group"]
    if g in ("IA", "IB", "IIA", "IIB"):
        return "curative"
    if g == "IIIA":
        return "potentially curative"
    if g in ("IIIB", "IIIC"):
        return "curative" if not case["inoperable"] else "potentially curative"
    return "life-prolonging palliative"


def _treatment(case: dict) -> str:
    if case["ps"] >= 3:
        return "best supportive care"
    if case["histology"] == "small cell carcinoma":
        return "concurrent chemoradiotherapy" if case["m"] == "M0" else "chemo-immunotherapy"
    g = case["stage_group"]
    if g in ("IA", "IB"):
        return "SABR" if case["inoperable"] else "lobectomy"
    if g in ("IIA", "IIB"):
        return "lobectomy"
    if g in ("IIIA", "IIIB", "IIIC"):
        return "concurrent chemoradiotherapy"
    if case["driver"] in TARGETABLE:
        return "targeted therapy"
    if case["pdl1"] >= 50:
        return "immunotherapy"
    return "chemo-immunotherapy"


def sample_case(rng: random.Random) -> dict:
    histology = rng.choice(HISTOLOGIES)
    size = rng.randint(8, 90)
    t = _t_from_size(size, rng.random() < 0.12)
    n = rng.choices(N_STAGES, weights=[5, 2, 3, 2])[0]
    m = rng.choices(["M0", "M1a", "M1b", "M1c"], weights=[6, 1, 1, 2])[0]
    case = {
        "age": rng.randint(45, 88),
        "sex": rng.choice(["M", "F"]),
        "smoking": rng.choice(["never", "former", "current"]),
        "pack_years": rng.choice([0, 10, 20, 30, 40, 50]),
        "side": rng.choice(["right", "left"]),
        "lobe": rng.choice(["upper", "middle", "lower"]),
        "size_mm": size,
        "histology": histology,
        "t": t,
        "n": n,
        "m": m,
        "driver": "none" if histology == "small cell carcinoma" else rng.choice(DRIVERS),
        "pdl1": rng.choice(PDL1_TPS),
        "ps": rng.choices([0, 1, 2, 3], weights=[4, 4, 2, 1])[0],
        "fvc": rng.randint(60, 110),
        "fev1": rng.randint(45, 105),
        "dlco": rng.randint(40, 100),
        "g8": rng.randint(8, 17),
        "inoperable": rng.random() < 0.3,
        "tnm_edition": "9th",
    }
    if case["lobe"] == "middle" and case["side"] == "left":
        case["lobe"] = "upper"
    case["stage_group"] = _stage_group(t, n, m)
    case["ctnm"] = f"c{t} {n} {m}"
    case["ctnm_canonical"] = f"c{t}{n}{m}"
    # pre-MDT cTNM: a plausibly under-staged value (lower N, M0) present in the note. When it differs
    # from the post-MDT stage it is the canonical "present-but-wrong" extraction target.
    n_idx = max(0, N_STAGES.index(n) - (1 if rng.random() < 0.7 else 0))
    before_n = N_STAGES[n_idx]
    before_m = "M0"
    case["ctnm_before"] = f"c{t} {before_n} {before_m}"
    case["ctnm_before_canonical"] = f"c{t}{before_n}{before_m}"
    case["stage_differs"] = case["ctnm_before"] != case["ctnm"]
    case["intent"] = _intent(case)
    case["treatment"] = _treatment(case)
    case["pdl1_surface_free"] = f"PD-L1 TPS {case['pdl1']}%"
    return case


# --------------------------------------------------------------------------- localisation

HISTOLOGY_L = {
    "adenocarcinoma": {
        "fi": "adenokarsinooma",
        "sv": "adenokarcinom",
        "nb": "adenokarsinom",
        "da": "adenokarcinom",
        "is": "kirtilfrumukrabbamein",
        "en": "adenocarcinoma",
    },
    "squamous cell carcinoma": {
        "fi": "levyepiteelikarsinooma",
        "sv": "skivepitelcancer",
        "nb": "plateepitelkarsinom",
        "da": "planocellulært karcinom",
        "is": "flöguþekjukrabbamein",
        "en": "squamous cell carcinoma",
    },
    "small cell carcinoma": {
        "fi": "pienisoluinen karsinooma",
        "sv": "småcellig lungcancer",
        "nb": "småcellet karsinom",
        "da": "småcellet karcinom",
        "is": "smáfrumukrabbamein",
        "en": "small cell carcinoma",
    },
    "nsclc_nos": {
        "fi": "ei-pienisoluinen karsinooma NOS",
        "sv": "icke-småcellig lungcancer UNS",
        "nb": "ikke-småcellet karsinom UNS",
        "da": "ikke-småcellet karcinom UNS",
        "is": "ekki-smáfrumukrabbamein NOS",
        "en": "non-small cell carcinoma NOS",
    },
}
TREATMENT_L = {
    "SABR": {lang: "SABR" for lang in ["fi", "sv", "nb", "da", "is", "en"]},
    "lobectomy": {
        "fi": "lobektomia",
        "sv": "lobektomi",
        "nb": "lobektomi",
        "da": "lobektomi",
        "is": "blaðnám",
        "en": "lobectomy",
    },
    "concurrent chemoradiotherapy": {
        "fi": "konkomitantti kemosädehoito",
        "sv": "konkomitant kemoradioterapi",
        "nb": "konkomitant kjemoradioterapi",
        "da": "konkomitant kemoradioterapi",
        "is": "samhliða krabbameinslyfja- og geislameðferð",
        "en": "concurrent chemoradiotherapy",
    },
    "targeted therapy": {
        "fi": "täsmälääkehoito",
        "sv": "målriktad behandling",
        "nb": "målrettet behandling",
        "da": "målrettet behandling",
        "is": "marksækin meðferð",
        "en": "targeted therapy",
    },
    "immunotherapy": {
        "fi": "immunoterapia",
        "sv": "immunterapi",
        "nb": "immunterapi",
        "da": "immunterapi",
        "is": "ónæmismeðferð",
        "en": "immunotherapy",
    },
    "chemo-immunotherapy": {
        "fi": "kemoimmunoterapia",
        "sv": "kemoimmunterapi",
        "nb": "kjemoimmunterapi",
        "da": "kemoimmunterapi",
        "is": "krabbameinslyfja- og ónæmismeðferð",
        "en": "chemo-immunotherapy",
    },
    "best supportive care": {
        "fi": "oireenmukainen hoito",
        "sv": "bästa understödjande vård",
        "nb": "best mulig støttebehandling",
        "da": "bedste understøttende behandling",
        "is": "líknandi meðferð",
        "en": "best supportive care",
    },
}
INTENT_L = {
    "curative": {
        "fi": "kuratiivinen",
        "sv": "kurativ",
        "nb": "kurativ",
        "da": "kurativ",
        "is": "læknandi",
        "en": "curative",
    },
    "potentially curative": {
        "fi": "mahdollisesti kuratiivinen",
        "sv": "potentiellt kurativ",
        "nb": "potensielt kurativ",
        "da": "potentielt kurativ",
        "is": "mögulega læknandi",
        "en": "potentially curative",
    },
    "life-prolonging palliative": {
        "fi": "elämää pidentävä palliatiivinen",
        "sv": "livsförlängande palliativ",
        "nb": "livsforlengende palliativ",
        "da": "livsforlængende palliativ",
        "is": "líflengjandi líknandi",
        "en": "life-prolonging palliative",
    },
    "best supportive care": {
        "fi": "paras oireenmukainen hoito",
        "sv": "bästa understödjande vård",
        "nb": "best mulig støttebehandling",
        "da": "bedste understøttende behandling",
        "is": "líknandi meðferð",
        "en": "best supportive care",
    },
}
DRIVER_NONE_L = {
    "fi": "ei toimintakelpoisia muutoksia",
    "sv": "inga targeterbara förändringar",
    "nb": "ingen målbare endringer",
    "da": "ingen targeterbare forandringer",
    "is": "engar marktækar breytingar",
    "en": "no actionable alteration",
}
SEX_L = {
    "M": {"fi": "mies", "sv": "man", "nb": "mann", "da": "mand", "is": "karl", "en": "man"},
    "F": {
        "fi": "nainen",
        "sv": "kvinna",
        "nb": "kvinne",
        "da": "kvinde",
        "is": "kona",
        "en": "woman",
    },
}
SMOKING_L = {
    "never": {
        "fi": "ei koskaan tupakoinut",
        "sv": "aldrig rökt",
        "nb": "aldri røkt",
        "da": "aldrig røget",
        "is": "hefur aldrei reykt",
        "en": "never-smoker",
    },
    "former": {
        "fi": "entinen tupakoitsija",
        "sv": "f.d. rökare",
        "nb": "tidligere røyker",
        "da": "tidligere ryger",
        "is": "fyrrum reykingamaður",
        "en": "former smoker",
    },
    "current": {
        "fi": "tupakoiva",
        "sv": "aktiv rökare",
        "nb": "aktiv røyker",
        "da": "aktiv ryger",
        "is": "reykingamaður",
        "en": "current smoker",
    },
}
SIDE_L = {
    "right": {
        "fi": "oikean",
        "sv": "höger",
        "nb": "høyre",
        "da": "højre",
        "is": "hægra",
        "en": "right",
    },
    "left": {
        "fi": "vasemman",
        "sv": "vänster",
        "nb": "venstre",
        "da": "venstre",
        "is": "vinstra",
        "en": "left",
    },
}
LOBE_L = {
    "upper": {
        "fi": "ylälohko",
        "sv": "överlob",
        "nb": "overlapp",
        "da": "overlap",
        "is": "efra blað",
        "en": "upper lobe",
    },
    "middle": {
        "fi": "keskilohko",
        "sv": "mellanlob",
        "nb": "midtlapp",
        "da": "mellemlap",
        "is": "miðblað",
        "en": "middle lobe",
    },
    "lower": {
        "fi": "alalohko",
        "sv": "underlob",
        "nb": "underlapp",
        "da": "underlap",
        "is": "neðra blað",
        "en": "lower lobe",
    },
}
PET_L = {
    "fi": ["ei etäpesäkkeisiin viittaavaa", "epäselvä lisämunuaislöydös"],
    "sv": ["inga tecken på fjärrmetastaser", "oklart binjurefynd"],
    "nb": ["ingen tegn til fjernmetastaser", "uklart binyrefunn"],
    "da": ["ingen tegn på fjernmetastaser", "uklart binyrefund"],
    "is": ["engin merki um fjarmeinvörp", "óljós nýrnahettufundur"],
    "en": ["no distant disease", "an indeterminate adrenal lesion"],
}

# free-text narrative templates per language. {f:NAME}=gold field; {x}=plain substitution.
TEMPLATES = {
    "fi": (
        "Keuhkosyövän MDT-kokous, {hospital}. {age}-vuotias {sex}, {smoking} ({pack} pakettivuotta), "
        "ECOG {ps}, G8 {g8}. TT: {size} mm kasvain {side} keuhkon {lobe}. PET-TT: {pet}. "
        "Patologia ({edition} TNM): {f:histology}. {beforeclause}Biomarkkerit: {f:pdl1}; ajurimuutos {f:driver}. "
        "MDT-suositus: cTNM {f:clinical_stage} (ryhmä {group}), hoitolinja {f:intent}, "
        "hoito {f:treatment}."
    ),
    "sv": (
        "Lungcancer-MDK, {hospital}. {age}-årig {sex}, {smoking} ({pack} packår), ECOG {ps}, "
        "G8 {g8}. DT: {size} mm tumör i {side} lungans {lobe}. PET-DT: {pet}. "
        "Patologi ({edition} TNM): {f:histology}. {beforeclause}Biomarkörer: {f:pdl1}; drivande {f:driver}. "
        "MDK-rekommendation: cTNM {f:clinical_stage} (grupp {group}), intention {f:intent}, "
        "behandling {f:treatment}."
    ),
    "nb": (
        "Lungekreft-MDT, {hospital}. {age} år gammel {sex}, {smoking} ({pack} pakkeår), ECOG {ps}, "
        "G8 {g8}. CT: {size} mm svulst i {side} lunges {lobe}. PET-CT: {pet}. "
        "Patologi ({edition} TNM): {f:histology}. {beforeclause}Biomarkører: {f:pdl1}; driver {f:driver}. "
        "MDT-anbefaling: cTNM {f:clinical_stage} (gruppe {group}), intensjon {f:intent}, "
        "behandling {f:treatment}."
    ),
    "da": (
        "Lungekræft-MDT, {hospital}. {age}-årig {sex}, {smoking} ({pack} pakkeår), ECOG {ps}, "
        "G8 {g8}. CT: {size} mm tumor i {side} lunges {lobe}. PET-CT: {pet}. "
        "Patologi ({edition} TNM): {f:histology}. {beforeclause}Biomarkører: {f:pdl1}; driver {f:driver}. "
        "MDT-anbefaling: cTNM {f:clinical_stage} (gruppe {group}), intention {f:intent}, "
        "behandling {f:treatment}."
    ),
    "is": (
        "Lungnakrabbameins-MDT, {hospital}. {age} ára {sex}, {smoking} ({pack} pakkaár), ECOG {ps}, "
        "G8 {g8}. TS: {size} mm æxli í {side} lunga {lobe}. PET-TS: {pet}. "
        "Meinafræði ({edition} TNM): {f:histology}. {beforeclause}Lífmerki: {f:pdl1}; drifbreyting {f:driver}. "
        "Tillaga MDT: cTNM {f:clinical_stage} (hópur {group}), markmið {f:intent}, "
        "meðferð {f:treatment}."
    ),
    "en": (
        "Lung cancer MDT meeting, {hospital}. {age}-year-old {sex}, {smoking} ({pack} pack-years), "
        "ECOG {ps}, G8 {g8}. CT: {size} mm mass in the {side} {lobe}. PET-CT: {pet}. "
        "Pathology ({edition} TNM): {f:histology}. {beforeclause}Biomarkers: {f:pdl1}; driver {f:driver}. "
        "MDT recommendation: cTNM {f:clinical_stage} (group {group}), intent {f:intent}, "
        "treatment {f:treatment}."
    ),
}

HOSPITALS = {
    "fi": "TAYS",
    "sv": "Karolinska",
    "nb": "OUS",
    "da": "Rigshospitalet",
    "is": "Landspítali",
    "en": "University Hospital",
}

# localized "pre-MDT cTNM" label; the before-stage is written into the note as a plain distractor
# (present-but-wrong target), not a gold field.
BEFORE_LABEL = {
    "fi": "MDT:tä edeltävä cTNM",
    "sv": "cTNM före MDK",
    "nb": "cTNM før MDT",
    "da": "cTNM før MDT",
    "is": "cTNM fyrir MDT",
    "en": "Pre-MDT cTNM",
}

# semistructured (mini) — labelled sections, English
SEMI_TEMPLATE = (
    "Lung Cancer MDT — structured (mini)\n"
    "Meeting: {hospital}; presenter {presenter}\n"
    "Patient: {age} {sex}, {smoking}, {pack} pack-years; ECOG {ps}; G8 {g8}\n"
    "Lung function: FVC {fvc}% · FEV1 {fev1}% · DLCO {dlco}%\n"
    "Imaging: CT thorax/abdomen; {size} mm, {side} {lobe}; PET-CT {pet}\n"
    "Pathology ({edition} ed. TNM): {f:histology}; tumour {size} mm; pre-MDT cTNM {before}\n"
    "Biomarkers: {f:pdl1}; driver {f:driver}\n"
    "MDT recommendation: cTNM {f:clinical_stage} (stage group {group}); "
    "intent {f:intent}; plan {f:treatment}"
)

# fully structured (v3.1) — coded key:value, English
STRUCT_TEMPLATE = (
    "mdt_purpose: primary_staging\n"
    "age: {age}\n"
    "sex: {sex}\n"
    "smoking_status: {smoking}\n"
    "pack_years: {pack}\n"
    "ecog: {ps}\n"
    "g8_total: {g8}\n"
    "fvc_pct: {fvc}\n"
    "fev1_pct: {fev1}\n"
    "dlco_pct: {dlco}\n"
    "tumour_side: {side}\n"
    "tumour_lobe: {lobe}\n"
    "t_size_mm: {size}\n"
    "t_size_basis: ct\n"
    "tnm_edition: 9\n"
    "histology: {f:histology}\n"
    "diagnostic_basis: histology\n"
    "pdl1_tps: {f:pdl1}\n"
    "driver_alteration: {f:driver}\n"
    "ctnm_before_mdt: {before}\n"
    "ctnm_after_mdt: {f:clinical_stage}\n"
    "stage_group: {group}\n"
    "treatment_intent: {f:intent}\n"
    "mdt_decision: {f:treatment}"
)

_TOKEN = re.compile(r"\{f:([a-z0-9_]+)\}|\{([a-z0-9_]+)\}")


def _render(template: str, plain: dict, golds: dict) -> tuple[str, dict]:
    out: list[str] = []
    pos = 0
    fields: dict = {}
    idx = 0
    for m in _TOKEN.finditer(template):
        out.append(template[idx : m.start()])
        pos += m.start() - idx
        idx = m.end()
        if m.group(1):
            name = m.group(1)
            value, canonical, ftype = golds[name]
            fields[name] = {
                "value": value,
                "span": [pos, pos + len(value)],
                "canonical": canonical,
                "field_type": ftype,
            }
            out.append(value)
            pos += len(value)
        else:
            s = str(plain[m.group(2)])
            out.append(s)
            pos += len(s)
    out.append(template[idx:])
    return "".join(out), fields


def _golds(case: dict, lang: str, pdl1_surface: str, driver_surface: str) -> dict:
    return {
        "histology": (HISTOLOGY_L[case["histology"]][lang], case["histology"], "categorical"),
        "clinical_stage": (case["ctnm"], case["ctnm_canonical"], "staging"),
        "intent": (INTENT_L[case["intent"]][lang], case["intent"], "categorical"),
        "treatment": (TREATMENT_L[case["treatment"]][lang], case["treatment"], "categorical"),
        "pdl1": (pdl1_surface, f"PD-L1 TPS {case['pdl1']}%", "categorical"),
        "driver": (driver_surface, case["driver"], "categorical"),
    }


def _driver_surface(case: dict, lang: str) -> str:
    return DRIVER_NONE_L[lang] if case["driver"] == "none" else case["driver"]


def build_challenges(case: dict, fields: dict) -> dict:
    """Adversarial extraction targets that test the VALIDITY heuristic, not just provenance.

    - surface_variant: a CORRECT value whose surface differs from the note (spacing/case), so it is
      found only via normalized/compact matching, not exact. Should validate as correct.
    - present_but_wrong: a WRONG value that nonetheless appears in the note (the pre-MDT cTNM), so
      provenance returns SPAN_FOUND (not a hallucination) — only an independent anchor / the validity
      heuristic can catch it. This is the hard case the verbatim corpus could not test.
    """
    ch: dict = {"surface_variant": {}, "present_but_wrong": {}}
    st = fields["clinical_stage"]["value"]
    if " " in st:
        ch["surface_variant"]["clinical_stage"] = st.replace(" ", "")
    h = fields["histology"]["value"]
    if h != h.upper():
        ch["surface_variant"]["histology"] = h.upper()
    p = fields["pdl1"]["value"]
    if "%" in p and " %" not in p:
        ch["surface_variant"]["pdl1"] = p.replace("%", " %")
    if case["stage_differs"]:
        ch["present_but_wrong"]["clinical_stage"] = case["ctnm_before"]
    return ch


def render_free_text(case: dict, lang: str, rng: random.Random) -> tuple[str, dict]:
    plain = {
        "hospital": HOSPITALS[lang],
        "age": case["age"],
        "sex": SEX_L[case["sex"]][lang],
        "smoking": SMOKING_L[case["smoking"]][lang],
        "pack": case["pack_years"],
        "ps": case["ps"],
        "g8": case["g8"],
        "size": case["size_mm"],
        "side": SIDE_L[case["side"]][lang],
        "lobe": LOBE_L[case["lobe"]][lang],
        "pet": rng.choice(PET_L[lang]),
        "edition": case["tnm_edition"],
        "group": case["stage_group"],
        "beforeclause": f"{BEFORE_LABEL[lang]} {case['ctnm_before']}.",
    }
    golds = _golds(case, lang, case["pdl1_surface_free"], _driver_surface(case, lang))
    return _render(TEMPLATES[lang], plain, golds)


def render_semistructured(case: dict, rng: random.Random) -> tuple[str, dict]:
    plain = {
        "hospital": "University Hospital",
        "presenter": "oncologist",
        "age": case["age"],
        "sex": SEX_L[case["sex"]]["en"],
        "smoking": SMOKING_L[case["smoking"]]["en"],
        "pack": case["pack_years"],
        "ps": case["ps"],
        "g8": case["g8"],
        "fvc": case["fvc"],
        "fev1": case["fev1"],
        "dlco": case["dlco"],
        "size": case["size_mm"],
        "side": case["side"],
        "lobe": LOBE_L[case["lobe"]]["en"],
        "pet": rng.choice(PET_L["en"]),
        "edition": "9th",
        "group": case["stage_group"],
        "before": case["ctnm_before"],
    }
    golds = _golds(case, "en", case["pdl1_surface_free"], _driver_surface(case, "en"))
    return _render(SEMI_TEMPLATE, plain, golds)


def render_structured(case: dict) -> tuple[str, dict]:
    plain = {
        "age": case["age"],
        "sex": case["sex"],
        "smoking": case["smoking"],
        "pack": case["pack_years"],
        "ps": case["ps"],
        "g8": case["g8"],
        "fvc": case["fvc"],
        "fev1": case["fev1"],
        "dlco": case["dlco"],
        "side": case["side"],
        "lobe": case["lobe"].replace(" lobe", ""),
        "size": case["size_mm"],
        "group": case["stage_group"],
        "before": case["ctnm_before_canonical"],
    }
    # structured PD-L1 surface is the bare "NN%"; driver "none" stays the code "none"
    pdl1_surface = f"{case['pdl1']}%"
    driver_surface = "none" if case["driver"] == "none" else case["driver"]
    golds = _golds(case, "en", pdl1_surface, driver_surface)
    return _render(STRUCT_TEMPLATE, plain, golds)


# --------------------------------------------------------------------------- driver

FREE_LANGS = ["fi", "sv", "nb", "da", "is", "en"]
GOLD_FIELDS = ["histology", "clinical_stage", "intent", "treatment", "pdl1", "driver"]


def _seed(group: str, i: int) -> int:
    return zlib.adler32(f"notevahti::{group}::{i}".encode())


def generate(n: int, out_dir: pathlib.Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "n_per_group": n,
        "groups": {},
        "gold_fields": GOLD_FIELDS,
        "tools": {
            "free": "ntog.org/mdt.html",
            "semi": "ntog.org/mdt-structured-mini.html",
            "struct": "ntog.org/mdt-structured-v3_1.html",
        },
    }
    groups = [(f"free_{lang}", "free", lang) for lang in FREE_LANGS]
    groups += [("semistructured_en", "semi", "en"), ("structured_en", "struct", "en")]

    for group, kind, lang in groups:
        path = out_dir / f"{group}.jsonl"
        with open(path, "w", encoding="utf-8") as fh:
            for i in range(n):
                rng = random.Random(_seed(group, i))
                case = sample_case(rng)
                if kind == "free":
                    text, fields = render_free_text(case, lang, rng)
                elif kind == "semi":
                    text, fields = render_semistructured(case, rng)
                else:
                    text, fields = render_structured(case)
                rec = {
                    "case_id": f"{group}-{i:04d}",
                    "group": group,
                    "modality": kind,
                    "language": lang,
                    "note": text,
                    "fields": fields,
                    "challenges": build_challenges(case, fields),
                }
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        manifest["groups"][group] = {"kind": kind, "language": lang, "n": n, "file": path.name}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate the synthetic lung-cancer MDT corpus.")
    ap.add_argument("--n", type=int, default=500, help="cases per group (default 500)")
    ap.add_argument("--out", default="corpus", help="output directory (default ./corpus)")
    args = ap.parse_args(argv)
    manifest = generate(args.n, pathlib.Path(args.out))
    total = sum(g["n"] for g in manifest["groups"].values())
    print(f"generated {total} cases across {len(manifest['groups'])} groups -> {args.out}/")
    for name, g in manifest["groups"].items():
        print(f"  {name:20} {g['kind']:7} {g['language']:3} n={g['n']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
