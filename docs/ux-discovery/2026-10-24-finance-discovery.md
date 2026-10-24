# Document de découverte UX : Finance

**Date** : 2026-10-24
**Auteur** : Frederick Sales + UX Superpowers
**Statut** : Brouillon (à relire)
**Sources** : `docs/design-brief.md`, entretien de découverte. Aucune donnée de recherche externe : toutes les affirmations sont des hypothèses validées par le porteur du projet, à confirmer par des tests d'usage.

## 1. Problem Brief

- **Problème** : suivre son patrimoine réparti entre PEE, PEA, CTO, assurance-vie, Livret A, SCPI et fonds, sans confier ses données à un service hébergé.
- **Utilisateurs concernés** : épargnant français qui détient plusieurs enveloppes dans plusieurs établissements, sans compétences techniques particulières.
- **Alternatives actuelles** : Finary et autres agrégateurs, tableurs maison, espaces en ligne des établissements.
- **Pourquoi elles échouent** : les agrégateurs exigent la confiance et les identifiants bancaires ; les tableurs sont laborieux et fragiles face aux cas particuliers (abondement PEE, SCPI à deux prix, fonds en euros) ; les espaces des établissements n'offrent aucune vue consolidée.
- **Périmètre** : nouveau produit, utilisateur unique, saisie manuelle et import CSV/OFX.

## 2. Personas

### Persona : L'épargnant salarié multi-enveloppes (Primaire)

**Rôle et contexte** : salarié français avec PEE/FCPE, PEA/CTO, assurance-vie, Livret A et éventuellement des SCPI, chez plusieurs établissements.

**Comportement actuel** : point mensuel en ouvrant chaque espace en ligne ; consultation avant de renforcer ou d'arbitrer une ligne.

- **Objectif principal** : voir son patrimoine net consolidé et sa performance réelle.
- **Objectif émotionnel** : se sentir en contrôle et en confiance, sans craindre qu'un tiers exploite ses données.
- **Objectif social** : être un investisseur sérieux et autonome.

**Frustrations**
- Une vue par établissement, aucun total consolidé.
- Les cas particuliers faussent les chiffres.
- Les agrégateurs demandent d'abandonner ses données ou ses identifiants.

**Outils et contournements** : espaces en ligne, tableur, Finary pour la consolidation.

**Contexte d'usage**
- **Quand** : mensuel, plus ponctuellement avant une décision.
- **Où et sur quoi** : bureau, ordinateur (mobile hors périmètre).
- **Contraintes** : débutant technique ; tout doit passer par l'interface, sans terminal.

> « Je veux voir tout mon patrimoine au même endroit, avec des chiffres justes, sans donner mes données à personne. »

**Priorité** : Primaire. **Preuve** : hypothèse validée par le porteur du projet, à confirmer par l'usage.

## 3. Jobs to Be Done

| # | Job | Imp. | Sat. | Opportunité |
|---|-----|------|------|-------------|
| J1 (principal) | Quand je fais mon point mensuel, je veux voir mon patrimoine net consolidé et son évolution, afin de savoir où j'en suis sans ouvrir cinq espaces en ligne. | 9 | 4 | 14 |
| J2 | Quand j'hésite à renforcer ou arbitrer une ligne, je veux connaître ma performance réelle et ma répartition, afin de décider sur des chiffres justes. | 9 | 3 | 15 |
| J3 | Quand j'ai réalisé une opération ou reçu un relevé, je veux l'enregistrer sans doublon ni erreur, afin de garder un historique fiable. | 8 | 4 | 12 |
| J4 | Quand je confie mes données à un outil, je veux garder la maîtrise de ce qui sort de chez moi, afin de rester serein. | 9 | 5 | 13 |
| J5 | Quand je mets l'outil en route la première fois, je veux l'installer et le configurer sans terminal, afin de l'utiliser sans compétences techniques. | 8 | 3 | 13 |

- **Émotionnel** : confiant dans les chiffres, en contrôle, serein sur la confidentialité.
- **Social** : investisseur sérieux et autonome, capable d'expliquer ses choix.
- **Réussite** : le total concorde avec les relevés de chaque établissement ; une décision se prend en moins de cinq minutes.

**Solutions concurrentes** : Finary (consolidation, mais données chez un tiers), tableur (maîtrisé, mais laborieux), espaces des établissements (fiables, mais fragmentés).

**Insight clé** : les besoins les moins servis sont une performance juste (J2) et une installation sans terminal (J5) ; la confiance dans les chiffres et la confidentialité sont la raison de choisir l'outil.

## 4. Parcours utilisateur

### Parcours actuel : point mensuel

