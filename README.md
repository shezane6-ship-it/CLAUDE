# 🤖 Job Automation Bot

**Recherche automatique d'emploi + génération de lettres de motivation par IA (Claude + Indeed)**

---

## ✨ Fonctionnalités

| Fonctionnalité | Détail |
|---|---|
| 🔍 Recherche automatique | Indeed via MCP tools |
| 🧠 Scoring IA | Claude analyse l'adéquation CV/offre (0-100) |
| ✉ Lettre de motivation | Générée par Claude, personnalisée par poste |
| 📊 Dashboard terminal | Statistiques en temps réel |
| 🗄 Base de données | SQLite — historique complet |
| 🔔 Notifications | Slack / Discord / ntfy |
| ♾ Mode 24/7 | Boucle configurable (toutes les N heures) |

---

## 🚀 Installation rapide

```bash
# 1. Cloner et installer les dépendances
git clone <repo-url> && cd job-automation
pip install -r requirements.txt

# 2. Ajouter votre clé Claude (optionnel mais recommandé)
export ANTHROPIC_API_KEY="sk-ant-..."

# 3. Configurer interactivement
python src/main.py --setup

# 4. Lancer !
python src/main.py          # test unique
python src/main.py --loop   # mode 24/7
```

---

## ⚙️ Configuration

Éditez **`data/config.json`** :

```json
{
  "search": {
    "keywords": ["Python Developer", "Backend Engineer"],
    "location": "remote",
    "country_code": "FR",
    "job_type": "fulltime",
    "min_match_score": 60,          ← seuil IA (0-100)
    "search_interval_hours": 4      ← fréquence de la boucle
  },
  "application": {
    "max_applications_per_day": 10, ← sécurité
    "blacklisted_companies": [],
    "excluded_keywords": ["unpaid"]
  },
  "claude": {
    "model": "claude-opus-4-7",
    "cover_letter_language": "auto" ← auto | fr | en
  }
}
```

---

## 📄 Votre CV

Deux options :
1. **MCP tool** : si `get_resume` MCP est connecté, il est utilisé automatiquement
2. **Fichier local** : placez votre CV dans `data/resume.txt`

---

## 🖥 Commandes

```bash
python src/main.py              # Cycle unique
python src/main.py --loop       # Boucle 24/7
python src/main.py --dashboard  # Dashboard stats
python src/main.py --cover <id> # Lettre de motivation pour un job
python src/main.py --setup      # Configuration guidée
```

---

## 📂 Structure du projet

```
job-automation/
├── src/
│   ├── main.py           # Point d'entrée + orchestration
│   ├── config.py         # Gestion de la configuration
│   ├── database.py       # SQLite — jobs, candidatures, cache
│   ├── resume_manager.py # Lecture et cache du CV
│   ├── job_searcher.py   # Recherche Indeed (MCP)
│   ├── job_analyzer.py   # Scoring + lettres de motivation (Claude)
│   ├── application_bot.py# Logique de candidature
│   ├── notifier.py       # Slack / Discord / ntfy
│   ├── dashboard.py      # Dashboard terminal
│   └── mcp_bridge.py     # Pont vers les outils MCP Indeed
├── data/
│   ├── config.json       # ← Votre configuration
│   ├── resume.txt        # ← Votre CV (si pas de MCP)
│   └── jobs.db           # Base SQLite (auto-créée)
├── logs/
│   └── automation.log
└── requirements.txt
```

---

## 🔑 Variables d'environnement

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Clé API Claude (console.anthropic.com) |

---

## 🛡 Limites de sécurité

- **Cap quotidien** : `max_applications_per_day` (défaut : 10)
- **Score minimum** : `min_match_score` (défaut : 60/100)
- **Blacklist entreprises** : `blacklisted_companies`
- **Mots-clés exclus** : `excluded_keywords`

---

## 🤝 Mode email automatique

Pour activer l'envoi automatique par email quand l'offre contient un email de contact :

```json
"application": {
  "auto_apply_email": true,
  "sender_email": "vous@gmail.com",
  "sender_password": "votre-app-password-gmail"
}
```

> ⚠️ Utilisez un **App Password** Gmail, pas votre vrai mot de passe.
> Paramètres Google → Sécurité → Mots de passe des applications

---

## 📊 Dashboard exemple

```
════════════════════════════════════════════════════════════
  🤖  JOB AUTOMATION DASHBOARD  —  2026-05-23 14:30 UTC
════════════════════════════════════════════════════════════

  📊 Overview
     Jobs scanned   :   247
     Applied        :    34  ████████░░░░░░░░░░░░
     Interviews 🎉  :     3  █░░░░░░░░░░░░░░░░░░░
     Applied today  :     5
     Queue (new)    :    12

  ✅ Recently Applied
     [ 87] Senior Python Developer           @ Acme Corp
     [ 82] Backend Engineer                  @ StartupXYZ

  🔍 New Jobs (pending review)
     [ 75] Full Stack Developer              @ TechCorp
════════════════════════════════════════════════════════════
```
