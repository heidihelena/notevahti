#!/usr/bin/env python3
"""Generate the NoteVahti synthetic Nordic lung-cancer MDT dataset.

The generator creates ground truth first, renders each case into three note
formats, writes language-specific JSONL files, and then runs the companion
validator. It uses only deterministic pseudo-random choices from fixed seeds.
"""

from __future__ import annotations

import copy
import json
import random
import subprocess
import sys
from pathlib import Path


DATASET_VERSION = "notevahti_lung_mdt_synthetic_v1"
BASE_SEED = 20260629
LANGUAGES = ["fi", "sv", "nb", "da", "is", "en"]
DOCUMENTATION_FORMATS = ["free_text", "structured_mini", "structured_v3_1"]

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

CASE_CATEGORY_COUNTS = {
    "clear_explicit": 90,
    "missing_ecog": 30,
    "partial_tnm": 30,
    "conflicting_tnm": 30,
    "old_vs_current_staging": 30,
    "mdt_planned": 15,
    "mdt_not_yet_discussed": 15,
    "indirect_functional_status": 30,
    "biomarker_treatment_complexity": 30,
}

HISTOLOGY_COUNTS = {
    "adenocarcinoma": 135,
    "squamous cell carcinoma": 75,
    "NSCLC NOS": 30,
    "small-cell lung cancer": 30,
    "other_or_uncertain": 30,
}

STAGE_BUCKET_COUNTS = {
    "I": 45,
    "II": 45,
    "III": 75,
    "IV": 105,
}

TREATMENT_INTENT_COUNTS = {
    "curative": 105,
    "palliative": 135,
    "diagnostic/additional workup": 45,
    "best supportive care or uncertain": 15,
}

EXPLICIT_ECOG_COUNTS = {
    0: 36,
    1: 84,
    2: 60,
    3: 48,
    4: 12,
}

TNM_PROFILES = {
    "I": [
        ("c", "T1a", "N0", "M0", "IA1"),
        ("c", "T1b", "N0", "M0", "IA2"),
        ("c", "T1c", "N0", "M0", "IA3"),
        ("c", "T2a", "N0", "M0", "IB"),
    ],
    "II": [
        ("c", "T2b", "N0", "M0", "IIA"),
        ("c", "T1c", "N1", "M0", "IIB"),
        ("c", "T2a", "N1", "M0", "IIB"),
        ("c", "T3", "N0", "M0", "IIB"),
    ],
    "III": [
        ("c", "T1c", "N2", "M0", "IIIA"),
        ("c", "T2b", "N2", "M0", "IIIA"),
        ("c", "T3", "N1", "M0", "IIIA"),
        ("c", "T4", "N0", "M0", "IIIA"),
        ("c", "T3", "N2", "M0", "IIIB"),
        ("c", "T4", "N2", "M0", "IIIB"),
        ("c", "T2a", "N3", "M0", "IIIC"),
    ],
    "IV": [
        ("c", "T1c", "N0", "M1a", "IVA"),
        ("c", "T2a", "N1", "M1b", "IVA"),
        ("c", "T3", "N2", "M1c1", "IVB"),
        ("c", "T4", "N3", "M1c2", "IVB"),
        ("c", "T2b", "N2", "M1c2", "IVB"),
    ],
}

TUMOUR_SITES = [
    ("right upper lobe", 28),
    ("right lower lobe", 36),
    ("left upper lobe", 31),
    ("left lower lobe", 42),
    ("right middle lobe", 24),
    ("lingula", 21),
]

INDIRECT_FUNCTION = {
    "en": [
        "independent in ADL but avoids stairs",
        "walks short distances with rests",
        "needs help with self-care on bad days",
        "mostly chair-bound after meals",
    ],
    "fi": [
        "omatoiminen päivittäisissä toimissa mutta välttää portaita",
        "kävelee lyhyitä matkoja taukojen kanssa",
        "tarvitsee apua peseytymisessä huonoina päivinä",
        "istuu suurimman osan päivästä ruokailujen jälkeen",
    ],
    "sv": [
        "klarar ADL själv men undviker trappor",
        "går korta sträckor med pauser",
        "behöver hjälp med egenvård vissa dagar",
        "sitter största delen av dagen efter måltider",
    ],
    "nb": [
        "selvhjulpen i ADL men unngår trapper",
        "går korte avstander med pauser",
        "trenger hjelp med egenomsorg enkelte dager",
        "sitter mesteparten av dagen etter måltider",
    ],
    "da": [
        "selvhjulpen i ADL men undgår trapper",
        "går korte afstande med pauser",
        "har brug for hjælp til egenomsorg nogle dage",
        "sidder det meste af dagen efter måltider",
    ],
    "is": [
        "sjálfbjarga í daglegum athöfnum en forðast stiga",
        "gengur stuttar vegalengdir með hvíldum",
        "þarf aðstoð við sjálfsumönnun suma daga",
        "siturnær allan daginn eftir máltíðir",
    ],
}

