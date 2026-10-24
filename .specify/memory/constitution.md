<!--
Sync Impact Report
- Version change: 1.1.0 → 1.2.0 (MINOR : ajout du principe VII)
- Principes ajoutés: VII. Expérience utilisateur et accessibilité
- Principes modifiés / sections retirées: aucun
- Historique : 1.0.0 (2026-10-24) a ajouté les principes I à VI, les sections Contraintes
  techniques et légales, Workflow de développement et Governance ; 1.1.0 a étendu le principe I
  (appels sortants précisés)
- Templates mis à jour: spec-template.md (parcours et états d'écran), plan-template.md (Design UX,
  gate UX, ux.md), tasks-template.md (tâches UX et accessibilité)
- TODO différés: aucun
-->

# Finance Constitution

## Core Principles

### I. Données locales d'abord
Les données financières de l'utilisateur ne quittent jamais sa machine ou son serveur sans action
explicite de sa part. Aucune télémétrie, aucun service tiers obligatoire, aucun compte en ligne
requis. Les seuls appels sortants autorisés sont les récupérations de cours et de taux et la
recherche de ticker à partir d'un code ISIN. Ils ne transmettent que des identifiants d'actifs et
des devises, jamais de quantités, de montants, de noms de comptes ni de dates d'opérations. Ces
identifiants révèlent néanmoins ce qui est détenu : la récupération automatique MUST être
désactivée tant que l'utilisateur ne l'a pas activée par un choix explicite, MUST pouvoir être
coupée à tout moment, et l'application MUST afficher la liste des services contactés et ce que
chacun reçoit. Les données sont chiffrées au repos et l'authentification est locale.
*Raison d'être : l'argument central du projet face aux solutions hébergées est la souveraineté des
données.*

### II. Journal immuable, source de vérité
Le journal de transactions est la seule source de vérité. Une transaction enregistrée n'est jamais
modifiée ni supprimée : une correction s'exprime par une transaction d'annulation ou de
régularisation. Le patrimoine et la performance à une date donnée MUST se recalculer depuis le
journal et les cours, sans valeur dérivée stockée en dur. Toute donnée dérivée mise en cache MUST
pouvoir être reconstruite à l'identique.
*Raison d'être : un import corrigé doit corriger tout l'historique, et chaque chiffre affiché doit
être traçable.*

### III. Exactitude monétaire
Tout montant, quantité et taux est représenté par un type décimal exact (`Decimal` côté Python,
`NUMERIC` ou texte décimal en base), jamais par un flottant. Chaque montant conserve sa devise
d'origine et n'est converti qu'à la date de valorisation, avec le taux de change de cette date.
Les arrondis ne se font qu'à l'affichage et selon une règle documentée.
*Raison d'être : les erreurs d'arrondi se cumulent sur des années d'historique et détruisent la
confiance dans l'outil.*

### IV. Ingestion sans scraping
Les données entrent par saisie manuelle, import de fichiers (CSV, OFX) ou API en lecture seule
documentées. Le projet MUST NOT stocker d'identifiants d'établissements financiers ni automatiser
la connexion à leurs sites. Chaque établissement est pris en charge par un importeur isolé qui
reçoit un fichier et renvoie des transactions au format commun ; un importeur n'écrit jamais en
base. Les imports sont idempotents : rejouer un fichier ne crée aucun doublon.
*Raison d'être : sécurité des utilisateurs, fragilité des connecteurs, respect des conditions
d'utilisation des établissements.*

### V. Tests chiffrés d'abord (NON-NEGOTIABLE)
Tout calcul financier (valorisation, prix de revient, XIRR, allocation, intérêts du Livret A,
dividendes, distributions de SCPI) est écrit test d'abord : cas chiffrés à la main ou issus d'une
source de référence, test qui échoue, puis implémentation. Tout importeur est livré avec un fichier
d'exemple anonymisé et un test qui vérifie le résultat attendu. Aucune fonctionnalité de calcul
n'est fusionnée sans ces tests.
*Raison d'être : une erreur silencieuse dans un chiffre financier est pire qu'un plantage.*

