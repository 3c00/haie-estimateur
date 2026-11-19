from datetime import datetime

import gradio as gr
import pandas as pd

import api_client
import donnees as db
from model import ACCES, DENSITES, TYPE_SOLO, TYPES_JOB, Calibration, estimer, evaluer
from soumission import generer_pdf, montants

STATUTS = ["soumis", "accepté", "terminé", "refusé"]
CHAMPS_REGLAGES = [
    ("taux_moins_5", "Taille normale, moins de 5 pi ($/pi)"),
    ("taux_5_10", "Taille normale, 5 à 10 pi ($/pi)"),
    ("taux_10_12", "Taille normale, 10 à 12 pi ($/pi)"),
    ("taux_12_20", "Taille normale, 12 à 20 pi ($/pi)"),
    ("taux_nivelage", "Nivelage ($/pi)"),
    ("taux_restoration", "Restoration ($/pi)"),
    ("solo_base", "Cèdre solo : prix de base ($)"),
    ("solo_par_pied", "Cèdre solo : par pied de hauteur ($)"),
    ("mult_acces_difficile_solo", "Cèdre solo : multiplicateur accès difficile"),
    ("mult_dense", "Multiplicateur haie dense"),
    ("mult_deux_cotes", "Multiplicateur deux côtés"),
    ("prix_minimum", "Prix minimum par job ($)"),
    ("arrondi", "Arrondir le prix au multiple de ($)"),
    ("validite_jours", "Validité des soumissions (jours)"),
]
CHAMPS_ENTREPRISE = [
    ("entreprise_nom", "Nom de l'entreprise"),
    ("entreprise_telephone", "Téléphone"),
    ("entreprise_courriel", "Courriel"),
    ("entreprise_adresse", "Adresse"),
    ("numero_tps", "No TPS"),
    ("numero_tvq", "No TVQ"),
]


def argent(x):
    return f"{x:,.2f} $".replace(",", " ").replace(".", ",")


def pluriel(n, mot, mot_pluriel=None):
    return f"{n} {mot if n <= 1 else (mot_pluriel or mot + 's')}"


def graphique(df):
    haut = float(df["montant"].max()) * 1.15 if len(df) else 1
    return gr.update(value=df, y_lim=[0, haut])


# ---------- Estimation ----------

def analyser_photo(image):
    vide = [gr.update()] * 5
    if image is None:
        return *vide, "Ajoute d'abord une photo."
    res, erreur = api_client.analyser_photo(image)
    if erreur:
        return *vide, f"⚠️ {erreur}"

    def nombre(v):
        try:
            return round(float(v), 1)
        except (TypeError, ValueError):
            return None

    def choix(v, options):
        v = str(v or "").strip().lower()
        return v if v in options else None

    valeurs = [
        choix(res.get("type_job"), TYPES_JOB),
        nombre(res.get("longueur_pieds")),
        nombre(res.get("hauteur_pieds")),
        choix(res.get("densite"), DENSITES),
        choix(res.get("acces"), ACCES),
    ]
    updates = [gr.update(value=v) if v is not None else gr.update() for v in valeurs]
    msg = "✅ Photo analysée. **Vérifie les valeurs**, surtout la longueur : une photo voit rarement toute la haie."
    if res.get("commentaire"):
        msg += f"\n\n> {res['commentaire']}"
    return *updates, msg


def lire_job_formulaire(type_job, longueur, hauteur, densite, acces, deux_cotes, suppl):
    erreurs = []
    if not type_job:
        erreurs.append("le type de job")
    if type_job != TYPE_SOLO and (not longueur or longueur <= 0):
        erreurs.append("une longueur valide")
    if not hauteur or hauteur <= 0:
        erreurs.append("une hauteur valide")
    if not densite:
        erreurs.append("la densité")
    if not acces:
        erreurs.append("l'accès")
    if erreurs:
        return None, "Il manque : " + ", ".join(erreurs) + "."
    return {
        "type_job": type_job,
        "longueur_pieds": float(longueur or 1),
        "hauteur_pieds": float(hauteur),
        "densite": densite,
        "acces": acces,
        "deux_cotes": bool(deux_cotes),
        "supplement_difficulte": float(suppl or 0),
    }, None