LOCAL = {
    "en": {
        "mdt_completed": "discussed at MDT",
        "mdt_planned": "planned for MDT",
        "mdt_not_completed": "not yet discussed at MDT",
        "missing_ecog": "no numeric ECOG documented",
        "tnm_missing": "{component} not documented",
        "tnm_conflict": "TNM values differ",
        "old_current_unclear": "current stage not explicitly labelled",
        "current_tnm": "current TNM",
        "old_tnm": "old TNM",
        "conflict_and": "and",
        "later_tnm": "later TNM",
        "path_p": "pathological staging after resection",
        "path_yp": "pathological staging after neoadjuvant therapy and resection",
        "ecog_prefix": "ECOG",
        "fictional_adult": "fictional adult",
        "age_sex": "{age}-year-old {sex}",
        "male": "male",
        "female": "female",
        "unspecified": "sex not specified",
        "smoking_current": "current smoker",
        "smoking_former": "former smoker",
        "smoking_never": "never smoker",
        "imaging": "CT/PET shows a {size} mm lesion in the {site}; {nodes}; {mets}.",
        "nodes_N0": "no suspicious nodal disease",
        "nodes_N1": "ipsilateral hilar nodes",
        "nodes_N2": "mediastinal nodal uptake",
        "nodes_N2a": "single-station mediastinal nodal uptake",
        "nodes_N2b": "multi-station mediastinal nodal uptake",
        "nodes_N3": "contralateral mediastinal or supraclavicular nodes",
        "nodes_none": "nodal status not fully documented",
        "mets_M0": "no distant metastases",
        "mets_M1a": "pleural disease or contralateral lung nodule",
        "mets_M1b": "one extrathoracic lesion",
        "mets_M1c1": "multiple lesions in one organ system",
        "mets_M1c2": "metastases in multiple organ systems",
        "mets_none": "distant metastasis status not fully documented",
        "pathology": "biopsy/cytology supports {histology}.",
        "recommend": "Recommendation: {recommendation}.",
        "intent": "Treatment intent",
        "review_none": "no review flags",
        "review_flags": "review required: {reason}",
        "bio": "Molecular markers: {markers}.",
        "free_join": " ",
        "mini": {
            "mdt": "MDT status",
            "imaging": "Imaging",
            "pathology": "Pathology",
            "stage": "Stage/TNM",
            "ecog": "ECOG/WHO PS",
            "recommendation": "Recommendation",
        },
        "v31": {
            "patient": "Patient context",
            "diagnostic": "Diagnostic status",
            "imaging": "Imaging",
            "pathology": "Pathology",
            "molecular": "Molecular markers",
            "tnm": "TNM",
            "ecog": "ECOG/WHO PS",
            "intent": "Treatment intent",
            "recommendation": "MDT recommendation",
            "review": "Review flags or missing data",
        },
    },
    "fi": {
        "mdt_completed": "käsitelty MDT:ssä",
        "mdt_planned": "suunniteltu MDT-käsittelyyn",
        "mdt_not_completed": "ei vielä käsitelty MDT:ssä",
        "missing_ecog": "numeerista ECOG-arvoa ei kirjattu",
        "tnm_missing": "{component} puuttuu kirjauksesta",
        "tnm_conflict": "TNM-arvot ovat ristiriitaiset",
        "old_current_unclear": "nykyistä levinneisyysluokkaa ei merkitty selvästi",
        "current_tnm": "current TNM",
        "old_tnm": "aiempi TNM",
        "conflict_and": "ja",
        "later_tnm": "myöhempi TNM",
        "path_p": "patologinen levinneisyys leikkauksen jälkeen",
        "path_yp": "patologinen levinneisyys neoadjuvanttihoidon ja leikkauksen jälkeen",
        "ecog_prefix": "ECOG",
        "fictional_adult": "fiktiivinen aikuinen",
        "age_sex": "{age}-vuotias {sex}",
        "male": "mies",
        "female": "nainen",
        "unspecified": "sukupuoli ei tiedossa",
        "smoking_current": "tupakoi",
        "smoking_former": "entinen tupakoija",
        "smoking_never": "ei ole tupakoinut",
        "imaging": "TT/PET: {size} mm muutos alueella {site}; {nodes}; {mets}.",
        "nodes_N0": "ei epäilyttäviä imusolmukkeita",
        "nodes_N1": "ipsilateraaliset hiluksen imusolmukkeet",
        "nodes_N2": "mediastinaaliset imusolmukkeet",
        "nodes_N2a": "yksi mediastinaalinen imusolmukeasema",
        "nodes_N2b": "useita mediastinaalisia imusolmukeasemia",
        "nodes_N3": "vastakkaispuolen mediastinaaliset tai supraklavikulaariset imusolmukkeet",
        "nodes_none": "imusolmuketieto ei ole täydellinen",
        "mets_M0": "ei etäpesäkkeitä",
        "mets_M1a": "pleuratauti tai vastakkaisen keuhkon kyhmy",
        "mets_M1b": "yksi rintakehän ulkopuolinen pesäke",
        "mets_M1c1": "useita pesäkkeitä yhdessä elinjärjestelmässä",
        "mets_M1c2": "etäpesäkkeitä useissa elinjärjestelmissä",
        "mets_none": "M-luokka ei ole täysin kirjattu",
        "pathology": "näyte sopii diagnoosiin {histology}.",
        "recommend": "Suositellaan: {recommendation}.",
        "intent": "Hoidon tavoite",
        "review_none": "ei tarkistusmerkintöjä",
        "review_flags": "tarkistus tarvitaan: {reason}",
        "bio": "Molekyylimarkkerit: {markers}.",
        "free_join": " ",
        "mini": {
            "mdt": "MDT-status",
            "imaging": "Kuvantaminen",
            "pathology": "Patologia",
            "stage": "Levinneisyys/TNM",
            "ecog": "ECOG/WHO PS",
            "recommendation": "Suositus",
        },
        "v31": {
            "patient": "Potilaskonteksti",
            "diagnostic": "Diagnostinen tilanne",
            "imaging": "Kuvantaminen",
            "pathology": "Patologia",
            "molecular": "Molekyylimarkkerit",
            "tnm": "TNM",
            "ecog": "ECOG/WHO PS",
            "intent": "Hoidon tavoite",
            "recommendation": "MDT-suositus",
            "review": "Tarkistusliput tai puuttuvat tiedot",
        },
    },
    "sv": {
        "mdt_completed": "diskuterad vid MDT",
        "mdt_planned": "planerad för MDT",
        "mdt_not_completed": "ännu inte diskuterad vid MDT",
        "missing_ecog": "numeriskt ECOG saknas",
        "tnm_missing": "{component} saknas i anteckningen",
        "tnm_conflict": "TNM-värdena skiljer sig",
        "old_current_unclear": "aktuell stadieindelning är inte tydligt markerad",
        "current_tnm": "current TNM",
        "old_tnm": "tidigare TNM",
        "conflict_and": "och",
        "later_tnm": "senare TNM",
        "path_p": "patologisk stadieindelning efter resektion",
        "path_yp": "patologisk stadieindelning efter neoadjuvant behandling och resektion",
        "ecog_prefix": "ECOG",
        "fictional_adult": "fiktiv vuxen",
        "age_sex": "{age}-årig {sex}",
        "male": "man",
        "female": "kvinna",
        "unspecified": "kön ej specificerat",
        "smoking_current": "nuvarande rökare",
        "smoking_former": "tidigare rökare",
        "smoking_never": "aldrig rökare",
        "imaging": "DT/PET visar {size} mm förändring i {site}; {nodes}; {mets}.",
        "nodes_N0": "inga suspekta lymfkörtlar",
        "nodes_N1": "ipsilaterala hiluskörtlar",
        "nodes_N2": "mediastinalt upptag",
        "nodes_N2a": "en mediastinal station",
        "nodes_N2b": "flera mediastinala stationer",
        "nodes_N3": "kontralaterala mediastinala eller supraklavikulära körtlar",
        "nodes_none": "nodal status är inte fullständigt dokumenterad",
        "mets_M0": "inga fjärrmetastaser",
        "mets_M1a": "pleurasjukdom eller kontralateral lungnodul",
        "mets_M1b": "en extratorakal lesion",
        "mets_M1c1": "flera lesioner i ett organsystem",
        "mets_M1c2": "metastaser i flera organsystem",
        "mets_none": "M-status är inte fullständigt dokumenterad",
        "pathology": "prov talar för {histology}.",
        "recommend": "Rekommenderas: {recommendation}.",
        "intent": "Behandlingsintention",
        "review_none": "inga granskningsflaggor",
        "review_flags": "granskning krävs: {reason}",
        "bio": "Molekylära markörer: {markers}.",
        "free_join": " ",
        "mini": {
            "mdt": "MDT-status",
            "imaging": "Bilddiagnostik",
            "pathology": "Patologi",
            "stage": "Stadie/TNM",
            "ecog": "ECOG/WHO PS",
            "recommendation": "Rekommendation",
        },
        "v31": {
            "patient": "Patientkontext",
            "diagnostic": "Diagnostisk status",
            "imaging": "Bilddiagnostik",
            "pathology": "Patologi",
            "molecular": "Molekylära markörer",
            "tnm": "TNM",
            "ecog": "ECOG/WHO PS",
            "intent": "Behandlingsintention",
            "recommendation": "MDT-rekommendation",
            "review": "Granskningsflaggor eller saknade data",
        },
    },
    "nb": {
        "mdt_completed": "diskutert i tverrfaglig MDT-møte",
        "mdt_planned": "planlagt til MDT",
        "mdt_not_completed": "ikke diskutert i MDT ennå",
        "missing_ecog": "numerisk ECOG er ikke dokumentert",
        "tnm_missing": "{component} mangler i notatet",
        "tnm_conflict": "TNM-verdiene er ulike",
        "old_current_unclear": "aktuell stadieinndeling er ikke tydelig merket",
        "current_tnm": "current TNM",
        "old_tnm": "tidligere TNM",
        "conflict_and": "og",
        "later_tnm": "senere TNM",
        "path_p": "patologisk stadieinndeling etter reseksjon",
        "path_yp": "patologisk stadieinndeling etter neoadjuvant behandling og reseksjon",
        "ecog_prefix": "ECOG",
        "fictional_adult": "fiktiv voksen",
        "age_sex": "{age} år gammel {sex}",
        "male": "mann",
        "female": "kvinne",
        "unspecified": "kjønn ikke spesifisert",
        "smoking_current": "nåværende røyker",
        "smoking_former": "tidligere røyker",
        "smoking_never": "aldri-røyker",
        "imaging": "CT/PET viser {size} mm lesjon i {site}; {nodes}; {mets}.",
        "nodes_N0": "ingen suspekte lymfeknuter",
        "nodes_N1": "ipsilaterale hilære lymfeknuter",
        "nodes_N2": "mediastinale lymfeknuter",
        "nodes_N2a": "en mediastinal stasjon",
        "nodes_N2b": "flere mediastinale stasjoner",
        "nodes_N3": "kontralaterale mediastinale eller supraklavikulære knuter",
        "nodes_none": "nodal status er ikke fullstendig dokumentert",
        "mets_M0": "ingen fjernmetastaser",
        "mets_M1a": "pleural sykdom eller kontralateral lungeknute",
        "mets_M1b": "én ekstratorakal lesjon",
        "mets_M1c1": "flere lesjoner i ett organsystem",
        "mets_M1c2": "metastaser i flere organsystemer",
        "mets_none": "M-status er ikke fullstendig dokumentert",
        "pathology": "prøve forenlig med {histology}.",
        "recommend": "Anbefales: {recommendation}.",
        "intent": "Behandlingsintensjon",
        "review_none": "ingen kontrollflagg",
        "review_flags": "kontroll kreves: {reason}",
        "bio": "Molekylære markører: {markers}.",
        "free_join": " ",
        "mini": {
            "mdt": "MDT-status",
            "imaging": "Bildediagnostikk",
            "pathology": "Patologi",
            "stage": "Stadium/TNM",
            "ecog": "ECOG/WHO PS",
            "recommendation": "Anbefaling",
        },
        "v31": {
            "patient": "Pasientkontekst",
            "diagnostic": "Diagnostisk status",
            "imaging": "Bildediagnostikk",
            "pathology": "Patologi",
            "molecular": "Molekylære markører",
            "tnm": "TNM",
            "ecog": "ECOG/WHO PS",
            "intent": "Behandlingsintensjon",
            "recommendation": "MDT-anbefaling",
            "review": "Kontrollflagg eller manglende data",
        },
    },
    "da": {
        "mdt_completed": "drøftet på MDT-konference",
        "mdt_planned": "planlagt til MDT",
        "mdt_not_completed": "endnu ikke drøftet på MDT",
        "missing_ecog": "numerisk ECOG er ikke dokumenteret",
        "tnm_missing": "{component} mangler i notatet",
        "tnm_conflict": "TNM-værdierne er forskellige",
        "old_current_unclear": "aktuel stadieinddeling er ikke tydeligt markeret",
        "current_tnm": "current TNM",
        "old_tnm": "tidligere TNM",
        "conflict_and": "og",
        "later_tnm": "senere TNM",
        "path_p": "patologisk stadieinddeling efter resektion",
        "path_yp": "patologisk stadieinddeling efter neoadjuverende behandling og resektion",
        "ecog_prefix": "ECOG",
        "fictional_adult": "fiktiv voksen",
        "age_sex": "{age}-årig {sex}",
        "male": "mand",
        "female": "kvinde",
        "unspecified": "køn ikke specificeret",
        "smoking_current": "aktuel ryger",
        "smoking_former": "tidligere ryger",
        "smoking_never": "aldrig-ryger",
        "imaging": "CT/PET viser {size} mm læsion i {site}; {nodes}; {mets}.",
        "nodes_N0": "ingen suspekte lymfeknuder",
        "nodes_N1": "ipsilaterale hilære lymfeknuder",
        "nodes_N2": "mediastinale lymfeknuder",
        "nodes_N2a": "en mediastinal station",
        "nodes_N2b": "flere mediastinale stationer",
        "nodes_N3": "kontralaterale mediastinale eller supraklavikulære knuder",
        "nodes_none": "nodal status er ikke fuldt dokumenteret",
        "mets_M0": "ingen fjernmetastaser",
        "mets_M1a": "pleural sygdom eller kontralateral lungeknude",
        "mets_M1b": "én ekstratorakal læsion",
        "mets_M1c1": "flere læsioner i ét organsystem",
        "mets_M1c2": "metastaser i flere organsystemer",
        "mets_none": "M-status er ikke fuldt dokumenteret",
        "pathology": "prøve forenelig med {histology}.",
        "recommend": "Anbefales: {recommendation}.",
        "intent": "Behandlingsintention",
        "review_none": "ingen review-flag",
        "review_flags": "review kræves: {reason}",
        "bio": "Molekylære markører: {markers}.",
        "free_join": " ",
        "mini": {
            "mdt": "MDT-status",
            "imaging": "Billeddiagnostik",
            "pathology": "Patologi",
            "stage": "Stadium/TNM",
            "ecog": "ECOG/WHO PS",
            "recommendation": "Anbefaling",
        },
        "v31": {
            "patient": "Patientkontekst",
            "diagnostic": "Diagnostisk status",
            "imaging": "Billeddiagnostik",
            "pathology": "Patologi",
            "molecular": "Molekylære markører",
            "tnm": "TNM",
            "ecog": "ECOG/WHO PS",
            "intent": "Behandlingsintention",
            "recommendation": "MDT-anbefaling",
            "review": "Review-flag eller manglende data",
        },
    },
    "is": {
        "mdt_completed": "rætt á MDT fundi",
        "mdt_planned": "áætlað fyrir MDT",
        "mdt_not_completed": "ekki enn rætt á MDT",
        "missing_ecog": "tölulegt ECOG er ekki skráð",
        "tnm_missing": "{component} vantar í skráningu",
        "tnm_conflict": "TNM-gildin eru ósamræmd",
        "old_current_unclear": "núverandi stigun er ekki skýrt merkt",
        "current_tnm": "current TNM",
        "old_tnm": "fyrra TNM",
        "conflict_and": "og",
        "later_tnm": "síðara TNM",
        "path_p": "meinafræðileg stigun eftir brottnám",
        "path_yp": "meinafræðileg stigun eftir formeðferð og brottnám",
        "ecog_prefix": "ECOG",
        "fictional_adult": "skáldaður fullorðinn einstaklingur",
        "age_sex": "{age} ára {sex}",
        "male": "karl",
        "female": "kona",
        "unspecified": "kyn ekki tilgreint",
        "smoking_current": "reykir nú",
        "smoking_former": "fyrrverandi reykingamaður",
        "smoking_never": "hefur aldrei reykt",
        "imaging": "CT/PET sýnir {size} mm mein í {site}; {nodes}; {mets}.",
        "nodes_N0": "engin grunsamleg eitlastækkun",
        "nodes_N1": "eitlar við lungnarót sömu megin",
        "nodes_N2": "miðmætiseitlar",
        "nodes_N2a": "ein miðmætiseitlastöð",
        "nodes_N2b": "fleiri miðmætiseitlastöðvar",
        "nodes_N3": "eitlar gagnstætt í miðmæti eða ofan viðbeins",
        "nodes_none": "eitlastatus ekki fullskráður",
        "mets_M0": "engin fjarmeinvörp",
        "mets_M1a": "fleiðrusjúkdómur eða hnútur í gagnstæðu lunga",
        "mets_M1b": "eitt mein utan brjósthols",
        "mets_M1c1": "mörg mein í einu líffærakerfi",
        "mets_M1c2": "meinvörp í mörgum líffærakerfum",
        "mets_none": "M-status ekki fullskráður",
        "pathology": "sýni samrýmist {histology}.",
        "recommend": "Mælt er með: {recommendation}.",
        "intent": "Meðferðarmarkmið",
        "review_none": "engin yfirferðarmerki",
        "review_flags": "yfirferð þarf: {reason}",
        "bio": "Sameindamarkarar: {markers}.",
        "free_join": " ",
        "mini": {
            "mdt": "MDT-staða",
            "imaging": "Myndgreining",
            "pathology": "Meinafræði",
            "stage": "Stigun/TNM",
            "ecog": "ECOG/WHO PS",
            "recommendation": "Ráðlegging",
        },
        "v31": {
            "patient": "Samhengi sjúklings",
            "diagnostic": "Greiningarstaða",
            "imaging": "Myndgreining",
            "pathology": "Meinafræði",
            "molecular": "Sameindamarkarar",
            "tnm": "TNM",
            "ecog": "ECOG/WHO PS",
            "intent": "Meðferðarmarkmið",
            "recommendation": "MDT-ráðlegging",
            "review": "Yfirferðarmerki eða vantar gögn",
        },
    },
}

