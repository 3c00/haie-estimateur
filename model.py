import math
from dataclasses import dataclass, field

TYPES_JOB = ["taille normale", "nivelage", "restoration", "cèdre solo / petit arbre"]
DENSITES = ["légère", "moyenne", "dense"]
ACCES = ["facile", "moyen", "difficile"]
TYPE_SOLO = "cèdre solo / petit arbre"

# Poids "a priori" de la grille : il faut environ K vrais jobs pour que l'ajustement compte à moitié.
K_LISSAGE = 3
ECART_DEFAUT = 0.15


@dataclass
class Estimation:
    prix: float | None
    prix_grille: float | None
    prix_min: float | None = None
    prix_max: float | None = None
    temps: float = 0.0
    equipement: list = field(default_factory=list)
    details: list = field(default_factory=list)
    facteur: float = 1.0
    nb_jobs_reels: int = 0


def taux_taille_normale(hauteur, r):
    if hauteur < 5:
        return r["taux_moins_5"]
    if hauteur <= 10:
        return r["taux_5_10"]
    if hauteur <= 12:
        return r["taux_10_12"]
    if hauteur <= 20:
        return r["taux_12_20"]
    return None


def prix_grille(job, r):
    """Prix selon la grille de l'entreprise, avec le détail du calcul."""
    t, L, H = job["type_job"], float(job["longueur_pieds"]), float(job["hauteur_pieds"])
    suppl = float(job.get("supplement_difficulte") or 0)
    details = []

    if t == TYPE_SOLO:
        prix = r["solo_base"] + H * r["solo_par_pied"]
        details.append(f"Cèdre solo : {r['solo_base']:.2f} $ + {H:g} pi × {r['solo_par_pied']:.2f} $")
        if job["acces"] == "difficile":
            prix *= r["mult_acces_difficile_solo"]
            details.append(f"Accès difficile : × {r['mult_acces_difficile_solo']:g}")
    else:
        taux = {
            "taille normale": taux_taille_normale(H, r),
            "nivelage": r["taux_nivelage"],
            "restoration": r["taux_restoration"],
        }[t]
        if taux is None:
            return None, ["Haie de plus de 20 pi : devis personnalisé"]
        prix = taux * L
        details.append(f"{L:g} pi × {taux:.2f} $/pi ({t}, {H:g} pi de haut)")
        if job["densite"] == "dense":
            prix *= r["mult_dense"]
            details.append(f"Haie dense : × {r['mult_dense']:g}")
        if job.get("deux_cotes"):
            prix *= r["mult_deux_cotes"]
            details.append(f"Deux côtés : × {r['mult_deux_cotes']:g}")

    if suppl:
        prix += suppl
        details.append(f"Supplément difficulté : + {suppl:g} $")
    return prix, details


def temps_grille(job):
    if job["type_job"] == TYPE_SOLO:
        return 0.5
    L, H = float(job["longueur_pieds"]), float(job["hauteur_pieds"])
    dens = {"légère": 1.0, "moyenne": 1.3, "dense": 1.8}.get(job["densite"], 1.0)
    acc = {"facile": 1.0, "moyen": 1.2, "difficile": 1.5}.get(job["acces"], 1.0)
    cotes = 1.5 if job.get("deux_cotes") else 1.0
    return (L / 15) * (H / 6) * dens * acc * cotes


def recommander_equipement(job):
    t, H = job["type_job"], float(job["hauteur_pieds"])
    eq = ["Sécateur", "Gants de protection"]
    if t in ("nivelage", "restoration") or job["densite"] == "dense":
        eq.append("Taille-haie")
    if H > 10:
        eq.append("Perche télescopique / escabeau")
    if H > 15:
        eq.append("Nacelle")
    if job["acces"] == "difficile":
        eq.append("Harnais de sécurité")
    if t == "nivelage":
        eq.append("Scie à chaîne")
    return eq


