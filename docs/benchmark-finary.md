# Analyse fonctionnelle de Finary et écrans à créer

*Rédigé le 24 octobre 2026. Sert de base aux prochaines specs (`specs/002-…` et suivantes).*

## Méthode et limites

- `app.finary.com/v2` demande un compte, et l'environnement de travail n'avait pas accès au domaine
  `finary.com`. L'analyse s'appuie donc sur les pages publiques de Finary (offres, notes de version,
  centre d'aide, forum) telles que les indexe la recherche web, et sur des tests publiés par des tiers.
- Une partie des tests tiers sont des blogs affiliés. Ils se contredisent sur les prix et sur la
  formule qui donne accès à chaque fonction, d'où l'absence de prix ici.
- Les libellés exacts des menus de la v2 n'ont pas pu être vérifiés. Le découpage ci-dessous suit les
  fonctions, pas l'ordre des onglets de Finary.
- On reprend l'organisation et les fonctions, jamais l'identité visuelle (nom, logo, couleurs,
  textes), comme l'exige déjà la spec 001.

Légende de l'état dans l'application : ✅ fait (lot 001) · 🟡 partiel · ⬜ à faire ·
🚫 écarté (contraire aux principes du projet : auto-hébergé, rien ne sort sans accord, pas de conseil).

## 1. Cartographie des fonctions de Finary

### 1.1 Tableau de bord et patrimoine

| Fonction Finary | Détail | État ici |
|---|---|---|
| Patrimoine **brut / net / financier** | Net = brut − capital restant dû des crédits ; vue « patrimoine financier » à part | 🟡 net « hors dettes » seulement |
| Courbe d'évolution | Périodes 1 sem., 1 mois, 3 mois (ajout janvier 2026), 1 an, depuis le début | 🟡 sans la période 3 mois |
| Répartition | Par classe d'actifs, par enveloppe, par établissement, par membre de la famille | 🟡 par classe d'actifs seulement |
| Vue « Patrimoine » refondue (2026) | Navigation de la classe d'actifs vers les sous-catégories puis les lignes | ⬜ |
| Dashboard personnalisable | Choix et ordre des blocs affichés | ⬜ |
| Bascule € / % des plus-values | Ajoutée sur mobile en janvier 2026 | ⬜ |
| Mode discret | Masquer les montants (partage d'écran) | ⬜ |

### 1.2 Portefeuille et investissements

| Fonction Finary | Détail | État ici |
|---|---|---|
| Comptes par enveloppe | PEA, CTO, assurance-vie, PER, PEE, livrets, comptes courants | 🟡 pas de PER, PERCO, compte courant, livrets autres que le A |
| **Vue consolidée par actif** (juin 2026) | Un ETF détenu dans trois enveloppes apparaît comme une seule ligne, avec le détail par compte | ⬜ |
| PRU et plus-value latente | Écart entre prix de revient unitaire et cours | ✅ |
| Performance réelle (TRI, CAGR, apports vs gains) | Annoncée par Finary pour 2026, réclamée sur le forum | ⬜ (spec 001 l'avait reportée) |
| Fiche actif | Cours, graphique, ISIN, frais, répartition, positions détenues | 🟡 |
| Cours en temps réel / différé | Actions, ETF, fonds, crypto | ✅ optionnel, avec consentement |

### 1.3 Analyses (« Insights »)

| Fonction Finary | Détail | État ici |
|---|---|---|
| **Scanner de frais** | Frais de gestion d'enveloppe, frais courants des fonds et ETF, frais d'entrée et de transaction ; coût projeté sur 30 ans | ⬜ |
| **Dividendes** | Projection annuelle, calendrier des prochains versements, historique tiré des opérations | 🟡 opérations saisies, sans écran dédié |
| **Score de diversification** | Note calculée sur l'allocation réelle, avec des pistes d'amélioration | ⬜ (pistes : 🚫 si elles tournent au conseil) |
| Répartition **géographique et sectorielle** | Pays, régions, secteurs, segments sur tout le patrimoine | ⬜ |
| Exposition aux devises | Part du patrimoine par devise | ⬜ |

### 1.4 Budget et flux

| Fonction Finary | Détail | État ici |
|---|---|---|
| Catégorisation des transactions | Catégories et sous-catégories, recatégorisation à la main | ⬜ |
| Règles automatiques | Une règle par marchand ou mot-clé, appliquée au passé et au futur | ⬜ |
| **Diagramme de Sankey** revenus → dépenses | Avec sous-catégories depuis janvier 2026 ; illisible au-delà d'une vingtaine de catégories selon le forum | ⬜ |
| Cash-flow mensuel et taux d'épargne | Revenus − dépenses par mois | ⬜ |
| **Scanner d'abonnements** (avril 2026) | Dépenses récurrentes détectées sur 6 mois, calendrier des prélèvements | ⬜ |
| Limite connue | Une transaction ne peut pas être répartie sur plusieurs catégories | à faire mieux ici |

### 1.5 Immobilier, dettes et autres actifs

| Fonction Finary | Détail | État ici |
|---|---|---|
| Biens immobiliers | Estimation automatique (partenaire PriceHubble) affinée par surface, état, extérieur ; loyers | ⬜ (estimation auto : 🚫 sauf service optionnel) |
| SCPI | Valeur au prix de retrait, distributions | ✅ |
| **Crédits et dettes** | Capital restant dû tiré du tableau d'amortissement, déduit du net | ⬜ |
| Crypto | Plateformes par API, adresses publiques (45 blockchains), positions DeFi à la main | ⬜ |
| Actifs « alternatifs » | Art, métaux précieux, private equity, montres, véhicules : saisie manuelle | ⬜ |
| Liquidités et comptes courants | Synchronisés chez Finary | ⬜ |

### 1.6 Objectifs et projections

| Fonction Finary | Détail | État ici |
|---|---|---|
| **Goals** | Montant cible, date, comptes rattachés ; calcule le rendement annuel nécessaire au rythme d'épargne actuel ; statut « en avance », « dans les temps », « difficile », « atteint » | ⬜ |
| Simulateur de projection | Patrimoine à 10, 20 ou 30 ans selon des scénarios | ⬜ |
| Simulateur retraite (v2 annoncée) | Feuille de route 2026, non confirmée | ⬜ |

### 1.7 Famille, structures, rapports

| Fonction Finary | Détail | État ici |
|---|---|---|
| **Mode famille** | Membres, détention partagée ou en pourcentage, vue par membre ou consolidée | ⬜ (la discovery l'exclut pour l'instant) |
| Holdings et sociétés (offre Pro) | Entités, détention de parts, comptes professionnels | ⬜ |
| **Rapport mensuel** | Synthèse envoyée chaque mois | ⬜ |
| Déclaration de patrimoine | Relevé exportable à une date (utile pour l'IFI) | ⬜ |
| Export des données | | ✅ export complet et restauration |

### 1.8 Réglages, sécurité, divers

| Fonction Finary | Détail | État ici |
|---|---|---|
| Agrégation bancaire automatique (20 000+ établissements, lecture seule) | Via un agrégateur agréé | 🚫 (hors périmètre de la discovery) ; à la place, import OFX/QIF et importeurs par courtier |
| Double authentification | | ⬜ |
| Mode sombre | | ⬜ à vérifier dans `theme.css` |
| Notifications et alertes | Variation, versement de dividende, compte désynchronisé | ⬜ |
| Accès pour un assistant IA (serveur MCP) | Finary propose un MCP pour Claude, ChatGPT, etc. | ⬜ (local, en lecture seule, sur activation) |
| Investir via Finary (Finary Life, crypto MiCA) | Produits financiers maison | 🚫 exécution d'ordres hors périmètre |
| Communauté, forum | | 🚫 |

## 2. Écrans à créer ou à étendre

Écrans existants : Tableau de bord, Comptes, Détail d'un compte, Actifs, Importer, Réglages, Connexion.

| # | Écran | Nouveau / extension | Contenu principal |
|---|---|---|---|
| E1 | Tableau de bord | extension | Brut / net / dettes ; périodes 1 sem. et 3 mois ; blocs déplaçables ; mode discret ; raccourcis vers dividendes, objectifs, budget |
| E2 | Patrimoine (explorateur) | nouveau | Arborescence classe → sous-catégorie → ligne ; bascule par classe, enveloppe, établissement, devise |
| E3 | Portefeuille consolidé | nouveau | Une ligne par actif, toutes enveloppes confondues ; dépliage par compte ; PRU, plus-value €/%, poids |
| E4 | Fiche actif | extension de « Actifs » | Graphique de cours, frais courants, pays et secteurs, dividendes, positions détenues |
| E5 | Performance | nouveau | Apports nets vs gains, TRI (rendement pondéré par les flux), CAGR, par compte et global, comparaison facultative à un indice |
| E6 | Dividendes et revenus | nouveau | Calendrier mensuel, projection sur 12 mois, historique, rendement sur PRU ; intérêts et distributions SCPI inclus |
| E7 | Frais | nouveau | Frais par enveloppe et par ligne, total annuel en €, projection du manque à gagner sur 10/20/30 ans |
| E8 | Diversification | nouveau | Score expliqué, cartes par pays, secteurs, devises, concentration sur les 10 premières lignes |
| E9 | Budget : transactions | nouveau | Liste filtrable, catégorie et sous-catégorie, ventilation d'une transaction sur plusieurs catégories |
| E10 | Budget : règles | nouveau | Règles par libellé, mot-clé, montant ; aperçu des transactions touchées avant d'appliquer |
| E11 | Budget : analyse | nouveau | Sankey revenus → dépenses (repli sur les petites catégories pour rester lisible), cash-flow mensuel, taux d'épargne |
| E12 | Abonnements | nouveau | Récurrences détectées, montant annuel, calendrier des prélèvements, confirmer ou ignorer |
| E13 | Immobilier | nouveau | Fiche bien (prix d'achat, frais, travaux, valeur estimée saisie, loyers, charges), rendement locatif |
| E14 | Dettes | nouveau | Crédit avec tableau d'amortissement calculé, capital restant dû, lien vers le bien financé |
| E15 | Crypto | nouveau | Comptes et portefeuilles, saisie manuelle ou import CSV de plateforme ; adresse publique en option avec consentement |
| E16 | Autres actifs | nouveau | Or, art, véhicules, private equity : valeur saisie et historique |
| E17 | Objectifs | nouveau | Liste avec statut ; création (cible, date, comptes) ; rendement nécessaire ; trajectoire |
| E18 | Simulateur | nouveau | Projection 10/20/30 ans, épargne mensuelle, rendement et inflation, trois scénarios |
| E19 | Rapports | nouveau | Rapport mensuel généré en local (PDF ou HTML) ; relevé de patrimoine à une date (IFI) |
| E20 | Import | extension | OFX/QIF, modèles prêts par courtier, import de transactions bancaires pour le budget |
| E21 | Réglages | extension | 2FA (TOTP), mode sombre, catégories, membres (plus tard), alertes, accès MCP local |

## 3. Découpage proposé en lots

Les priorités tiennent compte de la discovery (`docs/ux-discovery/2026-10-24-finance-discovery.md`) :
utilisateur unique, données locales, pas de connecteur bancaire.

1. **Lot 002 · Dettes et patrimoine net réel** (E1, E14, E13 en version simple). Lève la mention
   « hors dettes », qui est la plus grosse différence de lecture avec Finary.
2. **Lot 003 · Performance et portefeuille consolidé** (E3, E5, E4). Finary affiche surtout du latent,
   ce qui est la critique la plus fréquente sur son forum : un vrai TRI apports / gains serait un point fort ici.
3. **Lot 004 · Revenus et frais** (E6, E7). Les données sont déjà là (dividendes, frais saisis) ; il
   manque les frais courants par fonds, saisis à la main ou récupérés avec les cours.
4. **Lot 005 · Diversification** (E8, E2). Demande des données pays et secteur par actif : saisie ou
   source optionnelle, comme pour les cours.
5. **Lot 006 · Budget** (E9 à E12, E20). Le plus gros lot. Sans agrégation, il repose sur l'import
   OFX/CSV des relevés bancaires.
6. **Lot 007 · Objectifs et simulateur** (E17, E18).
7. **Lot 008 · Rapports et sécurité** (E19, E21 : 2FA, mode sombre, mode discret).
8. **Plus tard** : crypto et autres actifs (E15, E16), mode famille, holdings, accès MCP local, alertes.

## Sources

- [Finary : produits et offres](https://finary.com/en/pricing), [Finary Plus](https://finary.com/en/finary-plus),
  [Finary Lite](https://finary.com/en/finary-lite), [Finary Pro](https://finary.com/en/finary-pro)
- [Budget](https://finary.com/en/budget), [Scanner de dépenses récurrentes](https://finary.com/en/budget/expenses-scanner),
  [Suivi de patrimoine](https://finary.com/en/wealth-tracking)
- Notes de version : [janvier 2026](https://finary.com/en/product-updates/product-updates-january-2026),
  [portefeuille repensé](https://finary.com/fr/actualites-produit/un-portefeuille-repense-et-un-cap-pour-avancer),
  [Goals](https://finary.com/en/product-updates/goals-finary), [mars 2024](https://finary.com/fr/actualites-produit/mars-2024)
- Centre d'aide : [guide de prise en main](https://help.finary.com/fr/articles/15692392-guide-de-prise-en-main-de-finary),
  [membres de la famille](https://help.finary.com/en/articles/6521889-managing-family-members-and-their-assets),
  [créer sa holding](https://help.finary.com/fr/articles/8830249-creer-ma-holding-sur-finary)
- Forum : [nouvelle interface](https://community.finary.com/t/nouvelle-interface/38187),
  [priorités T1 2026](https://community.finary.com/t/ma-priorite-pour-le-1er-trimestre-2026-mounir-de-finary/33309),
  [apport vs performance](https://community.finary.com/t/fonctionnalite-differencier-apport-et-performance/2454?page=5),
  [Sankey et sous-catégories](https://community.finary.com/t/budget-souci-daffichage-sur-le-diagramme-de-sankey-avec-sous-categories/34309)
- Tests tiers : [Avenue des investisseurs](https://avenuedesinvestisseurs.fr/avis-finary-agregateur-suivi-patrimoine/),
  [Signal Alpha](https://signal-alpha.fr/avis-finary/), [Epargnoo](https://epargnoo.com/epargnews/articles/avis-finary),
  [Dealfluence](https://www.dealfluence.fr/tech/finary), [Parrain du web, feuille de route](https://parrainduweb.fr/blog/finary-roadmap)