HISTOLOGY_LOCAL = {
    "en": {
        "adenocarcinoma": "adenocarcinoma",
        "squamous cell carcinoma": "squamous cell carcinoma",
        "NSCLC NOS": "NSCLC NOS",
        "small-cell lung cancer": "small-cell lung cancer",
        "other_or_uncertain": "carcinoma, subtype uncertain",
    },
    "fi": {
        "adenocarcinoma": "adenokarsinooma",
        "squamous cell carcinoma": "levyepiteelikarsinooma",
        "NSCLC NOS": "NSCLC NOS",
        "small-cell lung cancer": "pienisoluinen keuhkosyöpä",
        "other_or_uncertain": "karsinooma, alatyyppi epävarma",
    },
    "sv": {
        "adenocarcinoma": "adenokarcinom",
        "squamous cell carcinoma": "skivepitelcancer",
        "NSCLC NOS": "NSCLC NOS",
        "small-cell lung cancer": "småcellig lungcancer",
        "other_or_uncertain": "karcinom, subtyp oklar",
    },
    "nb": {
        "adenocarcinoma": "adenokarsinom",
        "squamous cell carcinoma": "plateepitelkarsinom",
        "NSCLC NOS": "NSCLC NOS",
        "small-cell lung cancer": "småcellet lungekreft",
        "other_or_uncertain": "karsinom, subtype uklar",
    },
    "da": {
        "adenocarcinoma": "adenokarcinom",
        "squamous cell carcinoma": "planocellulært karcinom",
        "NSCLC NOS": "NSCLC NOS",
        "small-cell lung cancer": "småcellet lungekræft",
        "other_or_uncertain": "karcinom, subtype usikker",
    },
    "is": {
        "adenocarcinoma": "kirtilkrabbamein",
        "squamous cell carcinoma": "flöguþekjukrabbamein",
        "NSCLC NOS": "NSCLC NOS",
        "small-cell lung cancer": "smáfrumukrabbamein í lunga",
        "other_or_uncertain": "krabbamein, undirgerð óviss",
    },
}

