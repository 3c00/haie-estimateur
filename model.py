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

DONNEES_EXEMPLE = [
    {"type_haie": "cèdre", "longueur_m": 10, "hauteur_m": 2.0, "densite": "moyenne", "acces": "facile", "prix_reel": 350},
    {"type_haie": "cèdre", "longueur_m": 25, "hauteur_m": 3.0, "densite": "dense", "acces": "difficile", "prix_reel": 1200},
    {"type_haie": "thuya", "longueur_m": 8, "hauteur_m": 1.5, "densite": "légère", "acces": "facile", "prix_reel": 200},
    {"type_haie": "thuya", "longueur_m": 15, "hauteur_m": 2.5, "densite": "moyenne", "acces": "moyen", "prix_reel": 550},
    {"type_haie": "lilas", "longueur_m": 5, "hauteur_m": 3.0, "densite": "dense", "acces": "facile", "prix_reel": 400},
    {"type_haie": "lilas", "longueur_m": 20, "hauteur_m": 4.0, "densite": "dense", "acces": "difficile", "prix_reel": 1800},
    {"type_haie": "chèvrefeuille", "longueur_m": 12, "hauteur_m": 1.8, "densite": "moyenne", "acces": "facile", "prix_reel": 320},
    {"type_haie": "chèvrefeuille", "longueur_m": 6, "hauteur_m": 1.2, "densite": "légère", "acces": "facile", "prix_reel": 180},
    {"type_haie": "cèdre", "longueur_m": 30, "hauteur_m": 3.5, "densite": "dense", "acces": "moyen", "prix_reel": 1500},
    {"type_haie": "thuya", "longueur_m": 40, "hauteur_m": 4.0, "densite": "dense", "acces": "difficile", "prix_reel": 2000},
    {"type_haie": "cèdre", "longueur_m": 7, "hauteur_m": 1.8, "densite": "légère", "acces": "facile", "prix_reel": 220},
    {"type_haie": "lilas", "longueur_m": 3, "hauteur_m": 2.0, "densite": "moyenne", "acces": "facile", "prix_reel": 180},
    {"type_haie": "chèvrefeuille", "longueur_m": 18, "hauteur_m": 2.2, "densite": "dense", "acces": "moyen", "prix_reel": 650},
    {"type_haie": "cèdre", "longueur_m": 14, "hauteur_m": 2.5, "densite": "moyenne", "acces": "facile", "prix_reel": 480},
    {"type_haie": "thuya", "longueur_m": 22, "hauteur_m": 3.0, "densite": "moyenne", "acces": "difficile", "prix_reel": 950},
    {"type_haie": "cèdre", "longueur_m": 50, "hauteur_m": 5.0, "densite": "dense", "acces": "difficile", "prix_reel": 2800},
    {"type_haie": "lilas", "longueur_m": 9, "hauteur_m": 2.8, "densite": "moyenne", "acces": "moyen", "prix_reel": 420},
    {"type_haie": "chèvrefeuille", "longueur_m": 4, "hauteur_m": 1.0, "densite": "légère", "acces": "facile", "prix_reel": 150},
    {"type_haie": "cèdre", "longueur_m": 35, "hauteur_m": 4.5, "densite": "dense", "acces": "moyen", "prix_reel": 1900},
    {"type_haie": "thuya", "longueur_m": 11, "hauteur_m": 2.0, "densite": "légère", "acces": "facile", "prix_reel": 280},
]

TYPES_HAIE = ["cèdre", "thuya", "lilas", "chèvrefeuille"]
DENSITES = ["légère", "moyenne", "dense"]
ACCES = ["facile", "moyen", "difficile"]


def encoder_caracteristiques(type_haie, densite, acces):
    return [
        1 if type_haie == t else 0 for t in TYPES_HAIE
    ] + [
        1 if densite == d else 0 for d in DENSITES
    ] + [
        1 if acces == a else 0 for a in ACCES
    ]


def preparer_donnees(donnees):
    X, y = [], []
    for d in donnees:
        caracteristiques = encoder_caracteristiques(d["type_haie"], d["densite"], d["acces"])
        X.append(caracteristiques + [d["longueur_m"], d["hauteur_m"]])
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


def ajouter_correction(type_haie, longueur_m, hauteur_m, densite, acces, prix_estime, prix_reel):
    donnees = charger_donnees()
    donnees.append({
        "type_haie": type_haie,
        "longueur_m": longueur_m,
        "hauteur_m": hauteur_m,
        "densite": densite,
        "acces": acces,
        "prix_reel": prix_reel,
    })
    sauvegarder_donnees(donnees)


def estimer_prix(type_haie, longueur_m, hauteur_m, densite, acces):
    modele = charger_modele()

    if modele is None:
        return calculer_prix_fallback(type_haie, longueur_m, hauteur_m, densite, acces)

    caracteristiques = encoder_caracteristiques(type_haie, densite, acces)
    X = np.array([caracteristiques + [longueur_m, hauteur_m]])

    prix = modele.predict(X)[0]
    temps = estimer_temps(longueur_m, hauteur_m, densite, acces)
    equipement = recommander_equipement(hauteur_m, densite, acces)

    return round(float(prix), 2), round(temps, 1), equipement


def calculer_prix_fallback(type_haie, longueur_m, hauteur_m, densite, acces):
    prix_base = {"cèdre": 35, "thuya": 25, "lilas": 40, "chèvrefeuille": 28}
    multiplicateur_densite = {"légère": 1.0, "moyenne": 1.3, "dense": 1.7}
    multiplicateur_acces = {"facile": 1.0, "moyen": 1.25, "difficile": 1.6}

    prix = (
        prix_base.get(type_haie, 30)
        * longueur_m
        * (hauteur_m / 1.5)
        * multiplicateur_densite.get(densite, 1.0)
        * multiplicateur_acces.get(acces, 1.0)
    )

    temps = estimer_temps(longueur_m, hauteur_m, densite, acces)
    equipement = recommander_equipement(hauteur_m, densite, acces)

    return round(prix, 2), round(temps, 1), equipement


def estimer_temps(longueur_m, hauteur_m, densite, acces):
    multiplicateur_densite = {"légère": 1.0, "moyenne": 1.4, "dense": 2.0}
    multiplicateur_acces = {"facile": 1.0, "moyen": 1.3, "difficile": 1.7}
    heures_base = longueur_m * 0.3 * (hauteur_m / 1.5)
    return heures_base * multiplicateur_densite.get(densite, 1.0) * multiplicateur_acces.get(acces, 1.0)


def recommander_equipement(hauteur_m, densite, acces):
    equipement = ["Sécateur", "Gants de protection"]
    if hauteur_m > 2.5:
        equipement.append("Perche télescopique")
    if hauteur_m > 3.5:
        equipement.append("Nacelle")
    if densite == "dense":
        equipement.append("Taille-haie électrique")
    if acces == "difficile":
        equipement.append("Harnais de sécurité")
    return equipement


if __name__ == "__main__":
    modele, score = entrainer_modele()
    print(f"Modèle entraîné avec un score R² de {score:.3f}")
