import base64
import json
import os
from io import BytesIO

import requests
from dotenv import load_dotenv
from PIL import Image

from model import ACCES, DENSITES, TYPES_JOB

load_dotenv()

URL_API = "https://api.deepseek.com/chat/completions"
# Le nom du modèle qui accepte les images a changé plusieurs fois : on essaie dans l'ordre.
MODELES_PAR_DEFAUT = ["deepseek-flash", "deepseek-v4-flash-vision-exp"]


def encoder_image(image: Image.Image) -> str:
    image = image.convert("RGB")
    image.thumbnail((1280, 1280))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _consigne():
    return (
        "Tu es un expert québécois en taille de haies de cèdres. Analyse la photo et estime le travail. "
        "Réponds UNIQUEMENT avec un objet JSON, sans texte autour, avec exactement ces clés :\n"
        f'"type_job": une valeur parmi {json.dumps(TYPES_JOB, ensure_ascii=False)} '
        "(nivelage = baisser la hauteur, restoration = haie négligée à reformer),\n"
        '"hauteur_pieds": nombre (hauteur de la haie en pieds),\n'
        '"longueur_pieds": nombre (longueur visible en pieds linéaires),\n'
        f'"densite": une valeur parmi {json.dumps(DENSITES, ensure_ascii=False)},\n'
        f'"acces": une valeur parmi {json.dumps(ACCES, ensure_ascii=False)},\n'
        '"commentaire": une phrase courte sur ce que tu vois.'
    )


def _extraire_json(texte):
    debut, fin = texte.find("{"), texte.rfind("}")
    if debut == -1 or fin == -1:
        raise ValueError("pas de JSON dans la réponse")
    return json.loads(texte[debut:fin + 1])


def analyser_photo(image: Image.Image):
    """Retourne (resultat, message_erreur). Un seul des deux est rempli."""
    cle_api = os.getenv("DEEPSEEK_API_KEY")
    if not cle_api or cle_api == "sk-votre-cle-ici":
        return None, "Aucune clé DeepSeek : crée un fichier .env avec DEEPSEEK_API_KEY=ta-clé (voir .env.example)."

    modeles = [os.getenv("DEEPSEEK_MODEL")] if os.getenv("DEEPSEEK_MODEL") else MODELES_PAR_DEFAUT
    image_base64 = encoder_image(image)
    derniere_erreur = ""
    for modele in modeles:
        payload = {
            "model": modele,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": _consigne()},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                ],
            }],
            "temperature": 0.2,
        }
        try:
            reponse = requests.post(
                URL_API,
                headers={"Authorization": f"Bearer {cle_api}"},
                json=payload,
                timeout=60,
            )
        except requests.RequestException as e:
            return None, f"Impossible de joindre DeepSeek : {e}"

        if reponse.status_code in (400, 404, 422):
            derniere_erreur = f"modèle « {modele} » refusé ({reponse.status_code}) : {reponse.text[:200]}"
            continue
        if reponse.status_code == 401:
            return None, "Clé DeepSeek invalide (erreur 401). Vérifie DEEPSEEK_API_KEY dans le fichier .env."
        if reponse.status_code == 402:
            return None, "Solde DeepSeek insuffisant (erreur 402). Recharge ton compte DeepSeek."
        if not reponse.ok:
            return None, f"Erreur DeepSeek {reponse.status_code} : {reponse.text[:200]}"

        try:
            contenu = reponse.json()["choices"][0]["message"]["content"]
            return _extraire_json(contenu), None
        except (KeyError, IndexError, ValueError) as e:
            return None, f"Réponse de DeepSeek illisible ({e})."

    return None, (
        "Aucun modèle DeepSeek n'a accepté la photo. Mets le bon nom de modèle vision dans .env "
        f"(DEEPSEEK_MODEL=...). Détail : {derniere_erreur}"
    )