SITE_LOCAL = {
    "en": {
        "right upper lobe": "right upper lobe",
        "right lower lobe": "right lower lobe",
        "left upper lobe": "left upper lobe",
        "left lower lobe": "left lower lobe",
        "right middle lobe": "right middle lobe",
        "lingula": "lingula",
    },
    "fi": {
        "right upper lobe": "oikea ylälohko",
        "right lower lobe": "oikea alalohko",
        "left upper lobe": "vasen ylälohko",
        "left lower lobe": "vasen alalohko",
        "right middle lobe": "oikea keskilohko",
        "lingula": "lingula",
    },
    "sv": {
        "right upper lobe": "höger överlob",
        "right lower lobe": "höger underlob",
        "left upper lobe": "vänster överlob",
        "left lower lobe": "vänster underlob",
        "right middle lobe": "höger mellanlob",
        "lingula": "lingula",
    },
    "nb": {
        "right upper lobe": "høyre overlapp",
        "right lower lobe": "høyre underlapp",
        "left upper lobe": "venstre overlapp",
        "left lower lobe": "venstre underlapp",
        "right middle lobe": "høyre midtlapp",
        "lingula": "lingula",
    },
    "da": {
        "right upper lobe": "højre overlap",
        "right lower lobe": "højre underlap",
        "left upper lobe": "venstre overlap",
        "left lower lobe": "venstre underlap",
        "right middle lobe": "højre mellemlap",
        "lingula": "lingula",
    },
    "is": {
        "right upper lobe": "hægra efra lungnablað",
        "right lower lobe": "hægra neðra lungnablað",
        "left upper lobe": "vinstra efra lungnablað",
        "left lower lobe": "vinstra neðra lungnablað",
        "right middle lobe": "hægra miðlungnablað",
        "lingula": "lingula",
    },
}

