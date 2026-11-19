# Haie Estimateur

Application pour estimer, soumissionner et suivre des jobs de taille de haie (prix en $ CAD, dimensions en pieds).

## Lancer l'application

1. Installe Python 3.11 ou plus récent (python.org). Sur Windows, coche **« Add Python to PATH »**.
2. Double-clique sur **`lancer.bat`** (Windows) ou **`lancer.command`** (Mac).

L'application s'ouvre dans ton navigateur. Laisse la fenêtre noire ouverte pendant que tu l'utilises.

## Fonctionnalités

- **Estimation** basée sur ta grille de prix, avec le détail du calcul, une fourchette réaliste, le temps estimé et le taux horaire effectif.
- **Ajustement automatique** : chaque fois que tu entres le vrai prix d'un job, les estimations suivantes se rapprochent de ce que tu factures vraiment (par type de job).
- **Soumission PDF** pour le client (nom, adresse, taxes TPS/TVQ si activées, ligne de signature).
- **Suivi des jobs** : statut (soumis, accepté, terminé, refusé), prix réel, temps réel, photo, export CSV pour Excel.
- **Statistiques** : revenus, taux d'acceptation, taux horaire réel, précision des estimations, graphiques.
- **Réglages** : ta grille de prix, prix minimum, arrondi, taxes et coordonnées de l'entreprise.
- **Photo (optionnel)** : remplit le formulaire avec DeepSeek. Mets ta clé dans un fichier `.env` (voir `.env.example`).

## Fichiers

```
app.py          Interface
model.py        Calcul des prix et ajustement automatique
donnees.py      Historique et réglages (historique.json, reglages.json)
soumission.py   Soumissions PDF (dossier soumissions/)
api_client.py   Analyse photo DeepSeek
```