### VI. Simplicité et déploiement trivial
L'application s'installe avec une seule commande (`docker compose up`) et fonctionne avec SQLite
par défaut ; PostgreSQL reste une option, jamais un prérequis. Toute complexité ajoutée (nouvelle
dépendance, nouveau service, nouvelle abstraction) MUST être justifiée par un besoin du périmètre
courant (YAGNI). Les fonctionnalités hors périmètre (multi-utilisateurs, mobile, connecteurs
bancaires automatiques) ne sont pas anticipées dans l'architecture avant d'être spécifiées.
*Raison d'être : un outil auto-hébergé que l'on ne peut pas installer ou maintenir seul ne sera
pas adopté.*

### VII. Expérience utilisateur et accessibilité
Chaque fonctionnalité visible part des parcours, personas et besoins documentés dans
`docs/ux-discovery/` et les référence dans sa spécification. Chaque écran MUST définir ses états
vide, chargement, erreur et succès, et chaque message d'erreur MUST dire quoi faire ensuite.
L'interface respecte WCAG 2.2 niveau AA (contrastes, navigation au clavier, libellés de champs,
focus visible, information jamais portée par la seule couleur), s'adapte du mobile au bureau, et
utilise un seul jeu de composants et de jetons de design. Les montants, dates et nombres suivent les
conventions françaises (`1 234,56 €`, `24/10/2026`) et sont alignés pour être comparables. Toute
action destructive ou irréversible demande une confirmation explicite. Aucune fonctionnalité visible
n'est fusionnée sans sa revue UX (parcours, états, accessibilité) décrite dans le plan.
*Raison d'être : un outil de suivi de patrimoine n'est adopté que si l'on comprend ses chiffres au
premier regard et si chacun, quel que soit son handicap ou son appareil, peut s'en servir.*

## Contraintes techniques et légales

- **Stack :** backend Python avec FastAPI, frontend React avec Vite, SQLite par défaut,
  PostgreSQL en option, livraison en une image Docker qui sert l'API et le frontend compilé.
- **Frontières :** frontend et backend communiquent uniquement par une API JSON documentée
  (OpenAPI). Le moteur de performance est composé de fonctions pures, sans accès à la base.
- **Propriété intellectuelle :** l'interface s'inspire de l'organisation et des parcours de
  produits existants (dont Finary), mais le projet MUST NOT reprendre leur code, leurs assets, leurs
  marques, leurs logos, leurs icônes, leurs textes ni leur identité visuelle. Le projet a son
  propre nom, sa palette et ses textes.
- **Licence :** le projet est open source ; la licence choisie MUST être compatible avec toutes
  les dépendances et être déclarée à la racine du dépôt avant la première publication.
- **Avertissement :** les analyses fiscales et de performance sont indicatives et MUST le dire
  explicitement dans l'interface ; le projet ne fournit aucun conseil en investissement.

## Workflow de développement

- Le développement suit le flux Spec Kit : constitution, spécification, plan, tâches, implémentation.
- Chaque fonctionnalité est livrée par lots indépendants et testables ; le premier lot couvre
  le socle, le modèle de données, l'import CSV générique et le tableau de bord de patrimoine net.
- Le contrôle de conformité à cette constitution est un point de passage de la revue de plan et de
  la revue de code : un écart non justifié bloque la fusion.
- Les messages de commit suivent un format conventionnel (`feat:`, `fix:`, `docs:`, `chore:`).
- Aucune donnée personnelle réelle ne figure dans le dépôt, ni dans les fixtures de test, ni
  dans l'historique git.

## Governance

Cette constitution prévaut sur toute autre pratique du projet. Un amendement se propose par
modification de ce fichier, avec l'exposé du motif et, si des règles existantes changent, un plan
de migration du code concerné. Il est adopté par le mainteneur du dépôt.

Le versionnement suit la règle sémantique : MAJOR pour une suppression ou une redéfinition
incompatible d'un principe, MINOR pour l'ajout d'un principe ou d'une section ou l'extension
substantielle d'un existant, PATCH pour les clarifications et corrections de forme.

Toute revue de plan ou de code vérifie la conformité aux principes ci-dessus. Les écarts doivent
être justifiés par écrit dans le plan ou la description de la demande de fusion. Les consignes
d'exécution propres à l'agent de développement se trouvent dans les skills du dossier
`.claude/skills`, le contexte produit dans `docs/design-brief.md` et la découverte UX dans
`docs/ux-discovery/`.

**Version**: 1.2.0 | **Ratified**: 2026-10-24 | **Last Amended**: 2026-10-24