INTENT_LOCAL = {
    "en": {
        "curative": "curative",
        "palliative": "palliative",
        "diagnostic/additional workup": "diagnostic/additional workup",
        "best supportive care or uncertain": "best supportive care or uncertain",
    },
    "fi": {
        "curative": "kuratiivinen",
        "palliative": "palliatiivinen",
        "diagnostic/additional workup": "diagnostinen / lisäselvittely",
        "best supportive care or uncertain": "oireenmukainen tukihoito tai epävarma",
    },
    "sv": {
        "curative": "kurativ",
        "palliative": "palliativ",
        "diagnostic/additional workup": "diagnostik / kompletterande utredning",
        "best supportive care or uncertain": "bästa understödjande vård eller oklart",
    },
    "nb": {
        "curative": "kurativ",
        "palliative": "palliativ",
        "diagnostic/additional workup": "diagnostikk / videre utredning",
        "best supportive care or uncertain": "best supportive care eller uavklart",
    },
    "da": {
        "curative": "kurativ",
        "palliative": "palliativ",
        "diagnostic/additional workup": "diagnostik / yderligere udredning",
        "best supportive care or uncertain": "best supportive care eller uafklaret",
    },
    "is": {
        "curative": "læknandi",
        "palliative": "líknandi",
        "diagnostic/additional workup": "greining / frekari rannsóknir",
        "best supportive care or uncertain": "bestu stuðningsmeðferð eða óljóst",
    },
}

RECOMMENDATIONS = {
    "curative": [
        "thoracic surgery evaluation",
        "definitive chemoradiotherapy",
        "stereotactic radiotherapy assessment",
    ],
    "palliative": [
        "systemic therapy",
        "palliative radiotherapy",
        "oncology review after biomarkers",
    ],
    "diagnostic/additional workup": [
        "additional staging / biopsy",
        "repeat bronchoscopy or EBUS",
        "brain MRI before treatment decision",
    ],
    "best supportive care or uncertain": [
        "best supportive care",
        "symptom-directed care and reassessment",
    ],
}

RECOMMENDATION_LOCAL = {
    "en": {
        "thoracic surgery evaluation": "thoracic surgery evaluation",
        "definitive chemoradiotherapy": "definitive chemoradiotherapy",
        "stereotactic radiotherapy assessment": "stereotactic radiotherapy assessment",
        "systemic therapy": "systemic therapy",
        "palliative radiotherapy": "palliative radiotherapy",
        "oncology review after biomarkers": "oncology review after biomarkers",
        "additional staging / biopsy": "additional staging / biopsy",
        "repeat bronchoscopy or EBUS": "repeat bronchoscopy or EBUS",
        "brain MRI before treatment decision": "brain MRI before treatment decision",
        "best supportive care": "best supportive care",
        "symptom-directed care and reassessment": "symptom-directed care and reassessment",
    },
    "fi": {
        "thoracic surgery evaluation": "thoraxkirurginen leikkausarvio",
        "definitive chemoradiotherapy": "radikaali kemosädehoito",
        "stereotactic radiotherapy assessment": "SABR-arvio",
        "systemic therapy": "systeeminen hoito",
        "palliative radiotherapy": "palliatiivinen sädehoito",
        "oncology review after biomarkers": "onkologin arvio biomarkkerien jälkeen",
        "additional staging / biopsy": "lisäselvittely ja/tai biopsia",
        "repeat bronchoscopy or EBUS": "uusintabronkoskopia tai EBUS",
        "brain MRI before treatment decision": "aivojen MRI ennen hoitopäätöstä",
        "best supportive care": "paras oireenmukainen tukihoito",
        "symptom-directed care and reassessment": "oireenmukainen hoito ja uusi arvio",
    },
    "sv": {
        "thoracic surgery evaluation": "kirurgbedömning",
        "definitive chemoradiotherapy": "definitiv kemoradioterapi",
        "stereotactic radiotherapy assessment": "SABR-bedömning",
        "systemic therapy": "systemisk behandling",
        "palliative radiotherapy": "palliativ strålbehandling",
        "oncology review after biomarkers": "onkologbedömning efter biomarkörer",
        "additional staging / biopsy": "kompletterande stadieindelning/biopsi",
        "repeat bronchoscopy or EBUS": "upprepad bronkoskopi eller EBUS",
        "brain MRI before treatment decision": "hjärn-MR före behandlingsbeslut",
        "best supportive care": "bästa understödjande vård",
        "symptom-directed care and reassessment": "symtomriktad vård och ny bedömning",
    },
    "nb": {
        "thoracic surgery evaluation": "kirurgisk vurdering",
        "definitive chemoradiotherapy": "definitiv kjemoradioterapi",
        "stereotactic radiotherapy assessment": "SABR-vurdering",
        "systemic therapy": "systemisk behandling",
        "palliative radiotherapy": "palliativ strålebehandling",
        "oncology review after biomarkers": "onkologisk vurdering etter biomarkører",
        "additional staging / biopsy": "videre stadieinndeling/biopsi",
        "repeat bronchoscopy or EBUS": "ny bronkoskopi eller EBUS",
        "brain MRI before treatment decision": "MR caput før behandlingsbeslutning",
        "best supportive care": "best supportive care",
        "symptom-directed care and reassessment": "symptomrettet behandling og ny vurdering",
    },
    "da": {
        "thoracic surgery evaluation": "kirurgisk vurdering",
        "definitive chemoradiotherapy": "definitiv kemoradioterapi",
        "stereotactic radiotherapy assessment": "SABR-vurdering",
        "systemic therapy": "systemisk behandling",
        "palliative radiotherapy": "palliativ strålebehandling",
        "oncology review after biomarkers": "onkologisk vurdering efter biomarkører",
        "additional staging / biopsy": "yderligere stadieinddeling/biopsi",
        "repeat bronchoscopy or EBUS": "gentaget bronkoskopi eller EBUS",
        "brain MRI before treatment decision": "MR cerebrum før behandlingsbeslutning",
        "best supportive care": "best supportive care",
        "symptom-directed care and reassessment": "symptomrettet behandling og revurdering",
    },
    "is": {
        "thoracic surgery evaluation": "mat hjá brjóstholsskurðlækni",
        "definitive chemoradiotherapy": "endanleg lyfja- og geislameðferð",
        "stereotactic radiotherapy assessment": "mat fyrir SABR",
        "systemic therapy": "kerfismeðferð",
        "palliative radiotherapy": "líknandi geislameðferð",
        "oncology review after biomarkers": "krabbameinslæknismat eftir sameindamarkara",
        "additional staging / biopsy": "frekari stigun / vefjasýni",
        "repeat bronchoscopy or EBUS": "endurtekin berkjuspeglun eða EBUS",
        "brain MRI before treatment decision": "segulómun af heila fyrir meðferðarákvörðun",
        "best supportive care": "besta stuðningsmeðferð",
        "symptom-directed care and reassessment": "einkennamiðuð meðferð og endurmat",
    },
}