def texte_estimation(e, reglages):
    if e.prix is None:
        return "### Devis personnalisé\n" + "\n".join(f"- {d}" for d in e.details)
    m = montants(e.prix, reglages)
    lignes = [f"## Prix suggéré : {argent(e.prix)}"]
    if e.prix_min != e.prix_max:
        lignes.append(f"Fourchette réaliste : **{argent(e.prix_min)} à {argent(e.prix_max)}**")
    if reglages.get("facturer_taxes"):
        lignes.append(f"Avec taxes (TPS + TVQ) : **{argent(m['total'])}**")
    lignes.append("")
    lignes.append(f"- Temps estimé : **{e.temps:.1f} h**".replace(".", ","))
    if e.temps > 0:
        lignes.append(f"- Taux horaire effectif : **{argent(e.prix / e.temps)}/h**")
    lignes.append(f"- Équipement : {', '.join(e.equipement)}")
    lignes.append("\n**Détail du calcul**")
    lignes += [f"- {d}" for d in e.details]
    if e.nb_jobs_reels == 0:
        lignes.append(
            "\n_Prix basé uniquement sur ta grille. Entre le vrai prix de tes jobs dans « Suivi des jobs » "
            "et l'estimation s'ajustera toute seule._"
        )
    return "\n".join(lignes)


def faire_estimation(image, client, adresse, tel, note, type_job, longueur, hauteur, densite, acces, deux_cotes, suppl):
    job, erreur = lire_job_formulaire(type_job, longueur, hauteur, densite, acces, deux_cotes, suppl)
    if erreur:
        return f"⚠️ {erreur}", None, gr.update(visible=False), None
    reglages = db.charger_reglages()
    e = estimer(job, db.jobs_reels(), reglages)

    job.update({
        "date": datetime.now().isoformat(timespec="seconds"),
        "client": (client or "").strip(),
        "adresse": (adresse or "").strip(),
        "telephone_client": (tel or "").strip(),
        "note": (note or "").strip(),
        "prix_estime": e.prix,
        "prix_grille": e.prix_grille,
        "temps_estime": e.temps,
        "equipement": e.equipement,
        "prix_reel": None,
        "temps_reel": None,
        "statut": "soumis",
        "photo": None,
    })
    job = db.ajouter_job(job)
    if image is not None:
        db.DATA_DIR.mkdir(exist_ok=True)
        chemin = db.DATA_DIR / f"haie_{job['id']}_{datetime.now():%Y%m%d_%H%M%S}.jpg"
        image.convert("RGB").save(chemin, quality=90)
        db.modifier_job(job["id"], photo=str(chemin))

    texte = texte_estimation(e, reglages) + f"\n\n_Enregistré comme job no {job['id']}._"
    return texte, job["id"], gr.update(visible=e.prix is not None), None


def creer_soumission(job_id):
    job = db.trouver_job(job_id) if job_id else None
    if not job or job.get("prix_estime") is None:
        return None
    return str(generer_pdf(job, db.charger_reglages()))


# ---------- Suivi ----------

def tableau_jobs():
    jobs = db.charger_jobs()
    if not jobs:
        return pd.DataFrame(columns=["No", "Date", "Client", "Type", "Long. (pi)", "Haut. (pi)", "Estimé ($)", "Réel ($)", "Statut"])
    lignes = [{
        "No": j["id"],
        "Date": str(j.get("date", ""))[:10],
        "Client": j.get("client", ""),
        "Type": j.get("type_job") or j.get("type_haie", ""),
        "Long. (pi)": j.get("longueur_pieds"),
        "Haut. (pi)": j.get("hauteur_pieds"),
        "Estimé ($)": j.get("prix_estime"),
        "Réel ($)": j.get("prix_reel"),
        "Statut": j.get("statut", ""),
    } for j in reversed(jobs)]
    return pd.DataFrame(lignes)


def choix_jobs():
    return [
        (f"No {j['id']} · {str(j.get('date', ''))[:10]} · {j.get('client') or 'sans nom'} · "
         f"{j.get('type_job') or j.get('type_haie', '?')} · {j.get('prix_estime') or 0:g} $", j["id"])
        for j in reversed(db.charger_jobs())
    ]


