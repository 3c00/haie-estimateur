import base64
import json
import os
from io import BytesIO

import requests
from dotenv import load_dotenv
from PIL import Image

load_dotenv()


def encoder_image(image: Image.Image) -> str:
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def analyser_photo(image: Image.Image) -> dict | None:
    cle_api = os.getenv("DEEPSEEK_API_KEY")
    if not cle_api or cle_api == "sk-votre-cle-ici":
        return None

    image_base64 = encoder_image(image)

    payload = {
        "model": "deepseek-vision-pro",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Tu es un expert en taille de haie. Analyse cette photo "
                            "et estime : type d'arbuste, hauteur approximative en mètres, "
                            "longueur visible, densité du feuillage, difficulté d'accès. "
                            "Réponds en JSON uniquement avec les clés : "
                            "type_haie, hauteur_m, longueur_m, densite, acces."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                    },
                ],
            }
        ],
    }

    try:
        reponse = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {cle_api}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        reponse.raise_for_status()
        contenu = reponse.json()["choices"][0]["message"]["content"]
        contenu_propre = contenu.strip().removeprefix("```json").removesuffix("```").strip()
        return json.loads(contenu_propre)
    except Exception:
        return None