def make_queue(counts: dict, rng: random.Random) -> list:
    values = []
    for value, count in counts.items():
        values.extend([value] * count)
    rng.shuffle(values)
    return values


def split_for_index(index: int) -> str:
    if index <= 210:
        return "train"
    if index <= 255:
        return "dev"
    return "test"


def full_tnm(tnm: dict) -> str | None:
    if not all(tnm.get(k) for k in ("prefix", "t", "n", "m")):
        return None
    return f"{tnm['prefix']}{tnm['t']}{tnm['n']}{tnm['m']}"


def profile_to_tnm(profile: tuple[str, str, str, str, str]) -> dict:
    prefix, t, n, m, _stage = profile
    result = {
        "prefix": prefix,
        "t": t,
        "n": n,
        "m": m,
        "full": f"{prefix}{t}{n}{m}",
        "complete": True,
        "ambiguous": False,
        "edition": "unknown",
    }
    return result


def choose_distinct_profile(rng: random.Random, current_full: str) -> tuple[str, str, str, str, str]:
    all_profiles = [profile for profiles in TNM_PROFILES.values() for profile in profiles]
    choices = [profile for profile in all_profiles if profile_to_tnm(profile)["full"] != current_full]
    return rng.choice(choices)


def localized_markers(markers: dict) -> str:
    order = ["egfr", "alk", "ros1", "braf", "met", "ret", "ntrk", "kras", "pdl1"]
    return "; ".join(f"{key.upper() if key != 'pdl1' else 'PD-L1'} {markers[key]}" for key in order if markers[key] != "not_reported")


def build_biomarkers(category: str, histology: str, rng: random.Random) -> dict:
    markers = {
        "egfr": "not_reported",
        "alk": "not_reported",
        "ros1": "not_reported",
        "braf": "not_reported",
        "met": "not_reported",
        "ret": "not_reported",
        "ntrk": "not_reported",
        "kras": "not_reported",
        "pdl1": "not_reported",
    }
    if histology in {"adenocarcinoma", "NSCLC NOS"}:
        markers.update(
            {
                "egfr": "negative",
                "alk": "negative",
                "ros1": "negative",
                "pdl1": f"TPS {rng.choice([1, 5, 20, 40, 60, 80])}%",
            }
        )
    elif histology == "squamous cell carcinoma":
        markers.update({"pdl1": f"TPS {rng.choice([0, 10, 30, 55, 75])}%"})

    if category == "biomarker_treatment_complexity":
        variant = rng.choice(["egfr", "kras", "met_pending", "pdl1_high", "alk_pending"])
        if variant == "egfr":
            markers.update({"egfr": "exon 19 deletion", "alk": "negative", "ros1": "negative", "pdl1": "TPS 15%"})
        elif variant == "kras":
            markers.update({"egfr": "negative", "alk": "negative", "ros1": "negative", "kras": "G12C", "pdl1": "TPS 70%"})
        elif variant == "met_pending":
            markers.update({"egfr": "negative", "alk": "negative", "ros1": "negative", "met": "pending", "pdl1": "TPS 45%"})
        elif variant == "pdl1_high":
            markers.update({"egfr": "negative", "alk": "negative", "ros1": "negative", "braf": "negative", "pdl1": "TPS 95%"})
        elif variant == "alk_pending":
            markers.update({"egfr": "negative", "alk": "pending", "ros1": "negative", "ret": "negative", "pdl1": "TPS 5%"})
    return markers


def make_imaging_text(lang: str, tnm: dict, site: str, size: int) -> str:
    l10n = LOCAL[lang]
    site_text = SITE_LOCAL[lang][site]
    n_key = "nodes_none" if tnm.get("n") is None else f"nodes_{tnm['n']}"
    m_key = "mets_none" if tnm.get("m") is None else f"mets_{tnm['m']}"
    return l10n["imaging"].format(
        size=size,
        site=site_text,
        nodes=l10n.get(n_key, l10n["nodes_none"]),
        mets=l10n.get(m_key, l10n["mets_none"]),
    )


def make_tnm_sentence(lang: str, case: dict) -> str:
    l10n = LOCAL[lang]
    gt_tnm = case["ground_truth"]["tnm"]
    category = case["case_category"]
    if category == "partial_tnm":
        missing = [name.upper() for name in ("t", "n", "m") if gt_tnm.get(name) is None]
        return f"TNM: {gt_tnm['full']}; {l10n['tnm_missing'].format(component='/'.join(missing))}."
    if category == "conflicting_tnm":
        return f"{l10n['tnm_conflict']}: {case['tnm_conflict_a']} {l10n['conflict_and']} {case['tnm_conflict_b']}; {l10n['old_current_unclear']}."
    if category == "old_vs_current_staging":
        if gt_tnm["ambiguous"]:
            return f"{l10n['old_tnm']} {case['old_tnm']}; {l10n['later_tnm']} {case['current_candidate_tnm']}; {l10n['old_current_unclear']}."
        return f"{l10n['old_tnm']} {case['old_tnm']}; {l10n['current_tnm']} {gt_tnm['full']}."
    mode = case.get("tnm_path_mode")
    if mode in ("p", "yp"):
        return f"TNM: {gt_tnm['full']}; {l10n['path_p' if mode == 'p' else 'path_yp']}."
    return f"TNM: {gt_tnm['full']}."


def make_ecog_sentence(lang: str, case: dict) -> str:
    gt = case["ground_truth"]
    l10n = LOCAL[lang]
    if gt["ecog_status"] == "explicit":
        return f"{l10n['ecog_prefix']} {gt['ecog_ps']}"
    if gt["ecog_status"] == "missing":
        return l10n["missing_ecog"]
    return case["indirect_ecog_text"]


def make_mdt_evidence(lang: str, category: str) -> str:
    if category == "mdt_planned":
        return LOCAL[lang]["mdt_planned"]
    if category == "mdt_not_yet_discussed":
        return LOCAL[lang]["mdt_not_completed"]
    return LOCAL[lang]["mdt_completed"]


def make_review_reason(case: dict) -> str:
    q = case["quality_labels"]
    reasons = []
    if q["has_missing_ecog"]:
        reasons.append("missing ECOG")
    if q["has_partial_tnm"]:
        reasons.append("partial TNM")
    if q["has_conflict"]:
        reasons.append("conflicting TNM")
    if q["has_old_staging"] and case["ground_truth"]["tnm"]["ambiguous"]:
        reasons.append("old/current staging unclear")
    if q["has_future_mdt"]:
        reasons.append("future MDT")
    if q["has_indirect_ecog"]:
        reasons.append("indirect functional status")
    return ", ".join(reasons) if reasons else "none"


