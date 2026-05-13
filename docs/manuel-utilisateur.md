# Manuel d'utilisation — assu_genfli

> Assistant de génération des Fiches de Livraison (FLI) pour les projets ASSU.

---

## Table des matières

1. [Présentation](#1-présentation)
2. [Installation et lancement](#2-installation-et-lancement)
3. [Interface principale](#3-interface-principale)
4. [Configuration initiale](#4-configuration-initiale)
   - 4.1 [Onglet Général](#41-onglet-général)
   - 4.2 [Onglet Projets](#42-onglet-projets)
   - 4.3 [Onglet Git](#43-onglet-git)
   - 4.4 [Onglet SFTP](#44-onglet-sftp-optionnel)
   - 4.5 [Onglet Livraison](#45-onglet-livraison)
   - 4.6 [Onglet Base de données](#46-onglet-base-de-données)
5. [Règles de routage](#5-règles-de-routage)
   - 5.1 [Onglet Règles (glob)](#51-onglet-règles-glob)
   - 5.2 [Onglet Fichiers (surcharges)](#52-onglet-fichiers-surcharges)
6. [Générer une Fiche de Livraison](#6-générer-une-fiche-de-livraison)
   - 6.1 [Étape 1 — Sélection du projet](#61-étape-1--sélection-du-projet)
   - 6.2 [Étape 2 — Sélection des fichiers](#62-étape-2--sélection-des-fichiers)
   - 6.3 [Étape 3 — Informations de livraison](#63-étape-3--informations-de-livraison)
   - 6.4 [Résultat — Fichiers générés](#64-résultat--fichiers-générés)
7. [Synchronisation Git](#7-synchronisation-git)
8. [Fenêtre de journal](#8-fenêtre-de-journal)
9. [Résolution des problèmes courants](#9-résolution-des-problèmes-courants)

---

## 1. Présentation

**assu_genfli** est un assistant en 3 étapes qui vous permet de :

1. Sélectionner un projet configuré.
2. Calculer automatiquement les fichiers modifiés depuis la dernière livraison (diff Git) et choisir ceux à inclure.
3. Renseigner les informations de livraison et générer les **Fiches de Livraison** (PDF + JSON) conformes au modèle COEXYA.

Chaque livraison produit **un PDF et un JSON par dépôt cible** (WFD, RESS et/ou COMMUN) dans le répertoire de sortie configuré.

---

## 2. Installation et lancement

### Depuis l'exécutable (poste sans Python)

Téléchargez ou copiez le répertoire `dist\assu_genfli\` sur votre poste, puis double-cliquez sur :

```
assu_genfli.exe
```

Aucune installation Python n'est requise.

### Depuis les sources (développement)

```bash
# 1. Créer et activer l'environnement virtuel
python -m venv .venv
.venv\Scripts\activate

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Lancer l'application
python main.py
```

---

## 3. Interface principale

```
┌──────────────────────────────────────────────────────────┐
│  Fichier    Affichage                                     │  ← Barre de menus
├──────────────────────────────────────────────────────────┤
│  Titre de l'étape                    Étape X / 3         │  ← En-tête
├──────────────────────────────────────────────────────────┤
│                                                          │
│                 Zone de contenu                          │  ← Contenu de l'étape
│                                                          │
├──────────────────────────────────────────────────────────┤
│  [ ← Précédent ]                       [ Suivant → ]    │  ← Navigation
└──────────────────────────────────────────────────────────┘
```

**Menu Fichier :**
- **Préférences** — ouvre la fenêtre de configuration.
- **Quitter** — ferme l'application (la géométrie de la fenêtre est sauvegardée).

**Menu Affichage :**
- **Afficher le journal** — affiche/masque la fenêtre de journalisation.

---

## 4. Configuration initiale

Accédez aux préférences via **Fichier → Préférences**.

> **Important :** La configuration est obligatoire avant toute utilisation. Renseignez au minimum un projet, le répertoire de sortie, et les informations de livraison.

### 4.1 Onglet Général

| Champ | Description |
|---|---|
| Nom d'utilisateur | Pré-remplit le champ « Livreur » à l'étape 3 |
| Répertoire de sortie | Dossier où seront écrits les PDF et JSON générés |
| Répertoire de travail | Dossier de travail local (optionnel) |
| Fichier de journal | Chemin du fichier `.log` (optionnel) |

### 4.2 Onglet Projets

Cet onglet liste vos projets. Utilisez les boutons **Ajouter**, **Modifier** et **Supprimer** pour les gérer.

**Création d'un projet :**

| Champ | Exemple | Obligatoire |
|---|---|---|
| Nom | Mon Projet ASSU | Oui |
| Code | SGK | Oui |
| Projet destinataire | Projet ASSU Client | Non |
| Dépôt WFD local | `C:\Depots\WFD_SGK` | Non |
| Dépôt WFD distant | `https://github.com/org/wfd.git` | Non |
| Dépôt RESS local | `C:\Depots\RESS_SGK` | Non |
| Dépôt RESS distant | `https://github.com/org/ress.git` | Non |
| Dépôt DEV local | `C:\Depots\DEV_SGK` | Non |
| Dépôt DEV distant | `https://github.com/org/dev.git` | Non |
| Dépôt COMMUN local | `C:\Depots\COMMUN` | Non |
| Dépôt COMMUN distant | `https://github.com/org/commun.git` | Non |

> **Conseil :** Utilisez le bouton 📁 à droite de chaque champ « local » pour parcourir vos répertoires.

### 4.3 Onglet Git

Configurez ici la méthode d'authentification aux dépôts distants.

| Champ | Description |
|---|---|
| Méthode de connexion | `SSH` (recommandé) ou `HTTPS` |
| Clé SSH | Chemin vers votre fichier de clé privée (mode SSH) |
| Identifiant HTTPS | Votre nom d'utilisateur Git (mode HTTPS) |
| Mot de passe HTTPS | Votre mot de passe ou token Git (mode HTTPS) |

### 4.4 Onglet SFTP (optionnel)

Si vous souhaitez envoyer les fichiers générés vers un serveur SFTP après génération :

| Champ | Description |
|---|---|
| Hôte | Adresse IP ou hostname du serveur SFTP |
| Port | Port SFTP (défaut : 22) |
| Identifiant | Nom d'utilisateur SFTP |
| Mot de passe | Mot de passe SFTP |

Laissez le champ « Hôte » vide pour désactiver l'envoi SFTP.

### 4.5 Onglet Livraison

Ces informations figurent en en-tête de toutes les FLI générées.

**Entité émettrice :**

| Champ | Exemple |
|---|---|
| Nom de l'entité | COEXYA |
| Nom du client | Société Générale Assurances |
| Nom du projet | ASSU_RESS |
| Mode de livraison | Dépôt sécurisé |
| Livreur (par défaut) | Jean Dupont |

**Entité destinataire :**

| Champ | Exemple |
|---|---|
| Nom de l'entité | SGR INTÉGRATION |
| Nom du client | Société Générale Assurances |
| Réception par (par défaut) | Marie Martin |

### 4.6 Onglet Base de données

Renseignez le chemin vers votre fichier SQLite de règles de routage.

- Si le fichier n'existe pas encore, il sera créé automatiquement à la première ouverture.
- Utilisez le bouton 📁 pour le localiser.

> Sans base de données, tous les fichiers détectés dans le diff seront affichés avec la cible `NONE` (non livrés).

---

## 5. Règles de routage

Les règles de routage déterminent **vers quel dépôt cible** chaque fichier doit être livré. Accédez au dialogue via **Fichier → Préférences → [Projets] → Règles de routage** ou depuis un bouton dédié dans l'interface.

Les cibles disponibles sont :

| Cible | Signification |
|---|---|
| **WFD** | Dépôt des gabarits WFD |
| **RESS** | Dépôt des ressources |
| **COMMUN** | Dépôt des éléments communs |
| **BOTH** | WFD et RESS simultanément |
| **NONE** | Fichier exclu (non livré) |

### 5.1 Onglet Règles (glob)

Chaque règle est définie par :

| Colonne | Description | Exemple |
|---|---|---|
| Pattern | Motif glob (`*`, `**`, `?`) | `COMMUN/WFD/**` |
| Cible | Dépôt de destination | `COMMUN` |
| Priorité | Entier, règle à priorité haute évaluée en premier | `15` |
| Strip prefix | Préfixe à retirer pour former le chemin destination | `COMMUN/WFD/` |

**Ordre d'évaluation :** les règles sont évaluées par **priorité décroissante**. La première règle qui correspond au chemin du fichier est appliquée.

**Exemple :**

| Pattern | Cible | Priorité | Résultat |
|---|---|---|---|
| `COMMUN/ARCH/**` | NONE | 20 | Archives exclues |
| `COMMUN/WFD/**` | COMMUN | 15 | Gabarits → dépôt COMMUN |
| `**/*.wfd` | WFD | 5 | Autres .wfd → dépôt WFD |
| `**` | RESS | 0 | Tout le reste → dépôt RESS |

**Boutons disponibles :** Ajouter / Modifier / Supprimer / Monter / Descendre.

### 5.2 Onglet Fichiers (surcharges)

Permet de définir une cible **pour un chemin exact**, avec la priorité absolue sur toutes les règles glob.

| Colonne | Description |
|---|---|
| Chemin | Chemin exact du fichier dans le dépôt DEV |
| Cible | Dépôt de destination |
| Chemin destination | Chemin dans le dépôt cible (vide = même chemin) |

> Utilisez cet onglet pour les exceptions ponctuelles. Pour les familles de fichiers, préférez les règles glob.

---

## 6. Générer une Fiche de Livraison

### 6.1 Étape 1 — Sélection du projet

L'écran affiche les projets configurés sous forme de **tuiles cliquables**.

1. Cliquez sur le projet à livrer — la tuile se colore en bleu.
2. Cliquez sur **Suivant**.

> Si aucun projet n'apparaît, allez dans **Fichier → Préférences → Projets** pour en créer un.

### 6.2 Étape 2 — Sélection des fichiers

Au chargement, l'application calcule automatiquement le diff Git entre le tag courant et le tag précédent pour chaque dépôt configuré. Une icône de chargement indique que le calcul est en cours.

**Colonnes du tableau :**

| Colonne | Description |
|---|---|
| ☑/☐ | Case à cocher — seuls les fichiers cochés seront livrés |
| Statut | `Ajouté`, `Modifié`, `Supprimé`, `Renommé`, `Manuel` |
| Fichier (DEV) | Chemin dans le dépôt source |
| Version | Numéro de version du fichier (si renseigné) |
| Maquette | Version maquette (si renseignée) |
| Destination | Chemin calculé dans le dépôt d'intégration cible |
| Dépôt | Dépôt source (WFD / RESS / DEV) |
| Cible | Dépôt de livraison calculé par les règles de routage |

**Actions disponibles dans la barre d'outils :**

| Bouton | Action |
|---|---|
| ☑ Tout cocher | Coche tous les fichiers visibles |
| ☐ Tout décocher | Décoche tous les fichiers |
| 🔍 + champ texte | Filtre la liste par chemin de fichier (temps réel) |
| ✕ | Efface le filtre |
| ⟳ Recalculer | Relance le diff Git |

**Ajout manuel de fichiers :**
Cliquez droit dans le tableau (ou utilisez le bouton dédié si disponible) pour saisir manuellement un chemin de fichier à inclure dans la livraison.

**Codes couleur :**
- Vert : fichier ajouté
- Orange : fichier modifié
- Rouge : fichier supprimé
- Gris : fichier exclus (cible NONE)

Cliquez sur **Suivant** une fois votre sélection faite.

### 6.3 Étape 3 — Informations de livraison

Cette étape affiche quatre sections :

#### Entité émettrice
Les informations sont pré-remplies depuis vos préférences. Seul le champ **Livreur** est éditable.

#### Entité destinataire
Les informations sont pré-remplies. Seul le champ **Réception par** est éditable.

#### Fiche de livraison

| Champ | Description |
|---|---|
| Identifiant FLI | Calculé automatiquement (dernier FLI + 1) — éditable |
| Date de référence | Date de la version de référence — éditable (format JJ/MM/AAAA) |
| Date de livraison | Date de livraison prévue — éditable (format JJ/MM/AAAA) |
| ☑ Livraison en env. d'intégration | Option cochée par défaut |
| ☑ Livraison d'éléments Quadient R15 | Option cochable selon le contexte |

#### Tags Git

| Champ | Description |
|---|---|
| WFD maîtres | Tag Git calculé pour le dépôt WFD — éditable |
| Ressources | Tag Git calculé pour le dépôt RESS — éditable |

Ces champs sont calculés automatiquement en arrière-plan. Vous pouvez les modifier si nécessaire.

#### Génération

Cliquez sur **Générer FLI** pour lancer la création des fichiers. La progression s'affiche dans le journal (visible via **Affichage → Afficher le journal**).

> **Attention :** Vérifiez l'identifiant FLI et les dates avant de générer. Ces valeurs figureront dans les fichiers définitifs.

### 6.4 Résultat — Fichiers générés

Les fichiers sont créés dans le **répertoire de sortie** configuré dans les préférences :

```
{output_dir}/
    FLI_{CODE}_EXT_WFD_LIV_{NNNNN}.pdf
    FLI_{CODE}_EXT_WFD_LIV_{NNNNN}.json
    FLI_{CODE}_EXT_RESS_LIV_{NNNNN}.pdf
    FLI_{CODE}_EXT_RESS_LIV_{NNNNN}.json
    FLI_{CODE}_EXT_COMMUN_LIV_{NNNNN}.pdf
    FLI_{CODE}_EXT_COMMUN_LIV_{NNNNN}.json
```

Seuls les dépôts pour lesquels au moins un fichier est sélectionné donnent lieu à un PDF.

**Exemple pour le projet SGR, livraison n°528 :**
```
FLI_SGR_EXT_RESS_LIV_00528.pdf
FLI_SGR_EXT_RESS_LIV_00528.json
FLI_SGR_EXT_WFD_LIV_00528.pdf
FLI_SGR_EXT_WFD_LIV_00528.json
```

---

## 7. Synchronisation Git

Avant de lancer la génération, vous pouvez synchroniser vos dépôts locaux depuis l'interface :

1. À l'étape 3, cliquez sur le bouton **Synchroniser** (⟳) à côté de chaque dépôt.
2. La fenêtre `GitSyncDialog` s'ouvre et effectue un `git pull` sur le dépôt sélectionné.
3. La progression s'affiche dans le dialogue et dans le journal.

> **Conseil :** Synchronisez toujours vos dépôts avant de calculer le diff (étape 2) pour avoir les tags les plus récents.

---

## 8. Fenêtre de journal

La fenêtre de journal affiche en temps réel toutes les opérations effectuées par l'application (requêtes Git, calcul du diff, génération PDF, transferts SFTP, erreurs).

**Accès :** Menu **Affichage → Afficher le journal** (raccourci : cocher/décocher).

**Fonctionnalités :**
- Défilement automatique vers les derniers messages.
- Bouton **Effacer** pour vider l'affichage.
- Le journal est également écrit dans le fichier configuré dans **Préférences → Général → Fichier de journal**.

**Niveaux de messages :**

| Préfixe | Signification |
|---|---|
| `[INFO]` | Opération normale |
| `[WARNING]` | Anomalie non bloquante |
| `[ERROR]` | Erreur à corriger |
| `[DEBUG]` | Informations détaillées (mode debug) |

---

## 9. Résolution des problèmes courants

### Aucun projet affiché à l'étape 1

**Cause :** Aucun projet n'est configuré dans les préférences.

**Solution :** `Fichier → Préférences → Projets → Ajouter`, renseignez au minimum le **Nom** et le **Code**.

---

### Le diff Git ne se lance pas / reste en chargement

**Causes possibles :**
- Les chemins des dépôts locaux ne sont pas renseignés ou incorrects.
- Le dépôt local n'est pas initialisé (`git init` / `git clone` non effectué).
- Git n'est pas installé ou n'est pas dans le `PATH`.

**Solutions :**
1. Vérifiez les chemins dans `Préférences → Projets`.
2. Vérifiez que Git est installé : ouvrez un terminal et tapez `git --version`.
3. Vérifiez le journal (`Affichage → Afficher le journal`) pour le message d'erreur exact.

---

### Tous les fichiers ont la cible « NONE »

**Cause :** Aucune base de données de règles de routage n'est configurée, ou aucune règle ne correspond aux fichiers du projet.

**Solutions :**
1. Configurez le chemin de la base dans `Préférences → Base de données`.
2. Ajoutez des règles via le dialogue de routage.
3. Utilisez `seed_routing_rules.py` pour pré-charger les règles standard.

---

### L'identifiant FLI est incorrect

**Cause :** Le script de recherche n'a pas trouvé de commit correspondant au pattern `FLI_{CODE}_EXT_LIV_\d+` dans les 50 derniers commits.

**Solution :** Modifiez manuellement le champ **Identifiant FLI** à l'étape 3.

---

### Le PDF n'est pas généré / erreur à la génération

**Causes possibles :**
- Le répertoire de sortie n'est pas configuré ou n'existe pas.
- Les assets (logo, icônes) sont manquants.
- Problème d'accès en écriture au répertoire de sortie.

**Solutions :**
1. Vérifiez `Préférences → Général → Répertoire de sortie`.
2. Consultez le journal pour l'erreur exacte.
3. Vérifiez que les fichiers `src/assets/coexya.png`, `checked.gif`, `unchecked.gif` sont présents.

---

### Erreur de connexion SFTP

**Causes possibles :**
- Hôte, port ou identifiants incorrects.
- Bibliothèque `paramiko` non installée.
- Réseau/VPN non connecté.

**Solutions :**
1. Vérifiez les paramètres dans `Préférences → SFTP`.
2. Exécutez `pip install paramiko` si vous lancez depuis les sources.
3. Laissez le champ **Hôte** vide dans les préférences pour désactiver l'envoi SFTP.

---

### Les préférences ne sont pas sauvegardées

**Cause :** Problème d'accès en écriture à `%APPDATA%\assu_genfli\preferences.json`.

**Solution :** Vérifiez les droits d'accès au dossier `%APPDATA%\assu_genfli\`.

---

*Pour toute anomalie non couverte ici, consultez le fichier de journal ou contactez l'équipe de développement.*
