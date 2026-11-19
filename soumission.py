from datetime import date, timedelta
from pathlib import Path

from fpdf import FPDF

from donnees import TPS, TVQ

SOUMISSIONS_DIR = Path("soumissions")


def montants(prix, reglages):
    if not reglages.get("facturer_taxes"):
        return {"sous_total": prix, "tps": 0.0, "tvq": 0.0, "total": prix}
    tps, tvq = round(prix * TPS, 2), round(prix * TVQ, 2)
    return {"sous_total": prix, "tps": tps, "tvq": tvq, "total": round(prix + tps + tvq, 2)}


def _txt(s):
    # Les polices intégrées de FPDF ne gèrent que le latin-1.
    remplacements = {"—": "-", "–": "-", "’": "'", "“": '"', "”": '"', "…": "...", "œ": "oe"}
    s = str(s)
    for a, b in remplacements.items():
        s = s.replace(a, b)
    return s.encode("latin-1", "replace").decode("latin-1")


def _argent(x):
    return f"{x:,.2f} $".replace(",", " ").replace(".", ",")


def description_travaux(job):
    if job["type_job"] == "cèdre solo / petit arbre":
        return f"Taille d'un cèdre isolé / petit arbre d'environ {job['hauteur_pieds']:g} pi de haut"
    cotes = "des deux côtés" if job.get("deux_cotes") else "d'un côté"
    return (
        f"{job['type_job'].capitalize()} de haie : {job['longueur_pieds']:g} pi linéaires, "
        f"environ {job['hauteur_pieds']:g} pi de haut, {cotes} (densité {job['densite']}, accès {job['acces']})"
    )


def generer_pdf(job, reglages):
    SOUMISSIONS_DIR.mkdir(exist_ok=True)
    m = montants(job["prix_estime"], reglages)
    aujourd_hui = date.today()

    pdf = FPDF(format="Letter")
    pdf.set_margins(20, 20, 20)
    pdf.add_page()
    w = pdf.epw

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(w, 10, _txt(reglages.get("entreprise_nom") or "Soumission - Taille de haie"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for ligne in (reglages.get("entreprise_adresse"), reglages.get("entreprise_telephone"), reglages.get("entreprise_courriel")):
        if ligne:
            pdf.cell(w, 5, _txt(ligne), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(w, 8, _txt(f"SOUMISSION no {job['id']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(w, 5, _txt(f"Date : {aujourd_hui:%Y-%m-%d}"), new_x="LMARGIN", new_y="NEXT")
    validite = int(reglages.get("validite_jours") or 30)
    pdf.cell(w, 5, _txt(f"Valide jusqu'au : {aujourd_hui + timedelta(days=validite):%Y-%m-%d}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    if job.get("client") or job.get("adresse"):
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(w, 6, "Client", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        for ligne in (job.get("client"), job.get("adresse"), job.get("telephone_client")):
            if ligne:
                pdf.cell(w, 5, _txt(ligne), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_fill_color(230, 240, 230)
    pdf.cell(w * 0.75, 8, "Description des travaux", border=1, fill=True)
    pdf.cell(w * 0.25, 8, "Montant", border=1, fill=True, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    x, y = pdf.get_x(), pdf.get_y()
    pdf.multi_cell(w * 0.75, 6, _txt(description_travaux(job) + ". Ramassage et nettoyage des résidus inclus."), border=1)
    h = pdf.get_y() - y
    pdf.set_xy(x + w * 0.75, y)
    pdf.cell(w * 0.25, h, _txt(_argent(m["sous_total"])), border=1, align="R", new_x="LMARGIN", new_y="NEXT")

    lignes = [("Sous-total", m["sous_total"])]
    if reglages.get("facturer_taxes"):
        lignes += [("TPS (5 %)", m["tps"]), ("TVQ (9,975 %)", m["tvq"])]
    lignes.append(("TOTAL", m["total"]))
    for libelle, val in lignes:
        pdf.set_font("Helvetica", "B" if libelle == "TOTAL" else "", 11 if libelle == "TOTAL" else 10)
        pdf.cell(w * 0.75, 7, _txt(libelle), align="R")
        pdf.cell(w * 0.25, 7, _txt(_argent(val)), align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)
    pdf.set_font("Helvetica", "", 9)
    if reglages.get("facturer_taxes") and (reglages.get("numero_tps") or reglages.get("numero_tvq")):
        pdf.cell(w, 5, _txt(f"No TPS : {reglages.get('numero_tps', '')}    No TVQ : {reglages.get('numero_tvq', '')}"), new_x="LMARGIN", new_y="NEXT")
    if job.get("note"):
        pdf.multi_cell(w, 5, _txt(f"Note : {job['note']}"))
    pdf.ln(10)
    pdf.cell(w / 2, 5, "Signature du client : ____________________")
    pdf.cell(w / 2, 5, "Date : ______________", new_x="LMARGIN", new_y="NEXT")

    nom_client = "".join(c for c in (job.get("client") or "") if c.isalnum() or c in " -_").strip().replace(" ", "_")
    chemin = SOUMISSIONS_DIR / f"soumission_{job['id']}{'_' + nom_client if nom_client else ''}.pdf"
    pdf.output(str(chemin))
    return chemin
