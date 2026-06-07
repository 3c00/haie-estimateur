import csv
import json
import os
from datetime import datetime
from io import StringIO
from pathlib import Path

import gradio as gr
import numpy as np
import pandas as pd
from PIL import Image

import api_client
from model import (
    TYPES_JOB,
    DENSITES,
    ACCES,
    ajouter_correction,
    charger_donnees,
    entrainer_modele,
    estimer_prix,
)

HISTORIQUE_FILE = Path("historique.json")
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)


def charger_historique():
    if HISTORIQUE_FILE.exists():
        with open(HISTORIQUE_FILE, "r") as f:
            return json.load(f)
    return []


def sauvegarder_historique(historique):
    with open(HISTORIQUE_FILE, "w") as f:
        json.dump(historique, f, indent=2, ensure_ascii=False)


def analyser_photo(image):
    if image is None:
        return {k: None for k in ["type_job", "hauteur_pieds", "longueur_pieds", "densite", "acces"]}

    resultat = api_client.analyser_photo(image)
    if resultat is None:
        return {k: None for k in ["type_job", "hauteur_pieds", "longueur_pieds", "densite", "acces"]}

    type_job = resultat.get("type_job", "").lower()
    type_valide = type_job if type_job in TYPES_JOB else None

    densite = resultat.get("densite", "").lower()
    densite_valide = densite if densite in DENSITES else None

    acces = resultat.get("acces", "").lower()
    acces_valide = acces if acces in ACCES else None

    return {
        "type_job": type_valide,
        "hauteur_pieds": resultat.get("hauteur_pieds"),
        "longueur_pieds": resultat.get("longueur_pieds"),
        "densite": densite_valide,
        "acces": acces_valide,
    }


def estimer(type_job, longueur_pieds, hauteur_pieds, densite, acces, deux_cotes, supplement_difficulte, image):
    erreurs = []
    if not type_job:
        erreurs.append("Sélectionne un type de job")
    if not longueur_pieds or longueur_pieds <= 0:
        erreurs.append("Entre une longueur valide (en pieds linéaires)")
    if not hauteur_pieds or hauteur_pieds <= 0:
        erreurs.append("Entre une hauteur valide (en pieds)")
    if not densite:
        erreurs.append("Sélectionne une densité")
    if not acces:
        erreurs.append("Sélectionne un niveau d'accès")
    if erreurs:
        return "\n".join(erreurs), "", "", gr.update(visible=False)

    prix, temps, equipement = estimer_prix(type_job, longueur_pieds, hauteur_pieds, densite, acces, deux_cotes, supplement_difficulte)

    historique = charger_historique()
    entree = {
        "date": datetime.now().isoformat(),
        "type_job": type_job,
        "longueur_pieds": longueur_pieds,
        "hauteur_pieds": hauteur_pieds,
        "densite": densite,
        "acces": acces,
        "deux_cotes": deux_cotes,
        "supplement_difficulte": supplement_difficulte,
        "prix_estime": prix,
        "temps_estime": temps,
        "equipement": equipement,
        "prix_reel": None,
    }
    if image is not None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        chemin_photo = DATA_DIR / f"haie_{timestamp}.jpg"
        image.save(str(chemin_photo))
        entree["photo"] = str(chemin_photo)
    else:
        entree["photo"] = None

    historique.append(entree)
    sauvegarder_historique(historique)

    texte_equipement = ", ".join(equipement)

    details = f"Longueur : {longueur_pieds} pi linéaires  |  Hauteur : {hauteur_pieds} pi"
    if deux_cotes:
        details += "  |  ×1.5 (deux côtés)"
    if supplement_difficulte:
        details += f"  |  Suppl. difficulté : {supplement_difficulte}$"

    resultat = (
        f"--- RÉSULTAT DE L'ESTIMATION ---\n\n"
        f"{details}\n\n"
        f"**Prix suggéré : {prix:.2f} $ CAD**\n"
        f"Temps estimé : {temps:.1f} heures\n"
        f"Équipement recommandé : {texte_equipement}"
    )

    return resultat, "", "", gr.update(visible=True, value={
        "type_job": type_job,
        "longueur_pieds": longueur_pieds,
        "hauteur_pieds": hauteur_pieds,
        "densite": densite,
        "acces": acces,
        "deux_cotes": deux_cotes,
        "supplement_difficulte": supplement_difficulte,
        "prix_estime": prix,
    })