def rafraichir_suivi(selection=None):
    choix = choix_jobs()
    ids = [v for _, v in choix]
    return tableau_jobs(), gr.update(choices=choix, value=selection if selection in ids else None)


def charger_selection(job_id):
    j = db.trouver_job(job_id) if job_id else None
    if not j:
        return None, None, None, "", None
    photo = j.get("photo")
    return j.get("prix_reel"), j.get("temps_reel"), j.get("statut") or "soumis", j.get("note", ""), photo


def enregistrer_suivi(job_id, prix_reel, temps_reel, statut, note):
    if not job_id:
        return "Choisis d'abord un job.", *rafraichir_suivi()
    if prix_reel is not None and prix_reel < 0:
        return "Le prix réel ne peut pas être négatif.", *rafraichir_suivi(job_id)
    champs = {
        "prix_reel": prix_reel or None,
        "temps_reel": temps_reel or None,
        "statut": statut,
        "note": (note or "").strip(),
    }
    if prix_reel and statut in ("soumis", "accepté"):
        champs["statut"] = "terminé"
    db.modifier_job(job_id, **champs)
    msg = f"✅ Job no {job_id} enregistré."
    if prix_reel:
        n = len(db.jobs_reels())
        msg += f" Les prochaines estimations tiennent compte de {pluriel(n, 'vrai prix', 'vrais prix')}."
    return msg, *rafraichir_suivi(job_id)


def supprimer(job_id):
    if not job_id:
        return "Choisis d'abord un job.", *rafraichir_suivi()
    db.supprimer_job(job_id)
    return f"🗑️ Job no {job_id} supprimé.", *rafraichir_suivi()


def exporter_csv():
    jobs = db.charger_jobs()
    if not jobs:
        return None
    chemin = db.DATA_DIR / f"historique_{datetime.now():%Y%m%d}.csv"
    db.DATA_DIR.mkdir(exist_ok=True)
    df = pd.DataFrame(jobs)
    if "equipement" in df:
        df["equipement"] = df["equipement"].apply(lambda e: ", ".join(e) if isinstance(e, list) else e)
    # utf-8-sig : Excel sur Windows affiche alors correctement les accents.
    df.to_csv(chemin, index=False, encoding="utf-8-sig", sep=";", decimal=",")
    return str(chemin)


# ---------- Statistiques ----------

def statistiques():
    jobs = [j for j in db.charger_jobs() if not j.get("ancien_format")]
    reglages = db.charger_reglages()
    vide = pd.DataFrame({"mois": [], "montant": []})
    if not jobs:
        return "Aucun job pour l'instant.", vide, pd.DataFrame({"type": [], "montant": []})

    df = pd.DataFrame(jobs)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["montant"] = df["prix_reel"].fillna(df["prix_estime"]).fillna(0)
    faits = df[df["prix_reel"].notna()]
    decides = df[df["statut"].isin(["accepté", "terminé", "refusé"])]
    gagnes = df[df["statut"].isin(["accepté", "terminé"])]

    lignes = [
        f"- **Soumissions faites :** {len(df)}",
        f"- **Jobs terminés (prix réel connu) :** {len(faits)} — revenus {argent(faits['prix_reel'].sum())}",
    ]
    if len(decides):
        lignes.append(f"- **Taux d'acceptation :** {len(gagnes) / len(decides):.0%} ({len(gagnes)} sur {pluriel(len(decides), 'réponse')})")
    if len(faits):
        lignes.append(f"- **Prix moyen d'un job :** {argent(faits['prix_reel'].mean())}")
        avec_temps = faits[faits["temps_reel"].notna() & (faits["temps_reel"] > 0)]
        if len(avec_temps):
            taux = avec_temps["prix_reel"].sum() / avec_temps["temps_reel"].sum()
            lignes.append(f"- **Taux horaire réel moyen :** {argent(taux)}/h")

    reels = db.jobs_reels()
    ev = evaluer(reels, reglages)
    cal = Calibration(reels, reglages)
    lignes.append("\n**Précision des estimations**")
    if ev:
        lignes.append(
            f"- Testé sur tes {ev['n']} vrais prix (chaque job estimé sans le connaître) : "
            f"erreur moyenne **{argent(ev['erreur_ajustee'])}** avec ajustement, "
            f"contre {argent(ev['erreur_grille'])} avec la grille seule."
        )
    else:
        lignes.append("- Il faut au moins 3 jobs avec un prix réel pour mesurer la précision.")
    for t in TYPES_JOB:
        n_t = len(cal.logs_par_type.get(t, []))
        if n_t:
            f = cal.facteur(t)
            sens = "plus cher" if f > 1 else "moins cher"
            lignes.append(f"- {t} : tu factures en pratique {abs(f - 1):.0%} {sens} que ta grille ({pluriel(n_t, 'job')})")
    if cal.n_temps:
        lignes.append(f"- Temps : les estimations de durée sont corrigées × {cal.facteur_temps:.2f} ({pluriel(cal.n_temps, 'job chronométré', 'jobs chronométrés')})")

    par_mois = (
        df.dropna(subset=["date"]).groupby(df["date"].dt.strftime("%Y-%m"))["montant"].sum()
        .reset_index().rename(columns={"date": "mois"})
    )
    par_type = df.groupby("type_job")["montant"].sum().reset_index().rename(columns={"type_job": "type"})
    return "\n".join(lignes), graphique(par_mois), graphique(par_type)