def render_note_text(case: dict, documentation_format: str) -> str:
    lang = case["language"]
    l10n = LOCAL[lang]
    gt = case["ground_truth"]
    histology_text = HISTOLOGY_LOCAL[lang][gt["histology"]]
    intent_text = INTENT_LOCAL[lang][gt["treatment_intent"]]
    recommendation_text = RECOMMENDATION_LOCAL[lang][gt["mdt_recommendation"]]
    tnm_sentence = make_tnm_sentence(lang, case)
    ecog_sentence = make_ecog_sentence(lang, case)
    bio_sentence = l10n["bio"].format(markers=localized_markers(gt["biomarkers"]))
    review = l10n["review_none"]
    if gt["review_required"]:
        review = l10n["review_flags"].format(reason=make_review_reason(case))

    if documentation_format == "free_text":
        intro = l10n["age_sex"].format(age=case["age"], sex=LOCAL[lang][case["sex_key"]])
        pieces = [
            f"{case['mdt_evidence']}.",
            f"{intro}, {LOCAL[lang][case['smoking_key']]}.",
            case["imaging_summary_text"],
            l10n["pathology"].format(histology=histology_text),
            tnm_sentence,
            f"{ecog_sentence}.",
            bio_sentence,
            l10n["recommend"].format(recommendation=recommendation_text),
        ]
        return l10n["free_join"].join(pieces)

    if documentation_format == "structured_mini":
        h = l10n["mini"]
        return "\n".join(
            [
                f"{h['mdt']}: {case['mdt_evidence']}",
                f"{h['imaging']}: {case['imaging_summary_text']}",
                f"{h['pathology']}: {l10n['pathology'].format(histology=histology_text)}",
                f"{h['stage']}: stage {gt['stage_group']}; {tnm_sentence}",
                f"{h['ecog']}: {ecog_sentence}",
                f"{h['recommendation']}: {recommendation_text}",
            ]
        )

    h = l10n["v31"]
    return "\n".join(
        [
            f"{h['patient']}: {l10n['fictional_adult']}; {case['age']} years; {LOCAL[lang][case['sex_key']]}; {LOCAL[lang][case['smoking_key']]}",
            f"{h['diagnostic']}: synthetic MDT preparation note; source data are fictional.",
            f"{h['imaging']}: {case['imaging_summary_text']}",
            f"{h['pathology']}: {l10n['pathology'].format(histology=histology_text)}",
            f"{h['molecular']}: {localized_markers(gt['biomarkers'])}",
            f"{h['tnm']}: stage {gt['stage_group']}; {tnm_sentence}",
            f"{h['ecog']}: {ecog_sentence}",
            f"{h['intent']}: {intent_text}",
            f"{h['recommendation']}: {recommendation_text}; {case['mdt_evidence']}",
            f"{h['review']}: {review}",
        ]
    )


def make_case(lang: str, index: int, category: str, queues: dict, rng: random.Random) -> dict:
    case_id = f"{lang}_{index:04d}"
    histology = queues["histology"].pop()
    treatment_intent = queues["treatment_intent"].pop()
    recommendation = rng.choice(RECOMMENDATIONS[treatment_intent])
    sex_key = rng.choice(["male", "female", "unspecified"])
    smoking_key = rng.choice(["smoking_current", "smoking_former", "smoking_never"])
    age = rng.randint(48, 86)

    if category == "partial_tnm":
        stage_group = "unclear"
        base_stage = rng.choice(["I", "II", "III", "IV"])
    else:
        base_stage = queues["stage_bucket"].pop()
        stage_group = None

    profile = rng.choice(TNM_PROFILES[base_stage])
    tnm = profile_to_tnm(profile)
    if stage_group is None:
        stage_group = profile[4]

    # A minority of clear, complete cases are pathological (post-resection 'p' / post-neoadjuvant
    # 'yp') rather than baseline clinical 'c', with a coherent staging-context phrase in the note.
    # Pathological staging only on non-metastatic disease (resection / neoadjuvant is for M0).
    tnm_path_mode = None
    if category == "clear_explicit" and tnm["m"] == "M0":
        tnm_path_mode = rng.choices(["c", "p", "yp"], weights=[70, 20, 10])[0]
        if tnm_path_mode != "c":
            tnm["prefix"] = tnm_path_mode
            tnm["full"] = f"{tnm_path_mode}{tnm['t']}{tnm['n']}{tnm['m']}"
        else:
            tnm_path_mode = None

    site, base_size = rng.choice(TUMOUR_SITES)
    size = max(8, base_size + rng.randint(-5, 8))

    old_tnm = None
    current_candidate_tnm = None
    tnm_conflict_a = None
    tnm_conflict_b = None
    tnm_requires_review = False
    old_staging_ambiguous = False

    if category == "partial_tnm":
        missing_component = rng.choice(["t", "n", "m"])
        tnm[missing_component] = None
        partial_parts = [tnm["prefix"]]
        for key in ("t", "n", "m"):
            if tnm.get(key):
                partial_parts.append(tnm[key])
        tnm["full"] = "".join(partial_parts)
        tnm["complete"] = False
        tnm["ambiguous"] = False
        tnm_requires_review = True
    elif category == "conflicting_tnm":
        first = tnm["full"]
        second = profile_to_tnm(choose_distinct_profile(rng, first))["full"]
        tnm_conflict_a = first
        tnm_conflict_b = second
        tnm = {
            "prefix": None,
            "t": None,
            "n": None,
            "m": None,
            "full": None,
            "complete": False,
            "ambiguous": True,
            "edition": "unknown",
        }
        stage_group = "unclear"
        tnm_requires_review = True
    elif category == "old_vs_current_staging":
        old_profile = choose_distinct_profile(rng, tnm["full"])
        old_tnm = profile_to_tnm(old_profile)["full"]
        old_staging_ambiguous = index % 2 == 0
        current_candidate_tnm = tnm["full"]
        if old_staging_ambiguous:
            tnm = {
                "prefix": None,
                "t": None,
                "n": None,
                "m": None,
                "full": None,
                "complete": False,
                "ambiguous": True,
                "edition": "unknown",
            }
            stage_group = "unclear"
            tnm_requires_review = True

    if category in {"missing_ecog", "indirect_functional_status"}:
        ecog_ps = None
        ecog_status = "missing" if category == "missing_ecog" else "indirect"
    else:
        ecog_ps = queues["ecog"].pop()
        ecog_status = "explicit"

    mdt_status = "completed"
    mdt_discussed = True
    if category == "mdt_planned":
        mdt_status = "planned"
        mdt_discussed = False
    elif category == "mdt_not_yet_discussed":
        mdt_status = "not_completed"
        mdt_discussed = False

    biomarkers = build_biomarkers(category, histology, rng)
    imaging_summary_text = make_imaging_text(lang, tnm if tnm.get("full") else profile_to_tnm(profile), site, size)
    pathology_summary = f"synthetic {histology} pathology/cytology"
    mdt_evidence = make_mdt_evidence(lang, category)
    indirect_ecog_text = rng.choice(INDIRECT_FUNCTION[lang])

    quality = {
        "has_negation": category == "mdt_not_yet_discussed",
        "has_conflict": category == "conflicting_tnm" or old_staging_ambiguous,
        "has_missing_ecog": category == "missing_ecog",
        "has_partial_tnm": category == "partial_tnm",
        "has_old_staging": category == "old_vs_current_staging",
        "has_future_mdt": category == "mdt_planned",
        "has_indirect_ecog": category == "indirect_functional_status",
        "requires_review": False,
        "registry_ready": True,
    }
    quality["requires_review"] = any(
        [
            quality["has_missing_ecog"],
            quality["has_partial_tnm"],
            quality["has_conflict"],
            quality["has_future_mdt"],
            quality["has_indirect_ecog"],
        ]
    )
    quality["registry_ready"] = not quality["requires_review"]

    diagnostic_uncertainty = "none"
    if quality["requires_review"]:
        diagnostic_uncertainty = make_review_reason(
            {
                "quality_labels": quality,
                "ground_truth": {"tnm": tnm},
            }
        )

    ground_truth = {
        "mdt_discussed": mdt_discussed,
        "mdt_status": mdt_status,
        "ecog_ps": ecog_ps,
        "ecog_status": ecog_status,
        "tnm": tnm,
        "stage_group": stage_group,
        "histology": histology,
        "biomarkers": biomarkers,
        "treatment_intent": treatment_intent,
        "mdt_recommendation": recommendation,
        "imaging_summary": f"{site}, {size} mm; stage bucket {base_stage}",
        "pathology_summary": pathology_summary,
        "diagnostic_uncertainty": diagnostic_uncertainty,
        "review_required": quality["requires_review"],
    }

    case = {
        "dataset_version": DATASET_VERSION,
        "case_id": case_id,
        "case_category": category,
        "language": lang,
        "source_type": "synthetic",
        "messiness": "clean"
        if category == "clear_explicit"
        else "semistructured"
        if category in {"missing_ecog", "partial_tnm", "biomarker_treatment_complexity"}
        else "messy",
        "split_hint": split_for_index(index),
        "ground_truth": ground_truth,
        "quality_labels": quality,
        "age": age,
        "sex_key": sex_key,
        "smoking_key": smoking_key,
        "mdt_evidence": mdt_evidence,
        "imaging_summary_text": imaging_summary_text,
        "indirect_ecog_text": indirect_ecog_text,
        "old_tnm": old_tnm,
        "current_candidate_tnm": current_candidate_tnm,
        "tnm_conflict_a": tnm_conflict_a,
        "tnm_conflict_b": tnm_conflict_b,
        "tnm_path_mode": tnm_path_mode,
    }
    return case