def corriger_estimation(type_job, longueur_pieds, hauteur_pieds, densite, acces, deux_cotes, supplement_difficulte, prix_estime, prix_reel):
    if not prix_reel or prix_reel <= 0:
        return "Entre un prix réel valide."

    ajouter_correction(type_job, longueur_pieds, hauteur_pieds, densite, acces, deux_cotes, supplement_difficulte, prix_estime, prix_reel)

    historique = charger_historique()
    if historique:
        historique[-1]["prix_reel"] = prix_reel
        sauvegarder_historique(historique)

    return "Correction enregistrée ! Utilise 'Réentraîner le modèle' pour améliorer les prédictions."


def reentrainer():
    modele, score = entrainer_modele()
    if modele is None:
        return "Pas assez de données pour entraîner le modèle (minimum 3 entrées)."
    return f"Modèle réentraîné ! Précision (R²) : {score:.3f}"


def obtenir_statistiques():
    historique = charger_historique()
    if not historique:
        return pd.DataFrame()

    df = pd.DataFrame(historique)
    stats = {}

    df_avec_reel = df[df["prix_reel"].notna()].copy()
    if not df_avec_reel.empty:
        df_avec_reel["erreur"] = abs(df_avec_reel["prix_estime"] - df_avec_reel["prix_reel"])
        stats["Erreur moyenne ($)"] = f"{df_avec_reel['erreur'].mean():.2f} $"
        stats["Erreur médiane ($)"] = f"{df_avec_reel['erreur'].median():.2f} $"

    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        stats["Nombre total de jobs"] = len(df)
        stats["Prix moyen estimé"] = f"{df['prix_estime'].mean():.2f} $"

        meilleur_mois = df.set_index("date").resample("ME")["prix_estime"].sum()
        if not meilleur_mois.empty:
            stats["Meilleur mois"] = meilleur_mois.idxmax().strftime("%B %Y")

        type_plus_rentable = df.groupby("type_job")["prix_estime"].sum()
        if not type_plus_rentable.empty:
            stats["Type le plus rentable"] = type_plus_rentable.idxmax()

    return pd.DataFrame([stats]).T.rename(columns={0: "Valeur"})


def exporter_csv():
    historique = charger_historique()
    if not historique:
        return None

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=historique[0].keys())
    writer.writeheader()
    writer.writerows(historique)
    buffer.seek(0)
    return buffer.getvalue()


def mettre_jour_historique():
    historique = charger_historique()
    if not historique:
        return pd.DataFrame()

    df = pd.DataFrame(historique)
    colonnes = ["date", "type_job", "longueur_pieds", "hauteur_pieds", "densite", "acces", "deux_cotes", "supplement_difficulte", "prix_estime", "prix_reel"]
    colonnes_presentes = [c for c in colonnes if c in df.columns]
    return df[colonnes_presentes]


