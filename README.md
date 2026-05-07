# assu_genfli

Assistant de génération des Fiches de Livraison (FLI) pour les projets ASSU.

Application de bureau Windows (Python / tkinter) permettant de préparer, valider et générer les documents de livraison au format PDF et JSON, à partir des dépôts Git du projet.

---

## Fonctionnalités

- **Assistant en 3 étapes** : sélection du projet → sélection des fichiers → informations de livraison
- **Détection automatique** du dernier identifiant FLI et du prochain tag Git (`vX.Y.Z-beta1`) à partir de l'historique des dépôts
- **Sélection des fichiers** avec filtrage par cible (WFD, RESS, COMMUN, BOTH) ; les fichiers marqués NONE sont exclus
- **Génération de PDF** conformes au modèle FLI COEXYA (un PDF par dépôt cible), avec logo, tableaux formatés, cases à cocher, pagination
- **Génération de JSON** accompagnateur de chaque PDF (mêmes données structurées)
- **Préférences persistantes** (entités émettrice/destinataire, chemins locaux des dépôts, répertoire de sortie, journalisation)
- **Synchronisation Git** des dépôts locaux depuis l'interface

---

## Prérequis

- Python 3.11 ou supérieur
- Git installé et accessible dans le `PATH`
- Accès en lecture aux dépôts locaux WFD, RESS et/ou COMMUN

---

## Installation (développement)

```bash
# Créer et activer un environnement virtuel
python -m venv .venv
.venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt
```

### Dépendances principales

| Paquet | Rôle |
|---|---|
| `gitpython` | Lecture des tags et de l'historique Git |
| `reportlab` | Génération des PDF |
| `pyinstaller` | Compilation en exécutable Windows |

---

## Lancement

```bash
python main.py
```

---

## Build (exécutable Windows autonome)

```bat
build.bat
```

Le livrable est généré dans `dist\assu_genfli\assu_genfli.exe`.

---

## Structure du projet

```
main.py                      Point d'entrée
requirements.txt
build.bat                    Script de build PyInstaller
assu_genfli.spec             Spec PyInstaller
src/
  screens/
    screen1_project.py       Étape 1 — Sélection du projet
    screen2_files.py         Étape 2 — Sélection des fichiers
    screen3_delivery.py      Étape 3 — Informations de livraison + génération FLI
  fli_pdf.py                 Génération PDF et JSON des Fiches de Livraison
  git_ops.py                 Opérations Git (tags, historique, diff)
  wizard.py                  Infrastructure de l'assistant multi-étapes
  preferences.py             Chargement / sauvegarde des préférences (JSON)
  prefs_dialog.py            Dialogue de configuration
  project_dialog.py          Dialogue de gestion des projets
  routing_dialog.py          Dialogue de configuration des règles de routage
  db.py                      Base SQLite des règles de routage (schéma v2)
  log_window.py              Fenêtre de journalisation en temps réel
  logger.py                  Configuration du logger applicatif
  widgets.py                 Composants tkinter réutilisables
  assets/
    coexya.png               Logo COEXYA (en-tête PDF)
    checked.gif              Case cochée (inline PDF)
    unchecked.gif            Case décochée (inline PDF)
```

---

## Préférences

Les préférences sont stockées dans :

```
%APPDATA%\assu_genfli\preferences.json
```

Paramètres configurables depuis l'interface (`Fichier > Préférences`) :

- **Général** : nom d'utilisateur, répertoire de sortie des PDF, répertoire de travail, fichier de journal
- **Projets** : chemins locaux et distants des dépôts WFD / RESS / COMMUN
- **Git** : méthode de connexion (SSH / HTTPS), clé SSH, identifiants HTTPS
- **Livraison** : entité émettrice (nom, client, projet, mode, livreur) et destinataire

---

## Format des FLI générées

Chaque livraison produit, par dépôt cible :

- `FLI_{CODE}_EXT_{REPO}_LIV_{NNNNN}.pdf` — Fiche de Livraison PDF
- `FLI_{CODE}_EXT_{REPO}_LIV_{NNNNN}.json` — Données structurées équivalentes

Exemple : `FLI_SGR_EXT_RESS_LIV_00528.pdf`
