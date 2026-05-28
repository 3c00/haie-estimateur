import json
import os
import pickle
import random
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score
from sklearn.model_selection import train_test_split

TRAINING_DATA_FILE = Path("training_data.json")
MODEL_FILE = Path("model.pkl")

TYPES_JOB = ["taille normale", "nivelage", "restoration", "cèdre solo / petit arbre"]
DENSITES = ["légère", "moyenne", "dense"]
ACCES = ["facile", "moyen", "difficile"]

DONNEES_EXEMPLE = [
    {"type_job": "taille normale", "longueur_pieds": 40, "hauteur_pieds": 8, "densite": "moyenne", "acces": "facile", "deux_cotes": False, "supplement_difficulte": 0, "prix_reel": 110},
    {"type_job": "taille normale", "longueur_pieds": 80, "hauteur_pieds": 10, "densite": "dense", "acces": "moyen", "deux_cotes": True, "supplement_difficulte": 25, "prix_reel": 385},
    {"type_job": "taille normale", "longueur_pieds": 60, "hauteur_pieds": 11, "densite": "moyenne", "acces": "facile", "deux_cotes": False, "supplement_difficulte": 0, "prix_reel": 180},
    {"type_job": "taille normale", "longueur_pieds": 30, "hauteur_pieds": 4, "densite": "légère", "acces": "facile", "deux_cotes": False, "supplement_difficulte": 0, "prix_reel": 60},
    {"type_job": "taille normale", "longueur_pieds": 100, "hauteur_pieds": 14, "densite": "dense", "acces": "difficile", "deux_cotes": True, "supplement_difficulte": 50, "prix_reel": 575},
    {"type_job": "taille normale", "longueur_pieds": 50, "hauteur_pieds": 6, "densite": "moyenne", "acces": "facile", "deux_cotes": False, "supplement_difficulte": 0, "prix_reel": 137.50},
    {"type_job": "nivelage", "longueur_pieds": 40, "hauteur_pieds": 10, "densite": "dense", "acces": "moyen", "deux_cotes": False, "supplement_difficulte": 25, "prix_reel": 265},
    {"type_job": "nivelage", "longueur_pieds": 25, "hauteur_pieds": 8, "densite": "moyenne", "acces": "facile", "deux_cotes": False, "supplement_difficulte": 0, "prix_reel": 150},
    {"type_job": "nivelage", "longueur_pieds": 50, "hauteur_pieds": 12, "densite": "dense", "acces": "difficile", "deux_cotes": False, "supplement_difficulte": 50, "prix_reel": 350},
    {"type_job": "restoration", "longueur_pieds": 30, "hauteur_pieds": 8, "densite": "dense", "acces": "facile", "deux_cotes": False, "supplement_difficulte": 0, "prix_reel": 135},
    {"type_job": "restoration", "longueur_pieds": 45, "hauteur_pieds": 10, "densite": "dense", "acces": "moyen", "deux_cotes": False, "supplement_difficulte": 25, "prix_reel": 227.50},
    {"type_job": "restoration", "longueur_pieds": 20, "hauteur_pieds": 6, "densite": "moyenne", "acces": "facile", "deux_cotes": False, "supplement_difficulte": 0, "prix_reel": 80},
    {"type_job": "taille normale", "longueur_pieds": 15, "hauteur_pieds": 3, "densite": "légère", "acces": "facile", "deux_cotes": False, "supplement_difficulte": 0, "prix_reel": 30},
    {"type_job": "taille normale", "longueur_pieds": 70, "hauteur_pieds": 9, "densite": "moyenne", "acces": "facile", "deux_cotes": True, "supplement_difficulte": 0, "prix_reel": 288.75},
    {"type_job": "nivelage", "longueur_pieds": 60, "hauteur_pieds": 14, "densite": "dense", "acces": "difficile", "deux_cotes": False, "supplement_difficulte": 50, "prix_reel": 410},
    {"type_job": "restoration", "longueur_pieds": 35, "hauteur_pieds": 9, "densite": "dense", "acces": "moyen", "deux_cotes": False, "supplement_difficulte": 0, "prix_reel": 175},
    {"type_job": "cèdre solo / petit arbre", "longueur_pieds": 1, "hauteur_pieds": 7, "densite": "moyenne", "acces": "facile", "deux_cotes": False, "supplement_difficulte": 0, "prix_reel": 40},
    {"type_job": "cèdre solo / petit arbre", "longueur_pieds": 1, "hauteur_pieds": 15, "densite": "moyenne", "acces": "difficile", "deux_cotes": False, "supplement_difficulte": 50, "prix_reel": 100},
    {"type_job": "taille normale", "longueur_pieds": 120, "hauteur_pieds": 18, "densite": "dense", "acces": "difficile", "deux_cotes": True, "supplement_difficulte": 50, "prix_reel": 680},
    {"type_job": "taille normale", "longueur_pieds": 25, "hauteur_pieds": 5, "densite": "légère", "acces": "facile", "deux_cotes": False, "supplement_difficulte": 0, "prix_reel": 50},
]


def encoder_caracteristiques(type_job, densite, acces):
    return (
        [1 if type_job == t else 0 for t in TYPES_JOB]
        + [1 if densite == d else 0 for d in DENSITES]
        + [1 if acces == a else 0 for a in ACCES]
    )


def preparer_donnees(donnees):
    X, y = [], []
    for d in donnees:
        caracteristiques = encoder_caracteristiques(d["type_job"], d["densite"], d["acces"])
        X.append(caracteristiques + [d["longueur_pieds"], d["hauteur_pieds"], int(d["deux_cotes"]), d["supplement_difficulte"]])
        y.append(d["prix_reel"])
    return np.array(X), np.array(y)