with gr.Blocks(title="Haie Estimateur") as app:
    gr.Markdown("# Haie Estimateur")
    gr.Markdown("Estime le prix des jobs de taille de haie. Prix en $ CAD, dimensions en pieds.")

    estimation_courante = gr.State()

    with gr.Tab("Estimation"):
        with gr.Row():
            with gr.Column(scale=1):
                image_input = gr.Image(label="Photo de la haie", type="pil")
                btn_analyser = gr.Button("Analyser la photo (DeepSeek AI)")
                gr.Markdown("---")
                type_job = gr.Dropdown(choices=TYPES_JOB, label="Type de job")
                longueur_pieds = gr.Number(label="Longueur (pieds linéaires)", minimum=0)
                hauteur_pieds = gr.Number(label="Hauteur (pieds)", minimum=0)
                densite = gr.Radio(choices=DENSITES, label="Densité")
                acces = gr.Radio(choices=ACCES, label="Accès")
                deux_cotes = gr.Checkbox(label="Des deux côtés (×1.5)")
                supplement_difficulte = gr.Dropdown(choices=[0, 25, 50], label="Suppl. difficulté ($)", value=0)

            with gr.Column(scale=1):
                image_output = gr.Image(label="Aperçu")
                btn_estimer = gr.Button("Estimer le prix", variant="primary")
                resultat_texte = gr.Textbox(label="Résultat", lines=12)

        with gr.Row():
            btn_analyser.click(
                fn=analyser_photo,
                inputs=[image_input],
                outputs=[type_job, hauteur_pieds, longueur_pieds, densite, acces],
                queue=False,
            )

            image_input.change(
                fn=lambda img: img,
                inputs=[image_input],
                outputs=[image_output],
            )

    with gr.Tab("Correction"):
        gr.Markdown("## Corriger l'estimation")
        gr.Markdown("Entre le prix réel payé après le job pour améliorer le modèle.")
        with gr.Row():
            with gr.Column():
                correction_type = gr.Dropdown(choices=TYPES_JOB, label="Type de job", interactive=False)
                correction_longueur = gr.Number(label="Longueur (pi)", interactive=False)
                correction_hauteur = gr.Number(label="Hauteur (pi)", interactive=False)
                correction_densite = gr.Radio(choices=DENSITES, label="Densité", interactive=False)
                correction_acces = gr.Radio(choices=ACCES, label="Accès", interactive=False)
                correction_deux_cotes = gr.Checkbox(label="Deux côtés", interactive=False)
                correction_supplement = gr.Number(label="Suppl. difficulté ($)", interactive=False)
                correction_prix_estime = gr.Number(label="Prix estimé ($)", interactive=False)
            with gr.Column():
                correction_prix_reel = gr.Number(label="Prix réel ($ CAD)", minimum=0)
                btn_corriger = gr.Button("Enregistrer la correction", variant="secondary")
                message_correction = gr.Textbox(label="Statut")

        btn_corriger.click(
            fn=corriger_estimation,
            inputs=[
                correction_type, correction_longueur, correction_hauteur,
                correction_densite, correction_acces,
                correction_deux_cotes, correction_supplement,
                correction_prix_estime, correction_prix_reel,
            ],
            outputs=[message_correction],
        )

    with gr.Tab("Entraînement"):
        gr.Markdown("## Réentraîner le modèle")
        gr.Markdown(
            "Utilise toutes les corrections enregistrées pour améliorer les prédictions."
        )
        btn_reentrainer = gr.Button("Réentraîner le modèle", variant="primary")
        resultat_entrainement = gr.Textbox(label="Résultat")
        btn_reentrainer.click(fn=reentrainer, inputs=[], outputs=[resultat_entrainement])

    with gr.Tab("Historique"):
        gr.Markdown("## Historique des estimations")
        btn_rafraichir = gr.Button("Rafraîchir")
        tableau_historique = gr.DataFrame(label="Jobs")

        btn_exporter = gr.DownloadButton("Exporter en CSV")
        csv_data = gr.State()

        btn_rafraichir.click(
            fn=mettre_jour_historique,
            inputs=[],
            outputs=[tableau_historique],
        )
        btn_exporter.click(
            fn=exporter_csv,
            inputs=[],
            outputs=[csv_data],
        )

    with gr.Tab("Statistiques"):
        gr.Markdown("## Statistiques")
        btn_stats = gr.Button("Calculer les statistiques")
        tableau_stats = gr.DataFrame(label="Statistiques")
        btn_stats.click(fn=obtenir_statistiques, inputs=[], outputs=[tableau_stats])

    btn_estimer.click(
        fn=estimer,
        inputs=[type_job, longueur_pieds, hauteur_pieds, densite, acces, deux_cotes, supplement_difficulte, image_input],
        outputs=[resultat_texte, gr.Textbox(visible=False), gr.Textbox(visible=False), estimation_courante],
    )

    def afficher_correction(estimation):
        if estimation is None:
            return tuple([None] * 9)
        return (
            estimation.get("type_job"),
            estimation.get("longueur_pieds"),
            estimation.get("hauteur_pieds"),
            estimation.get("densite"),
            estimation.get("acces"),
            estimation.get("deux_cotes", False),
            estimation.get("supplement_difficulte", 0),
            estimation.get("prix_estime"),
        )

    estimation_courante.change(
        fn=afficher_correction,
        inputs=[estimation_courante],
        outputs=[correction_type, correction_longueur, correction_hauteur, correction_densite, correction_acces, correction_deux_cotes, correction_supplement, correction_prix_estime],
    )

if __name__ == "__main__":
    modele, score = entrainer_modele()
    print(f"Modèle pré-entraîné avec {len(charger_donnees())} entrées (R² = {score:.3f})")
    app.launch(inbrowser=False, server_name="0.0.0.0", share=True, theme=gr.themes.Soft())
