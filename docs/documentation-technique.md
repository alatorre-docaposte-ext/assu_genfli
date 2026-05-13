# Documentation technique — assu_genfli

> Application de bureau Windows (Python / tkinter) pour la génération des Fiches de Livraison (FLI) des projets ASSU.

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture générale](#2-architecture-générale)
3. [Prérequis et environnement](#3-prérequis-et-environnement)
4. [Structure du projet](#4-structure-du-projet)
5. [Modules détaillés](#5-modules-détaillés)
   - 5.1 [main.py — Point d'entrée](#51-mainpy--point-dentrée)
   - 5.2 [wizard.py — Infrastructure multi-étapes](#52-wizardpy--infrastructure-multi-étapes)
   - 5.3 [screen1_project.py — Étape 1](#53-screen1_projectpy--étape-1)
   - 5.4 [screen2_files.py — Étape 2](#54-screen2_filespy--étape-2)
   - 5.5 [screen3_delivery.py — Étape 3](#55-screen3_deliverypy--étape-3)
   - 5.6 [fli_pdf.py — Génération PDF/JSON](#56-fli_pdfpy--génération-pdfjson)
   - 5.7 [git_ops.py — Opérations Git](#57-git_opspy--opérations-git)
   - 5.8 [db.py — Base de données SQLite](#58-dbpy--base-de-données-sqlite)
   - 5.9 [preferences.py — Préférences](#59-preferencespy--préférences)
   - 5.10 [prefs_dialog.py — Dialogue préférences](#510-prefs_dialogpy--dialogue-préférences)
   - 5.11 [routing_dialog.py — Règles de routage](#511-routing_dialogpy--règles-de-routage)
   - 5.12 [project_dialog.py — Gestion des projets](#512-project_dialogpy--gestion-des-projets)
   - 5.13 [sftp_ops.py — Transfert SFTP](#513-sftp_opspy--transfert-sftp)
   - 5.14 [log_window.py / logger.py — Journalisation](#514-log_windowpy--loggerpy--journalisation)
   - 5.15 [widgets.py — Composants réutilisables](#515-widgetspy--composants-réutilisables)
6. [Base de données — Schéma](#6-base-de-données--schéma)
7. [Modèle de préférences](#7-modèle-de-préférences)
8. [Moteur de routage des fichiers](#8-moteur-de-routage-des-fichiers)
9. [Format des FLI générées](#9-format-des-fli-générées)
10. [Build — Exécutable Windows](#10-build--exécutable-windows)
11. [Script d'amorçage seed_routing_rules.py](#11-script-damorçage-seed_routing_rulespy)
12. [Flux de données bout en bout](#12-flux-de-données-bout-en-bout)

---

## 1. Vue d'ensemble

**assu_genfli** est un assistant (wizard) en 3 étapes permettant de :

1. Sélectionner un projet parmi ceux configurés dans les préférences.
2. Calculer automatiquement le diff Git entre le tag courant et le tag précédent, puis sélectionner les fichiers à livrer.
3. Renseigner les informations de livraison et générer les Fiches de Livraison (PDF + JSON) par dépôt cible.

L'application gère jusqu'à **quatre dépôts Git** par projet :

| Identifiant | Rôle |
|---|---|
| `WFD` | Gabarits WFD (WorkFlow Designer) |
| `RESS` | Ressources (images, polices, données) |
| `COMMUN` | Éléments communs à plusieurs dépôts |
| `DEV` | Dépôt de développement source (lecture seule pour le diff) |

Les fichiers détectés dans le diff sont routés vers une ou plusieurs cibles grâce au moteur de règles configuré dans la base SQLite.

---

## 2. Architecture générale

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py                              │
│  Fenêtre Tk principale — Menubar — LogWindow — Wizard       │
└──────────────────────────┬──────────────────────────────────┘
                           │ instancie
                    ┌──────▼──────┐
                    │  Wizard     │  wizard.py
                    │  (3 étapes) │
                    └──┬───┬───┬──┘
                       │   │   │
              ┌────────┘   │   └──────────┐
              │            │              │
    ┌─────────▼──┐  ┌──────▼─────┐  ┌────▼──────────┐
    │ Screen1    │  │  Screen2   │  │  Screen3      │
    │ Project    │  │  Files     │  │  Delivery     │
    └────────────┘  └─────┬──────┘  └────┬──────────┘
                          │              │
                    ┌─────▼──────┐  ┌────▼──────────┐
                    │  git_ops   │  │  fli_pdf      │
                    │  (diff)    │  │  (PDF + JSON) │
                    └─────┬──────┘  └───────────────┘
                          │
                    ┌─────▼──────┐
                    │   db       │  SQLite — règles de routage
                    └────────────┘
```

Toutes les opérations longues (diff Git, récupération des tags, génération PDF) s'exécutent dans des **threads secondaires** et communiquent avec l'interface via des `queue.Queue` et `after()` de Tkinter.

---

## 3. Prérequis et environnement

| Composant | Version minimale |
|---|---|
| Python | 3.11 |
| Git | toute version récente, accessible dans `PATH` |
| OS | Windows 10 / 11 |

### Dépendances Python

| Paquet | Version minimale | Rôle |
|---|---|---|
| `gitpython` | 3.1 | Lecture des tags et de l'historique Git |
| `reportlab` | 4.0 | Génération des PDF |
| `paramiko` | 3.0 | Transfert SFTP |
| `pyinstaller` | 6.0 | Compilation en exécutable Windows |

### Installation (développement)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

---

## 4. Structure du projet

```
assu_genfli/
├── main.py                      # Point d'entrée
├── requirements.txt
├── build.bat                    # Script de build PyInstaller
├── assu_genfli.spec             # Spec PyInstaller
├── seed_routing_rules.py        # Amorçage des règles de routage
├── list.csv                     # Liste source pour seed_routing_rules.py
├── src/
│   ├── __init__.py
│   ├── wizard.py                # Infrastructure multi-étapes
│   ├── fli_pdf.py               # Génération PDF + JSON
│   ├── git_ops.py               # Opérations Git
│   ├── db.py                    # Base SQLite (règles de routage)
│   ├── preferences.py           # Préférences (lecture/écriture JSON)
│   ├── prefs_dialog.py          # Dialogue de préférences (6 onglets)
│   ├── project_dialog.py        # Dialogue création/édition de projet
│   ├── routing_dialog.py        # Dialogue règles de routage
│   ├── git_sync_dialog.py       # Dialogue synchronisation Git
│   ├── sftp_ops.py              # Transfert SFTP (paramiko)
│   ├── log_window.py            # Fenêtre de journalisation
│   ├── logger.py                # Configuration du logger
│   ├── widgets.py               # Composants tkinter (DateEntry…)
│   ├── assets/
│   │   ├── coexya.png           # Logo en-tête PDF
│   │   ├── checked.gif          # Case cochée (inline PDF)
│   │   └── unchecked.gif        # Case décochée (inline PDF)
│   └── screens/
│       ├── __init__.py
│       ├── screen1_project.py   # Étape 1 — Sélection du projet
│       ├── screen2_files.py     # Étape 2 — Sélection des fichiers
│       └── screen3_delivery.py  # Étape 3 — Informations + génération
└── docs/
    ├── documentation-technique.md   # Ce fichier
    └── manuel-utilisateur.md
```

---

## 5. Modules détaillés

### 5.1 `main.py` — Point d'entrée

Responsabilités :
- Initialise le logging et charge les préférences.
- Ouvre la base de données SQLite si un chemin est configuré.
- Crée la fenêtre `tk.Tk` principale et la redimensionne selon les préférences sauvegardées.
- Construit la **barre de menus** (`Fichier`, `Affichage`).
- Instancie `LogWindow`, `Wizard` et enregistre les trois écrans dans l'ordre.
- Sauvegarde la géométrie et l'état de la fenêtre à la fermeture (`<<AppClose>>`).

### 5.2 `wizard.py` — Infrastructure multi-étapes

La classe `Wizard` gère le squelette graphique commun :

```
┌──────────────────────────────────────────┐
│  En-tête : titre + numéro d'étape        │
├──────────────────────────────────────────┤
│  Zone contenu (frame swappable)          │
├──────────────────────────────────────────┤
│  [ Précédent ]          [ Suivant / OK ] │
└──────────────────────────────────────────┘
```

**Interface des écrans :** chaque classe d'écran doit exposer :
- `title: str` — titre affiché dans l'en-tête.
- `frame: ttk.Frame` — frame racine à afficher.
- `on_next() -> bool` — validations et sauvegarde dans `session`; retourne `False` pour bloquer la navigation.
- `on_enter()` *(optionnel)* — appelé à chaque arrivée sur l'écran.

La session est un dictionnaire partagé stocké dans `prefs["session"]`.

### 5.3 `screen1_project.py` — Étape 1

Affiche les projets configurés sous forme de **tuiles cliquables** dans un Canvas scrollable.

Chaque tuile affiche :
- Nom du projet (gras)
- Code du projet
- Chemins des dépôts locaux configurés

`on_next()` enregistre le projet sélectionné dans `prefs["session"]["selected_project"]`.

Si aucun projet n'est configuré, un message guide vers `Fichier → Préférences → Projets`.

### 5.4 `screen2_files.py` — Étape 2

**Pipeline au démarrage :**

1. Lance un thread qui appelle `git_ops.get_diff()` sur chaque dépôt configuré (WFD, RESS, DEV).
2. Pour chaque fichier détecté, consulte `db_mod.resolve_target()` pour déterminer la cible (WFD / RESS / COMMUN / BOTH / NONE).
3. Les fichiers avec cible `NONE` sont affichés mais décochés par défaut.
4. Affiche les résultats dans un `Treeview` à 8 colonnes.

**Colonnes du Treeview :**

| Colonne | Description |
|---|---|
| ☑/☐ | Case à cocher |
| Statut | A (Ajouté), M (Modifié), D (Supprimé), R (Renommé), — (Manuel) |
| Fichier (DEV) | Chemin dans le dépôt source |
| Version | Numéro de version |
| Maquette | Version maquette |
| Destination | Chemin dans le dépôt d'intégration |
| Dépôt | Dépôt source (WFD / RESS / DEV) |
| Cible | Dépôt cible calculé |

**Fonctionnalités :**
- Filtrage temps réel par chemin de fichier.
- Ajout manuel de fichiers via dialogue.
- Recalcul du diff à la demande (bouton ⟳).
- `on_next()` sauvegarde `prefs["session"]["files"]` (liste des fichiers cochés uniquement).

### 5.5 `screen3_delivery.py` — Étape 3

Affiche quatre panneaux :

1. **Entité émettrice** — données en lecture seule depuis les préférences + champ `Livreur` éditable.
2. **Entité destinataire** — données en lecture seule + champ `Réception par` éditable.
3. **Fiche de livraison** — Identifiant FLI (auto-calculé + éditable), dates de référence et de livraison, checkboxes options.
4. **Git / Livraison** — Tags Git WFD et RESS (auto-calculés), bouton de synchronisation, bouton **Générer FLI**.

**Calcul automatique de l'identifiant FLI :**
Parcourt les 50 derniers commits du dépôt WFD (ou RESS) à la recherche du pattern `FLI_{CODE}_EXT_LIV_\d+`. Propose `dernier_id + 1`.

**Génération :**
Appelle `fli_pdf.generate_fli()` dans un thread secondaire pour chaque dépôt cible concerné. Les fichiers sont regroupés par cible à partir de `session["files"]`.

### 5.6 `fli_pdf.py` — Génération PDF/JSON

Produit, pour chaque dépôt cible, un couple de fichiers :
- `FLI_{CODE}_EXT_{REPO}_LIV_{NNNNN}.pdf`
- `FLI_{CODE}_EXT_{REPO}_LIV_{NNNNN}.json`

**Structure du PDF (ReportLab Platypus) :**

| Section | Contenu |
|---|---|
| En-tête | Logo COEXYA + titre "FICHE DE LIVRAISON" |
| Objet | Identifiant FLI, dates |
| Signatures | Tableau émetteur/destinataire |
| Description | Tableau des fichiers livrés (chemin DEV, chemin destination, statut) |
| Stockage | Répertoire de sortie |
| Identification | Chemins dépôts + tag Git |

La pagination est gérée par `_NumberedCanvas` qui surcharge `showPage()` pour injecter un pied de page `Page X / Y`.

**Format JSON :**
Reprend la même structure que le PDF sous forme de dictionnaire Python sérialisé.

### 5.7 `git_ops.py` — Opérations Git

Fonctions principales :

| Fonction | Description |
|---|---|
| `get_tags(repo_path, pattern)` | Tags triés par date, filtrables par pattern glob |
| `get_latest_beta1_tag(repo_path)` | Dernier tag `*-beta1` |
| `get_next_beta1_tag(repo_path)` | Calcule le prochain tag `vX.Y.Z-beta1` |
| `get_last_fli_commit(repo_path, code)` | Dernier commit dont le message contient `FLI_{CODE}_EXT_LIV_\d+` |
| `get_diff(repo_path, tag_from, tag_to)` | Diff entre deux tags → liste de fichiers modifiés |
| `pull(repo_path, ...)` | `git pull` avec gestion SSH / HTTPS |

La stratégie de calcul du prochain tag (`get_next_beta1_tag`) :
1. Cherche le dernier tag `*-beta1` → extrait `vMAJ.MIN.PATCH` → propose `vMAJ.MIN.(PATCH+1)-beta1`.
2. Si absent, cherche le dernier tag `vMAJ.MIN.PATCH` et incrémente PATCH.
3. Si rien trouvé, retourne `''`.

### 5.8 `db.py` — Base de données SQLite

**Schéma version 3 :**

```sql
projects (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
)

routing_rules (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    pattern      TEXT NOT NULL,
    target       TEXT NOT NULL CHECK(target IN ('WFD','RESS','COMMUN','BOTH','NONE')),
    priority     INTEGER NOT NULL DEFAULT 0,
    strip_prefix TEXT NOT NULL DEFAULT '',
    UNIQUE(project_id, pattern)
)

file_routes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    path         TEXT NOT NULL,
    target       TEXT NOT NULL CHECK(target IN ('WFD','RESS','COMMUN','BOTH','NONE')),
    dest_path    TEXT NOT NULL DEFAULT '',
    UNIQUE(project_id, path)
)
```

**Ordre de priorité pour la résolution d'une cible :**
1. `file_routes` — surcharge exacte par chemin (priorité absolue).
2. `routing_rules` — règles glob, évaluées par `priority DESC`, première règle gagnante.
3. Défaut : `NONE`.

`strip_prefix` dans `routing_rules` et `dest_path` dans `file_routes` permettent de transformer le chemin DEV en chemin dans le dépôt d'intégration.

**Migration automatique :** à chaque ouverture, `open_db()` vérifie `PRAGMA user_version` et applique les migrations nécessaires (V1→V2→V3).

### 5.9 `preferences.py` — Préférences

Fichier : `%APPDATA%\assu_genfli\preferences.json`

Fonctions exposées :

| Fonction | Description |
|---|---|
| `load() -> dict` | Charge depuis le disque, fusionne avec les défauts |
| `save(prefs)` | Sérialise en JSON (indent=2, UTF-8) |
| `get(prefs, *keys, default)` | Lecture imbriquée sécurisée |
| `set(prefs, *keys, value)` | Écriture imbriquée sécurisée |

La fusion est récursive (`_deep_merge`) : les valeurs absentes dans le fichier sont complétées par les défauts sans écraser les valeurs existantes.

### 5.10 `prefs_dialog.py` — Dialogue préférences

Fenêtre modale à **6 onglets** :

| Onglet | Contenu |
|---|---|
| Général | Nom d'utilisateur, répertoire de sortie, répertoire de travail, fichier de log |
| Projets | Liste des projets (Ajouter / Modifier / Supprimer) avec `ProjectDialog` |
| Git | Méthode de connexion (SSH / HTTPS), clé SSH, identifiants HTTPS |
| SFTP | Hôte, port, identifiants de connexion SFTP |
| Livraison | Informations entité émettrice et destinataire |
| Base de données | Chemin du fichier SQLite |

Les modifications sont appliquées via **Appliquer** (sans fermer) ou **OK** (applique et ferme). Le callback `on_apply(prefs)` est appelé dans les deux cas.

### 5.11 `routing_dialog.py` — Règles de routage

Fenêtre modale avec sélecteur de projet et deux onglets :

- **Règles** : tableau des règles glob (pattern, cible, priorité, strip_prefix) avec CRUD complet.
- **Fichiers** : surcharges par chemin exact (path, cible, dest_path) avec CRUD complet.

Les couleurs par cible facilitent la lecture :

| Cible | Couleur |
|---|---|
| WFD | Bleu `#0055cc` |
| RESS | Vert `#007700` |
| COMMUN | Violet `#6600aa` |
| BOTH | Orange-brun `#884400` |
| NONE | Gris `#888888` |

### 5.12 `project_dialog.py` — Gestion des projets

Boîte de dialogue de création/édition avec les champs :

| Champ | Description |
|---|---|
| `name` | Alias du projet |
| `code` | Code court (ex: `SGK`, `SGR`) |
| `dest_projet` | Nom du projet côté destinataire |
| `depot_wfd_local` | Chemin local du dépôt WFD |
| `depot_wfd_distant` | URL distante du dépôt WFD |
| `depot_ress_local` | Chemin local du dépôt RESS |
| `depot_ress_distant` | URL distante du dépôt RESS |
| `depot_dev` | Chemin local du dépôt DEV |
| `depot_dev_distant` | URL distante du dépôt DEV |
| `depot_commun_local` | Chemin local du dépôt COMMUN |
| `depot_commun_distant` | URL distante du dépôt COMMUN |

### 5.13 `sftp_ops.py` — Transfert SFTP

Fonction `upload_files()` : envoie une liste de fichiers locaux vers un répertoire distant via SFTP (paramiko). Le mot de passe est stocké obfusqué en base64 dans les préférences (non chiffré — à utiliser sur poste de travail uniquement).

### 5.14 `log_window.py` / `logger.py` — Journalisation

- `logger.py` configure un logger Python nommé `assu_genfli` avec un handler fichier (si configuré) et un handler en mémoire (`QueueHandler`).
- `log_window.py` ouvre une fenêtre secondaire `Toplevel` qui consomme la queue de log et affiche les entrées en temps réel dans un `Text` en lecture seule. L'état visible/masqué est persisté dans les préférences.

### 5.15 `widgets.py` — Composants réutilisables

- **`DateEntry`** : champ de saisie de date avec bouton calendrier (🗓). Accepte les formats `DD/MM/YYYY`. Utilisé dans `Screen3Delivery` pour les dates de référence et de livraison.

---

## 6. Base de données — Schéma

Voir [§ 5.8](#58-dbpy--base-de-données-sqlite) pour le DDL complet.

**Chemin par défaut :** libre, configuré dans `Préférences → Base de données`.

**Migrations :**

| Version | Changements |
|---|---|
| 1 | Création initiale (`projects`, `routing_rules`, `file_routes`) |
| 2 | Ajout de `COMMUN` dans les contraintes `CHECK` |
| 3 | Ajout de `strip_prefix` sur `routing_rules`, `dest_path` sur `file_routes` |

---

## 7. Modèle de préférences

```json
{
  "general": {
    "username": "",
    "work_dir": "",
    "log_file": "",
    "output_dir": ""
  },
  "projects": [
    {
      "name": "Mon projet",
      "code": "SGK",
      "dest_projet": "Projet destinataire",
      "depot_wfd_local": "C:/depots/wfd",
      "depot_wfd_distant": "https://github.com/org/wfd.git",
      "depot_ress_local": "C:/depots/ress",
      "depot_ress_distant": "https://github.com/org/ress.git",
      "depot_dev": "C:/depots/dev",
      "depot_dev_distant": "https://github.com/org/dev.git",
      "depot_commun_local": "C:/depots/commun",
      "depot_commun_distant": "https://github.com/org/commun.git",
      "conn_method": "SSH"
    }
  ],
  "git": {
    "ssh_key": "",
    "https_login": "",
    "https_password": "",
    "conn_method": "SSH"
  },
  "sftp": {
    "host": "",
    "port": 22,
    "username": "",
    "password": ""
  },
  "livraison": {
    "emettrice": {
      "nom": "",
      "client": "",
      "projet": "",
      "mode": "",
      "livreur": ""
    },
    "destinataire": {
      "nom": "",
      "client": "",
      "reception_par": ""
    }
  },
  "db": {
    "db_path": ""
  }
}
```

---

## 8. Moteur de routage des fichiers

Pour un chemin de fichier donné, la résolution s'effectue dans l'ordre suivant :

```
chemin → file_routes (match exact) → cible trouvée ?
                    ↓ non
         routing_rules (glob fnmatch, priority DESC) → cible trouvée ?
                    ↓ non
         NONE (exclusion par défaut)
```

**Calcul du chemin de destination :**

```
chemin_dest = chemin_source.removeprefix(strip_prefix)
```

Exemple :
- Source : `COMMUN/WFD/GABARIT_SOGECAP.wfd`
- `strip_prefix` : `COMMUN/WFD/`
- Destination : `GABARIT_SOGECAP.wfd`

Les fichiers à cible `BOTH` génèrent deux entrées dans les fichiers de livraison (une pour WFD, une pour RESS).

---

## 9. Format des FLI générées

### Nommage

```
FLI_{CODE}_EXT_{REPO}_LIV_{NNNNN}.pdf
FLI_{CODE}_EXT_{REPO}_LIV_{NNNNN}.json
```

- `{CODE}` : code du projet (ex: `SGR`)
- `{REPO}` : dépôt cible (`WFD`, `RESS`, `COMMUN`)
- `{NNNNN}` : identifiant FLI sur 5 chiffres (ex: `00528`)

Exemple : `FLI_SGR_EXT_RESS_LIV_00528.pdf`

### Structure JSON

```json
{
  "fli_id": "00528",
  "code": "SGR",
  "repo": "RESS",
  "date_reference": "13/05/2026",
  "date_livraison": "13/05/2026",
  "emettrice": { "nom": "...", "client": "...", "projet": "...", "mode": "...", "livreur": "..." },
  "destinataire": { "nom": "...", "client": "...", "reception_par": "..." },
  "tag_git": "v1.2.94-beta1",
  "fichiers": [
    { "path": "GABARIT.wfd", "dest_path": "GABARIT.wfd", "status": "M" }
  ],
  "options": {
    "livraison_integration": true,
    "livraison_quadient": false
  }
}
```

---

## 10. Build — Exécutable Windows

```bat
build.bat
```

Exécute PyInstaller avec `assu_genfli.spec`. Le livrable est :

```
dist\assu_genfli\assu_genfli.exe
```

Le spec embarque les assets (`src/assets/`) et les binaires gitpython nécessaires. L'exécutable est **autonome** (mode `onedir`) — aucune installation Python requise sur le poste cible.

---

## 11. Script d'amorçage `seed_routing_rules.py`

Pré-charge les règles de routage dans la base à partir de l'analyse de `list.csv`.

**Usage :**

```bash
python seed_routing_rules.py              # tous les projets
python seed_routing_rules.py SGK          # projet SGK uniquement
python seed_routing_rules.py SGK SGR      # projets SGK et SGR
```

Les règles définies couvrent la structure du dépôt DEV `ASSU_RESS_EXTERNE` :

| Pattern glob | Cible | Priorité |
|---|---|---|
| `COMMUN/ARCH/**` | NONE | 20 |
| `SOGESSUR/DATA/JIRA/**` | NONE | 20 |
| `OUTILS/**` | NONE | 20 |
| `*_Workspace*.xml` | NONE | 20 |
| `COMMUN/WFD/**` | COMMUN | 15 |
| `COMMUN/FONTE/**` | COMMUN | 15 |
| `COMMUN/LIB/**` | COMMUN | 15 |
| `SOGESSUR/DATA/**` | RESS | 10 |
| `SOGESSUR/IMAGE/**` | RESS | 10 |
| `**/*.wfd` | WFD | 5 |
| `**` | RESS | 0 |

---

## 12. Flux de données bout en bout

```
Utilisateur
    │
    ├─ [Étape 1] Sélectionne un projet
    │       └─► session["selected_project"] = { code, depots… }
    │
    ├─ [Étape 2] Diff Git calculé en thread
    │       ├─► git_ops.get_diff(depot_dev, tag_from, tag_to)
    │       ├─► db.resolve_target(project_id, path) → cible
    │       └─► session["files"] = [ {path, dest_path, status, cible, checked} ]
    │
    ├─ [Étape 3] Renseigne informations de livraison
    │       ├─► git_ops.get_next_beta1_tag(depot_wfd)
    │       ├─► git_ops.get_last_fli_commit(depot_wfd, code) → fli_id
    │       └─► Utilisateur valide et clique "Générer FLI"
    │
    └─ [Génération] Thread secondaire
            ├─► Regroupe session["files"] par cible
            ├─► fli_pdf.generate_fli(…) → PDF + JSON par cible
            └─► sftp_ops.upload_files(…) [optionnel]
```