def expected_output_for_case(case: dict) -> dict:
    lang = case["language"]
    gt = case["ground_truth"]
    category = case["case_category"]
    tnm = gt["tnm"]

    if gt["ecog_status"] == "explicit":
        ecog_value = gt["ecog_ps"]
        ecog_evidence = f"{LOCAL[lang]['ecog_prefix']} {gt['ecog_ps']}"
        ecog_review = False
    elif gt["ecog_status"] == "missing":
        ecog_value = None
        ecog_evidence = LOCAL[lang]["missing_ecog"]
        ecog_review = True
    else:
        ecog_value = None
        ecog_evidence = case["indirect_ecog_text"]
        ecog_review = True

    tnm_value = None
    tnm_evidence = None
    if tnm["complete"] and not tnm["ambiguous"]:
        tnm_value = tnm["full"]
        tnm_evidence = tnm["full"]
    elif category == "partial_tnm":
        tnm_evidence = tnm["full"]
    elif category == "conflicting_tnm":
        tnm_evidence = LOCAL[lang]["tnm_conflict"]
    elif category == "old_vs_current_staging" and tnm["ambiguous"]:
        tnm_evidence = LOCAL[lang]["old_current_unclear"]

    return {
        "mdt_discussed": {
            "value": gt["mdt_discussed"],
            "evidence": case["mdt_evidence"],
            "requires_review": category == "mdt_planned",
        },
        "ecog_ps": {
            "value": ecog_value,
            "evidence": ecog_evidence,
            "requires_review": ecog_review,
        },
        "tnm": {
            "value": tnm_value,
            "components": {
                "prefix": tnm.get("prefix"),
                "t": tnm.get("t"),
                "n": tnm.get("n"),
                "m": tnm.get("m"),
            },
            "evidence": tnm_evidence,
            "requires_review": (not tnm["complete"]) or tnm["ambiguous"],
        },
    }


def record_for_case(case: dict, documentation_format: str) -> dict:
    record = {
        "dataset_version": case["dataset_version"],
        "case_id": case["case_id"],
        "case_category": case["case_category"],
        "record_id": f"{case['case_id']}_{documentation_format}",
        "language": case["language"],
        "source_type": case["source_type"],
        "documentation_format": documentation_format,
        "messiness": case["messiness"],
        "split_hint": case["split_hint"],
        "ground_truth": copy.deepcopy(case["ground_truth"]),
        "note_text": render_note_text(case, documentation_format),
        "expected_output": expected_output_for_case(case),
        "quality_labels": copy.deepcopy(case["quality_labels"]),
    }
    return record


def generate_language(lang: str, lang_index: int) -> list[dict]:
    rng = random.Random(BASE_SEED + (lang_index * 1000))
    categories = make_queue(CASE_CATEGORY_COUNTS, rng)
    queues = {
        "histology": make_queue(HISTOLOGY_COUNTS, rng),
        "stage_bucket": make_queue(STAGE_BUCKET_COUNTS, rng),
        "treatment_intent": make_queue(TREATMENT_INTENT_COUNTS, rng),
        "ecog": make_queue(EXPLICIT_ECOG_COUNTS, rng),
    }
    records = []
    for index, category in enumerate(categories, start=1):
        case = make_case(lang, index, category, queues, rng)
        for documentation_format in DOCUMENTATION_FORMATS:
            records.append(record_for_case(case, documentation_format))

    if any(queues[name] for name in queues):
        leftovers = {name: len(value) for name, value in queues.items()}
        raise RuntimeError(f"Unconsumed queue values for {lang}: {leftovers}")
    return records


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def generate_all() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for lang_index, lang in enumerate(LANGUAGES):
        rows = generate_language(lang, lang_index)
        write_jsonl(DATA_DIR / f"synthetic_mdt_{lang}.jsonl", rows)


def run_validator() -> None:
    validator = ROOT / "scripts" / "validate_dataset.py"
    subprocess.run([sys.executable, str(validator), str(ROOT)], check=True)


def main() -> None:
    generate_all()
    run_validator()
    print(f"Generated and validated {ROOT}")


if __name__ == "__main__":
    main()
