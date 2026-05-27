# Haie Estimateur

Application desktop pour estimer les prix de jobs de taille de haie à partir de photos.

## Fonctionnalités

- **Upload de photos** et analyse automatique via l'API DeepSeek Vision
- **Formulaire d'estimation** : type de haie, longueur, hauteur, densité, accès
- **Prédiction IA** avec RandomForestRegressor (scikit-learn)
- **Correction** des estimations pour améliorer le modèle
- **Historique** complet avec export CSV
- **Statistiques** : erreur moyenne, meilleur mois, type le plus rentable
- Fonctionne 100% hors ligne sauf pour l'analyse photo

## Installation

```bash
# Cloner le dépôt
git clone https://github.com/3c00/haie-estimateur.git
cd haie-estimateur

# Créer un environnement virtuel
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate sur Windows

# Installer les dépendances
pip install -r requirements.txt

# Configurer la clé API DeepSeek (optionnel)
cp .env.example .env
# Éditer .env et mettre votre clé DEEPSEEK_API_KEY
```

## Utilisation

```bash
python app.py
```

L'interface s'ouvre dans votre navigateur par défaut.

## Structure

```
haie-estimateur/
├── app.py              # Interface Gradio
├── model.py            # Modèle ML (RandomForest)
├── api_client.py       # Client DeepSeek Vision API
├── requirements.txt    # Dépendances Python
├── .env.example        # Template de configuration
└── .gitignore
```

## Tech Stack

- Python 3.11+
- Gradio (interface graphique)
- scikit-learn (RandomForestRegressor)
- DeepSeek Vision API (analyse photo)
