import json
import os
from pathlib import Path

HISTORIQUE_FILE = Path("historique.json")
REGLAGES_FILE = Path("reglages.json")
ANCIEN_ENTRAINEMENT_FILE = Path("training_data.json")
DATA_DIR = Path("data")

REGLAGES_DEFAUT = {
    "taux_moins_5": 2.0,
    "taux_5_10": 2.75,
    "taux_10_12": 3.0,
    "taux_12_20": 3.5,
    "taux_nivelage": 6.0,
    "taux_restoration": 4.25,
    "solo_base": 30.0,
    "solo_par_pied": 3.0,
    "mult_acces_difficile_solo": 1.3,
    "mult_dense": 1.15,
    "mult_deux_cotes": 1.5,
    "prix_minimum": 0.0,
    "arrondi": 5.0,
    "facturer_taxes": False,
    "entreprise_nom": "",
    "entreprise_telephone": "",
    "entreprise_courriel": "",
    "entreprise_adresse": "",
    "numero_tps": "",
    "numero_tvq": "",
    "validite_jours": 30,
}

TPS = 0.05
TVQ = 0.09975

# Exemples fictifs fournis par l'ancienne version : copiés dans training_data.json à la première correction.
_ANCIENS_EXEMPLES = {
    ("taille normale", 40, 8, 110), ("taille normale", 80, 10, 385), ("taille normale", 60, 11, 180),
    ("taille normale", 30, 4, 60), ("taille normale", 100, 14, 575), ("taille normale", 50, 6, 137.5),
    ("nivelage", 40, 10, 265), ("nivelage", 25, 8, 150), ("nivelage", 50, 12, 350),
    ("restoration", 30, 8, 135), ("restoration", 45, 10, 227.5), ("restoration", 20, 6, 80),
    ("taille normale", 15, 3, 30), ("taille normale", 70, 9, 288.75), ("nivelage", 60, 14, 410),
    ("restoration", 35, 9, 175), ("cèdre solo / petit arbre", 1, 7, 40),
    ("cèdre solo / petit arbre", 1, 15, 100), ("taille normale", 120, 18, 680),
    ("taille normale", 25, 5, 50),
}


def _est_ancien_exemple(j):
    try:
        cle = (j["type_job"], float(j["longueur_pieds"]), float(j["hauteur_pieds"]), float(j["prix_reel"]))
    except (KeyError, TypeError, ValueError):
        return False
    return cle in _ANCIENS_EXEMPLES


def lire_json(chemin, defaut):
    if not chemin.exists():
        return defaut
    brut = chemin.read_bytes()
    # Les anciennes versions écrivaient avec l'encodage Windows par défaut.
    for enc in ("utf-8", "cp1252"):
        try:
            return json.loads(brut.decode(enc))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return defaut


def ecrire_json(chemin, contenu):
    tmp = chemin.with_suffix(chemin.suffix + ".tmp")
    tmp.write_text(json.dumps(contenu, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, chemin)


def charger_reglages():
    return {**REGLAGES_DEFAUT, **lire_json(REGLAGES_FILE, {})}


def sauvegarder_reglages(reglages):
    ecrire_json(REGLAGES_FILE, reglages)


def charger_jobs():
    jobs = lire_json(HISTORIQUE_FILE, [])
    prochain = max((j.get("id", 0) for j in jobs), default=0) + 1
    modifie = False
    for j in jobs:
        if "id" not in j:
            j["id"] = prochain
            j["ancien_format"] = True
            prochain += 1
            modifie = True
    if modifie:
        ecrire_json(HISTORIQUE_FILE, jobs)
    return jobs


def sauvegarder_jobs(jobs):
    ecrire_json(HISTORIQUE_FILE, jobs)


def ajouter_job(job):
    jobs = charger_jobs()
    job["id"] = max((j["id"] for j in jobs), default=0) + 1
    jobs.append(job)
    sauvegarder_jobs(jobs)
    return job


def trouver_job(job_id):
    return next((j for j in charger_jobs() if j["id"] == job_id), None)


def modifier_job(job_id, **champs):
    jobs = charger_jobs()
    for j in jobs:
        if j["id"] == job_id:
            j.update(champs)
            sauvegarder_jobs(jobs)
            return j
    return None


def supprimer_job(job_id):
    sauvegarder_jobs([j for j in charger_jobs() if j["id"] != job_id])


def _est_complet(j):
    return all(j.get(k) not in (None, "") for k in ("type_job", "longueur_pieds", "hauteur_pieds", "densite", "acces"))


def jobs_reels():
    """Jobs dont on connaît le vrai prix : base de l'ajustement automatique."""
    from model import TYPES_JOB

    reels = [
        j for j in charger_jobs()
        if not j.get("ancien_format") and j.get("prix_reel") and _est_complet(j)
    ]
    # Corrections faites avec l'ancienne version (sans les exemples copiés de la grille).
    for j in lire_json(ANCIEN_ENTRAINEMENT_FILE, []):
        if _est_ancien_exemple(j) or not _est_complet(j) or j["type_job"] not in TYPES_JOB:
            continue
        if j.get("prix_reel"):
            reels.append(j)
    return reels