| Phase | Action | Touchpoint | Ressenti | Frictions | Durée |
|---|---|---|---|---|---|
| Déclenchement | Décide de faire le point | Rappel mental, mail de relevé | Neutre | Aucun rappel structuré | – |
| Collecte | Ouvre chaque espace en ligne | 4 à 5 sites, identifiants multiples | Agacé | Connexions, 2FA, formats différents | 15 à 25 min |
| Consolidation | Reporte les montants dans un tableur | Tableur / calculatrice | Anxieux | Cas particuliers faussent le total | 10 min |
| Lecture | Cherche évolution et répartition | Tableur, graphiques maison | Incertain | Pas de courbe fiable, pas de XIRR | 5 à 10 min |
| Décision | Renforcer ou arbitrer ? | Courtier, notes | Hésitant | Chiffres douteux | variable |
| Erreur | Un total ne colle pas au relevé | Relevés papier / PDF | Frustré | Chasse à l'écart sans traçabilité | 20+ min |

**Moments de vérité** : la collecte (abandon du suivi si trop pénible) ; le premier total qui ne concorde pas avec un relevé (perte de confiance).
**Plus forte friction déclarée** : la collecte.
**À préserver** : la fiabilité des relevés des établissements.

### Parcours désiré : point mensuel

| Phase | Action | Touchpoint | Ressenti cible | Opportunité de conception | Métrique |
|---|---|---|---|---|---|
| Déclenchement | Ouvre l'application | Page d'accueil | Serein | Date de dernière mise à jour visible, rappel d'import discret | Fréquence de visite |
| Collecte | Dépose un export par établissement ou saisit une opération | Import guidé (glisser-déposer, aperçu avant validation) | Efficace | Lignes reconnues, doublons détectés, résultat clair | Collecte < 5 min |
| Consolidation | Rien à faire | Automatique | Détendu | Total recalculé depuis le journal, écarts signalés | – |
| Lecture | Lit patrimoine net, courbe, répartition | Dashboard | Confiant | Chiffres traçables jusqu'à la transaction, formats FR | Premier chiffre < 10 s |
| Décision | Compare positions et performance | Détail compte / position | En contrôle | Plus-values latentes, XIRR, mention « indicatif » | Décision < 5 min |
| Erreur | Un total ne colle pas au relevé | Contrôle de solde déclaré | Rassuré | Écart expliqué, correction par régularisation, message actionnable | Écarts résolus sans aide |

**Première utilisation (débutant)** : installation et création du compte local sans terminal, assistant « ajouter mon premier compte », import d'exemple, premier tableau de bord en moins de 10 minutes.

### Analyse des écarts

| Phase | Écart | Priorité |
|---|---|---|
| Collecte | Import guidé avec aperçu | Haute |
| Lecture | Chiffres consolidés fiables et traçables | Haute |
| Première utilisation | Installation et onboarding sans terminal | Haute |
| Erreur | Explication et correction des écarts | Moyenne |
| Décision | Performance (XIRR) et diversification | Moyenne (phase 2) |
| Déclenchement | Rappels d'import | Basse |

## 5. Métriques de succès

**Contrainte** : le principe I de la constitution interdit toute télémétrie sortante. Aucune métrique n'est collectée à distance ; elles sont mesurées en test d'usage ou par des compteurs locaux, visibles uniquement dans l'application.

### North Star
- **Métrique** : temps entre l'ouverture de l'application et un total de patrimoine que l'utilisateur juge juste.
- **Référence** : 30 à 45 min aujourd'hui (estimation, à mesurer).
- **Cible à 6 mois** : moins de 5 minutes de collecte et lecture.
- **Pourquoi** : réunit J1 (consolidation) et la confiance dans les chiffres.

### Garde-fous
| Métrique | Protège contre | Cible | Seuil d'alerte |
|---|---|---|---|
| Écart total affiché / relevés | Perte de confiance | 0 € après contrôle de solde | Tout écart non expliqué |
| Imports rejoués sans doublon | Corruption du journal | 100 % | Un seul doublon |
| Appels sortants hors cours et taux | Violation de la confidentialité | 0, et uniquement si activés | Tout autre appel |
| Violations WCAG 2.2 AA bloquantes | Exclusion d'utilisateurs | 0 | Une seule |

### Indicateurs avancés
| Métrique | Prédit | Mesure |
|---|---|---|
| Temps jusqu'au premier tableau de bord après installation (< 10 min, sans terminal) | Adoption | Test d'usage chronométré |
| Part des lignes reconnues à l'import sans correction | Réussite de la collecte | Compteur local à l'import |
| Tâches réussies sans aide (ajouter un compte, importer, lire le patrimoine net), ≥ 90 % | Utilisabilité | Test d'usage |

### Qualitatif
| Signal | Méthode | Fréquence |
|---|---|---|
| Utilisabilité | 3 séances de test chronométrées (porteur du projet + 1 à 2 proches débutants) | À chaque jalon |
| Retours de fonctionnalité | Tickets du dépôt | En continu |