def _moyenne_log_lissee(logs, a_priori=0.0, k=K_LISSAGE):
    n = len(logs)
    return (sum(logs) + k * a_priori) / (n + k)


class Calibration:
    """Ajuste la grille avec les vrais prix payés : facteur global, puis facteur par type de job."""

    def __init__(self, jobs_reels, reglages):
        self.r = reglages
        self.logs_par_type = {}
        logs = []
        for j in jobs_reels:
            g, _ = prix_grille(j, reglages)
            if g and g > 0 and j.get("prix_reel"):
                lr = math.log(float(j["prix_reel"]) / g)
                logs.append(lr)
                self.logs_par_type.setdefault(j["type_job"], []).append(lr)
        self.n = len(logs)
        self.log_global = _moyenne_log_lissee(logs) if logs else 0.0

        residus = [
            lr - self.log_type(t) for t, lrs in self.logs_par_type.items() for lr in lrs
        ]
        if len(residus) >= 3:
            ecart = math.sqrt(sum(x * x for x in residus) / (len(residus) - 1))
            self.ecart = min(max(ecart, 0.05), 0.5)
        else:
            self.ecart = ECART_DEFAUT

        ratios_temps = [
            math.log(float(j["temps_reel"]) / temps_grille(j))
            for j in jobs_reels
            if j.get("temps_reel") and temps_grille(j) > 0
        ]
        self.n_temps = len(ratios_temps)
        self.facteur_temps = math.exp(_moyenne_log_lissee(ratios_temps)) if ratios_temps else 1.0

    def log_type(self, type_job):
        return _moyenne_log_lissee(self.logs_par_type.get(type_job, []), a_priori=self.log_global)

    def facteur(self, type_job):
        return math.exp(self.log_type(type_job))


def arrondir(prix, pas):
    return round(prix / pas) * pas if pas and pas > 0 else round(prix, 2)


def estimer(job, jobs_reels, reglages):
    g, details = prix_grille(job, reglages)
    cal = Calibration(jobs_reels, reglages)
    temps = temps_grille(job) * cal.facteur_temps
    eq = recommander_equipement(job)
    if g is None:
        return Estimation(None, None, temps=temps, equipement=eq, details=details, nb_jobs_reels=cal.n)

    f = cal.facteur(job["type_job"])
    prix = g * f
    if abs(f - 1) >= 0.005:
        quoi = "ton vrai prix" if cal.n == 1 else f"tes {cal.n} vrais prix"
        details.append(f"Ajustement selon {quoi} : × {f:.3f}")
    minimum = float(reglages.get("prix_minimum") or 0)
    if prix < minimum:
        prix = minimum
        details.append(f"Prix minimum appliqué : {minimum:g} $")

    pas = reglages.get("arrondi", 5)
    return Estimation(
        prix=arrondir(prix, pas),
        prix_grille=round(g, 2),
        prix_min=arrondir(max(prix * math.exp(-cal.ecart), minimum), pas),
        prix_max=arrondir(prix * math.exp(cal.ecart), pas),
        temps=round(temps, 1),
        equipement=eq,
        details=details,
        facteur=f,
        nb_jobs_reels=cal.n,
    )


def evaluer(jobs_reels, reglages):
    """Validation « un job retiré à la fois » : erreur moyenne de la grille seule vs grille ajustée."""
    utilisables = [j for j in jobs_reels if prix_grille(j, reglages)[0]]
    if len(utilisables) < 3:
        return None
    err_grille, err_ajuste = [], []
    for i, j in enumerate(utilisables):
        autres = utilisables[:i] + utilisables[i + 1:]
        g, _ = prix_grille(j, reglages)
        f = Calibration(autres, reglages).facteur(j["type_job"])
        reel = float(j["prix_reel"])
        err_grille.append(abs(g - reel))
        err_ajuste.append(abs(g * f - reel))
    n = len(utilisables)
    return {"n": n, "erreur_grille": sum(err_grille) / n, "erreur_ajustee": sum(err_ajuste) / n}