def charger_donnees():
    if TRAINING_DATA_FILE.exists():
        with open(TRAINING_DATA_FILE, "r") as f:
            return json.load(f)
    return list(DONNEES_EXEMPLE)


def sauvegarder_donnees(donnees):
    with open(TRAINING_DATA_FILE, "w") as f:
        json.dump(donnees, f, indent=2, ensure_ascii=False)


def entrainer_modele():
    donnees = charger_donnees()
    X, y = preparer_donnees(donnees)

    if len(donnees) < 3:
        return None, 0.0

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    modele = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
    modele.fit(X_train, y_train)

    with open(MODEL_FILE, "wb") as f:
        pickle.dump(modele, f)

    score = r2_score(y_test, modele.predict(X_test)) if len(y_test) > 1 else 0.0
    return modele, score


def charger_modele():
    if MODEL_FILE.exists():
        with open(MODEL_FILE, "rb") as f:
            return pickle.load(f)
    return entrainer_modele()[0]


def ajouter_correction(type_job, longueur_pieds, hauteur_pieds, densite, acces, deux_cotes, supplement_difficulte, prix_estime, prix_reel):
    donnees = charger_donnees()
    donnees.append({
        "type_job": type_job,
        "longueur_pieds": longueur_pieds,
        "hauteur_pieds": hauteur_pieds,
        "densite": densite,
        "acces": acces,
        "deux_cotes": deux_cotes,
        "supplement_difficulte": supplement_difficulte,
        "prix_reel": prix_reel,
    })
    sauvegarder_donnees(donnees)


def calculer_prix_fallback(type_job, longueur_pieds, hauteur_pieds, densite, acces, deux_cotes, supplement_difficulte):
    taux_horaire = None
    if type_job == "taille normale":
        if hauteur_pieds < 5:
            taux_horaire = 2.0
        elif hauteur_pieds <= 6:
            taux_horaire = 2.75
        elif hauteur_pieds <= 10:
            taux_horaire = 2.75
        elif hauteur_pieds <= 12:
            taux_horaire = 3.0
        elif hauteur_pieds <= 20:
            taux_horaire = 3.5
        else:
            taux_horaire = None
    elif type_job == "nivelage":
        taux_horaire = 6.0
    elif type_job == "restoration":
        taux_horaire = 4.25
    elif type_job == "cèdre solo / petit arbre":
        return estimer_prix_solo(longueur_pieds, hauteur_pieds, acces, supplement_difficulte), 0.5, ["Sécateur", "Gants"]

    if taux_horaire is None:
        return 0, 0, ["Nous contacter - devis personnalisé"]

    prix_base = taux_horaire * longueur_pieds

    multiplicateur_densite = {"légère": 1.0, "moyenne": 1.0, "dense": 1.15}
    prix_base *= multiplicateur_densite.get(densite, 1.0)

    if deux_cotes:
        prix_base *= 1.5

    prix_base += supplement_difficulte

    temps = estimer_temps(longueur_pieds, hauteur_pieds, densite, acces)
    equipement = recommander_equipement(hauteur_pieds, densite, acces, type_job)

    return round(prix_base, 2), round(temps, 1), equipement


def estimer_prix_solo(longueur_pieds, hauteur_pieds, acces, supplement_difficulte):
    prix_base = 30 + (hauteur_pieds * 3)
    if acces == "difficile":
        prix_base *= 1.3
    prix_base += supplement_difficulte
    return round(max(prix_base, 30), 2)


def estimer_prix(type_job, longueur_pieds, hauteur_pieds, densite, acces, deux_cotes, supplement_difficulte):
    modele = charger_modele()

    if modele is None:
        return calculer_prix_fallback(type_job, longueur_pieds, hauteur_pieds, densite, acces, deux_cotes, supplement_difficulte)

    if type_job == "cèdre solo / petit arbre":
        prix = estimer_prix_solo(longueur_pieds, hauteur_pieds, acces, supplement_difficulte)
        temps = 0.5
        equipement = recommander_equipement(hauteur_pieds, densite, acces, type_job)
        return prix, temps, equipement

    caracteristiques = encoder_caracteristiques(type_job, densite, acces)
    X = np.array([caracteristiques + [longueur_pieds, hauteur_pieds, int(deux_cotes), supplement_difficulte]])

    prix = float(modele.predict(X)[0])
    temps = estimer_temps(longueur_pieds, hauteur_pieds, densite, acces)
    equipement = recommander_equipement(hauteur_pieds, densite, acces, type_job)

    return round(prix, 2), round(temps, 1), equipement


def estimer_temps(longueur_pieds, hauteur_pieds, densite, acces):
    multiplicateur_densite = {"légère": 1.0, "moyenne": 1.3, "dense": 1.8}
    multiplicateur_acces = {"facile": 1.0, "moyen": 1.2, "difficile": 1.5}
    heures_base = (longueur_pieds / 15) * (hauteur_pieds / 6)
    return heures_base * multiplicateur_densite.get(densite, 1.0) * multiplicateur_acces.get(acces, 1.0)


def recommander_equipement(hauteur_pieds, densite, acces, type_job):
    equipement = ["Sécateur", "Gants de protection"]
    if type_job in ("nivelage", "restoration"):
        equipement.append("Taille-haie électrique")
    if hauteur_pieds > 10:
        equipement.append("Perche télescopique")
    if hauteur_pieds > 15:
        equipement.append("Nacelle")
    if densite == "dense":
        equipement.append("Taille-haie électrique")
    if acces == "difficile":
        equipement.append("Harnais de sécurité")
    if type_job == "nivelage":
        equipement.append("Chainsaw")
    return equipement


if __name__ == "__main__":
    modele, score = entrainer_modele()
    print(f"Modèle entraîné avec un score R² de {score:.3f}")