### Plan de réponse
| Métrique | Si elle s'améliore | Si stable | Si elle se dégrade |
|---|---|---|---|
| Temps de collecte | Étendre les importeurs | Simplifier l'import guidé | Revoir l'import avant toute nouvelle fonction |
| Écarts relevés | Passer à la performance (phase 2) | Renforcer la traçabilité | Geler les nouvelles fonctions, corriger le calcul |
| Tâches débutant réussies | Passer au jalon suivant | Itérer l'onboarding | Revoir l'onboarding en priorité |

## 6. Principes de conception

1. **La confiance avant la richesse** : chaque chiffre affiché est traçable jusqu'aux transactions.
   - *Parce que* : la confiance dans le total est l'émotion cible et la cause d'abandon.
   - *Cela signifie* : liens de chaque valeur vers sa source, écarts expliqués, mention « indicatif ».
   - *Cela exclut* : des indicateurs sophistiqués sans origine vérifiable.
2. **Zéro terminal pour l'utilisateur** : tout se fait dans l'interface.
   - *Parce que* : l'utilisateur est débutant technique.
   - *Cela signifie* : installation, configuration, import et sauvegarde guidés.
   - *Cela exclut* : des étapes qui exigent un shell ou un fichier de configuration.
3. **Importer, pas ressaisir** : la collecte est la plus grosse friction.
   - *Cela signifie* : glisser-déposer, aperçu avant validation, doublons détectés.
   - *Cela exclut* : des formulaires lourds comme voie principale ; le scraping.
4. **Confidentialité visible** : l'utilisateur voit ce qui sort de chez lui.
   - *Cela signifie* : récupération des cours désactivée par défaut, liste des services contactés.
   - *Cela exclut* : toute télémétrie, même anonyme.
5. **Lisible au premier regard, accessible à tous** : formats français, états explicites, WCAG 2.2 AA.
   - *Cela signifie* : `1 234,56 €`, montants alignés, états vide/chargement/erreur/succès, clavier complet.
   - *Cela exclut* : l'information portée par la seule couleur.

## 7. Hypothèses et risques

### Hypothèses validées par le porteur du projet
- L'utilisateur principal est un épargnant salarié multi-enveloppes, débutant technique.
- Le point mensuel et la décision d'investissement sont les usages dominants.
- La collecte est la plus forte friction.

### Hypothèses non validées
- Le temps actuel de 30 à 45 min est une estimation : à mesurer sur un point mensuel réel.
- Les exports CSV/OFX sont disponibles et exploitables chez tous les établissements visés. À valider en listant les exports réels (PEE, courtier, assureur).
- Un proche débutant réussira l'onboarding sans aide. À valider par un test d'usage.

### Risques
| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| `docker compose up` bloque un utilisateur débutant | Haute | Haute | Étudier une livraison simplifiée (installateur, hébergement domestique clé en main) ; décision à prendre avant le plan |
| Exports d'établissements non standards ou absents | Moyenne | Haute | Import CSV générique avec correspondance de colonnes, saisie manuelle en repli |
| Interface Finary-like perçue comme copie | Faible | Moyenne | Identité visuelle propre (constitution, contrainte IP) |
| Pas de télémétrie, donc retours tardifs | Moyenne | Moyenne | Tests d'usage à chaque jalon |

## 8. Contraintes et limites

**Techniques** : FastAPI, React/Vite, SQLite par défaut, une image Docker, API JSON documentée.
**Utilisateur** : débutant technique, ordinateur, accessibilité WCAG 2.2 AA.
**Légales et produit** : pas de scraping ni d'identifiants bancaires, pas de reprise d'assets de Finary, analyses fiscales et de performance indicatives, aucune télémétrie sortante.

- **Dans le périmètre** : saisie manuelle, import CSV/OFX, cours automatiques optionnels, dashboard patrimoine net, détail par compte, onboarding sans terminal.
- **Hors périmètre** : multi-utilisateurs, mobile, connecteurs bancaires automatiques, social, conseil, exécution d'ordres.
- **À considérer plus tard** : budget et cashflow, objectifs, rapport fiscal, partage en lecture seule, alertes.

## 9. Synthèse de recherche

Aucune donnée de recherche externe n'a été fournie. Voir les hypothèses non validées (section 7).

## 10. Prochaines étapes

- [ ] Trancher la livraison pour un utilisateur débutant (docker compose seul, installateur ou autre) avant `/speckit-plan`.
- [ ] Lister les exports réels disponibles chez les établissements visés (PEE, courtier, assureur).
- [ ] Mesurer un point mensuel actuel pour établir la référence de la North Star.
- [ ] Lancer `/speckit-checklist` (thème UX) puis `/speckit-analyze` sur la spec 001, et `/speckit-converge` pour les écarts.
- [ ] Ajouter la section « User Experience » à `specs/001-wealth-dashboard-foundation/spec.md` en référence à ce document.
- [ ] Passer à `superpowers:brainstorming` pour le design technique et visuel (design system, jetons).