# ---------- Réglages ----------

def sauver_reglages(taxes, *valeurs):
    cles = [c for c, _ in CHAMPS_REGLAGES] + [c for c, _ in CHAMPS_ENTREPRISE]
    reglages = db.charger_reglages()
    for cle, v in zip(cles, valeurs):
        if cle in dict(CHAMPS_REGLAGES):
            if v is None or v < 0:
                return f"⚠️ Valeur invalide pour « {dict(CHAMPS_REGLAGES)[cle]} »."
            reglages[cle] = float(v)
        else:
            reglages[cle] = (v or "").strip()
    reglages["facturer_taxes"] = bool(taxes)
    db.sauvegarder_reglages(reglages)
    return "✅ Réglages enregistrés. Ils s'appliquent aux prochaines estimations."


# ---------- Interface ----------

with gr.Blocks(title="Haie Estimateur") as app:
    gr.Markdown("# 🌲 Haie Estimateur\nEstime, soumissionne et suis tes jobs de taille de haie. Prix en $ CAD, dimensions en pieds.")
    job_courant = gr.State()
    r0 = db.charger_reglages()

    with gr.Tab("Estimation"):
        with gr.Row():
            with gr.Column(scale=1):
                image_input = gr.Image(label="Photo de la haie (optionnel)", type="pil", height=260)
                btn_analyser = gr.Button("📷 Remplir à partir de la photo (DeepSeek)")
                statut_photo = gr.Markdown()
                type_job = gr.Dropdown(choices=TYPES_JOB, label="Type de job", value="taille normale")
                with gr.Row():
                    longueur = gr.Number(label="Longueur (pieds linéaires)", minimum=0)
                    hauteur = gr.Number(label="Hauteur (pieds)", minimum=0)
                densite = gr.Radio(choices=DENSITES, label="Densité", value="moyenne")
                acces = gr.Radio(choices=ACCES, label="Accès", value="facile")
                with gr.Row():
                    deux_cotes = gr.Checkbox(label="Des deux côtés")
                    suppl = gr.Dropdown(choices=[0, 25, 50, 75, 100], value=0, allow_custom_value=True, label="Supplément difficulté ($)")
                with gr.Accordion("Client (pour la soumission)", open=False):
                    client = gr.Textbox(label="Nom du client")
                    adresse = gr.Textbox(label="Adresse des travaux")
                    tel = gr.Textbox(label="Téléphone du client")
                    note = gr.Textbox(label="Note (apparaît sur la soumission)", lines=2)

            with gr.Column(scale=1):
                btn_estimer = gr.Button("💰 Estimer le prix", variant="primary", size="lg")
                resultat = gr.Markdown("Remplis le formulaire puis clique sur **Estimer le prix**.")
                btn_pdf = gr.Button("📄 Créer la soumission PDF", visible=False)
                fichier_pdf = gr.File(label="Soumission", interactive=False)

        btn_analyser.click(analyser_photo, [image_input], [type_job, longueur, hauteur, densite, acces, statut_photo])
        btn_estimer.click(
            faire_estimation,
            [image_input, client, adresse, tel, note, type_job, longueur, hauteur, densite, acces, deux_cotes, suppl],
            [resultat, job_courant, btn_pdf, fichier_pdf],
        )
        btn_pdf.click(creer_soumission, [job_courant], [fichier_pdf])

    with gr.Tab("Suivi des jobs") as onglet_suivi:
        gr.Markdown("Après un job, entre le **vrai prix** (et le temps si tu l'as) : les estimations s'ajustent automatiquement.")
        with gr.Row():
            with gr.Column(scale=1):
                selection = gr.Dropdown(label="Job", choices=[])
                with gr.Row():
                    prix_reel = gr.Number(label="Prix réel payé ($)", minimum=0)
                    temps_reel = gr.Number(label="Temps réel (heures)", minimum=0)
                statut = gr.Radio(choices=STATUTS, label="Statut", value="soumis")
                note_suivi = gr.Textbox(label="Note", lines=2)
                with gr.Row():
                    btn_sauver = gr.Button("Enregistrer", variant="primary")
                    btn_pdf_suivi = gr.Button("📄 Soumission PDF")
                    btn_suppr = gr.Button("Supprimer", variant="stop")
                msg_suivi = gr.Markdown()
                fichier_suivi = gr.File(label="Fichier", interactive=False)
            with gr.Column(scale=1):
                photo_suivi = gr.Image(label="Photo", interactive=False, height=240)
        tableau = gr.DataFrame(label="Tous les jobs", interactive=False, wrap=True)
        btn_csv = gr.Button("⬇️ Exporter en CSV (Excel)")

        onglet_suivi.select(rafraichir_suivi, [selection], [tableau, selection])
        selection.change(charger_selection, [selection], [prix_reel, temps_reel, statut, note_suivi, photo_suivi])
        btn_sauver.click(enregistrer_suivi, [selection, prix_reel, temps_reel, statut, note_suivi], [msg_suivi, tableau, selection])
        btn_suppr.click(supprimer, [selection], [msg_suivi, tableau, selection])
        btn_pdf_suivi.click(creer_soumission, [selection], [fichier_suivi])
        btn_csv.click(exporter_csv, [], [fichier_suivi])

    with gr.Tab("Statistiques") as onglet_stats:
        stats_texte = gr.Markdown()
        with gr.Row():
            graph_mois = gr.BarPlot(x="mois", y="montant", title="Montant par mois ($)", height=300)
            graph_type = gr.BarPlot(x="type", y="montant", title="Montant par type de job ($)", height=300)
        onglet_stats.select(statistiques, [], [stats_texte, graph_mois, graph_type])

    with gr.Tab("Réglages"):
        gr.Markdown("### Ta grille de prix\nC'est la base de toutes les estimations, ensuite ajustée selon tes vrais prix.")
        with gr.Row():
            entrees_reglages = [gr.Number(label=lib, value=r0[cle], minimum=0) for cle, lib in CHAMPS_REGLAGES[:7]]
        with gr.Row():
            entrees_reglages += [gr.Number(label=lib, value=r0[cle], minimum=0) for cle, lib in CHAMPS_REGLAGES[7:]]
        gr.Markdown("### Taxes et entreprise (apparaissent sur les soumissions)")
        taxes = gr.Checkbox(label="Je facture la TPS (5 %) et la TVQ (9,975 %)", value=r0["facturer_taxes"])
        with gr.Row():
            entrees_entreprise = [gr.Textbox(label=lib, value=r0[cle]) for cle, lib in CHAMPS_ENTREPRISE]
        btn_reglages = gr.Button("Enregistrer les réglages", variant="primary")
        msg_reglages = gr.Markdown()
        btn_reglages.click(sauver_reglages, [taxes, *entrees_reglages, *entrees_entreprise], [msg_reglages])


if __name__ == "__main__":
    app.launch(inbrowser=True, theme=gr.themes.Soft(primary_hue="green"))
