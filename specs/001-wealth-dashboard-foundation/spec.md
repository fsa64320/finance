# Feature Specification: Socle de suivi de patrimoine et tableau de bord

**Feature Branch**: `001-wealth-dashboard-foundation`

**Created**: 2026-10-24

**Status**: Draft

**Input**: User description: "Premier lot du produit Finance (application web auto-hébergée de suivi de patrimoine): socle, modèle de données, import CSV générique et tableau de bord de patrimoine net. Enveloppes: PEE, PEA, CTO, assurance-vie, Livret A. Classes d'actifs: SCPI, actions/ETF, fonds d'investissement (dont FCPE et fonds en euros). Saisie manuelle des comptes, instruments et transactions; import CSV avec mapping de colonnes et dédoublonnage; cours et valeurs liquidatives; tableau de bord avec patrimoine net, courbe d'évolution et répartition par classe d'actifs; liste des comptes avec valeur; interface inspirée de l'organisation de Finary mais avec identité visuelle propre."

## Clarifications

### Session 2026-10-24

- Q: Si l'utilisateur oublie son mot de passe, que doit-il se passer avec ses données ? → A: Les données sont illisibles sans le mot de passe, aucune récupération n'est possible, et l'application rappelle d'exporter régulièrement.
- Q: Comment enregistrer un déplacement d'argent entre deux comptes de l'utilisateur ? → A: Un type d'opération « virement entre comptes » relie un compte source et un compte destination ; il est neutre pour le patrimoine net et pour le rendement, et un import peut produire les deux côtés.
- Q: Comment corriger une opération saisie par erreur ? → A: L'utilisateur modifie ou annule l'opération directement ; le système conserve l'ancienne version dans un historique des modifications, et les écrans courants montrent la version à jour.
- Q: Que faire d'une ligne CSV qui porte sur un actif inconnu ? → A: L'aperçu liste les actifs inconnus avec les informations lues dans le fichier ; l'utilisateur peut les créer, les rattacher à un actif existant ou ignorer les lignes concernées, et rien n'est créé avant sa validation.
- Q: Le patrimoine net déduit-il des dettes dans ce lot ? → A: Non. Le libellé « patrimoine net » est conservé avec la mention « hors dettes » ; la gestion des dettes est reportée à un lot ultérieur.
- Q: Quelles règles pour le mot de passe et les sessions ? → A: 12 caractères minimum (128 maximum) et absent de la liste des mots de passe courants ; après 5 échecs consécutifs le délai avant un nouvel essai double à chaque échec jusqu'à 15 minutes ; la session expire après 30 minutes d'inactivité et au plus 12 heures après la connexion ; le cookie est `Secure` en HTTPS.
- Q: La récupération automatique des prix est-elle active par défaut ? → A: Non. Elle reste désactivée jusqu'à un choix explicite de l'utilisateur à la première utilisation, peut être coupée à tout moment, et la liste des services contactés et des données envoyées est affichée (constitution v1.1.0, principe I).
- Q: Peut-on changer le mot de passe ? → A: Oui, depuis les réglages, en saisissant l'ancien mot de passe ; les données sont rechiffrées (FR-033).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Enregistrer ses comptes et ses positions (Priority: P1)

Une personne qui suit son propre patrimoine déclare ses enveloppes (PEE, PEA, compte-titres, assurance-vie, Livret A), y rattache les actifs qu'elle détient (actions, ETF, fonds, SCPI, fonds en euros) et saisit à la main l'historique de ses opérations : versements, achats, ventes, dividendes, distributions, intérêts, frais. Elle obtient la valeur de chaque compte à partir de ce qu'elle a saisi.

**Why this priority**: sans données, rien d'autre n'a de valeur. Ce parcours, à lui seul, fournit un suivi de patrimoine utilisable, sans import ni cours automatiques.

**Independent Test**: créer un compte de chaque type, y saisir quelques opérations, puis vérifier que la valeur affichée de chaque compte correspond à un calcul fait à la main.

**Acceptance Scenarios**:

1. **Given** aucune donnée, **When** la personne crée un PEA nommé « PEA Courtier A » et y saisit un versement de 1 000 € puis l'achat de 10 parts d'un ETF à 90 € avec 1,99 € de frais, **Then** le compte affiche 10 parts, un prix de revient de 90,199 € par part et 98,01 € de liquidités.
2. **Given** un compte d'assurance-vie, **When** la personne y ajoute un fonds en euros et déclare un solde de 5 000 € à une date donnée, **Then** la valeur du fonds en euros est ce solde, augmentée des flux saisis depuis cette date.
3. **Given** un Livret A avec 3 000 € de solde, **When** la personne enregistre un retrait de 500 €, **Then** le solde passe à 2 500 € et l'opération apparaît dans l'historique du compte.
4. **Given** un PEA avec 2 000 € de liquidités et un Livret A de 3 000 €, **When** la personne enregistre un virement de 500 € du PEA vers le Livret A, **Then** le PEA affiche 1 500 €, le Livret A 3 500 € et le patrimoine net total reste inchangé.
5. **Given** une opération saisie par erreur, **When** la personne la modifie ou l'annule, **Then** la liste montre la version à jour, la valeur du compte reflète la correction, et l'historique des modifications conserve la version d'origine.

---

### User Story 2 - Consulter son patrimoine sur un tableau de bord (Priority: P1)

La personne ouvre l'application et voit d'un coup d'œil son patrimoine net, la courbe de son évolution dans le temps, sa répartition par classe d'actifs et la liste de ses comptes avec la valeur de chacun. Elle peut ouvrir un compte pour voir ses positions et son historique. La page d'accueil est organisée comme celle d'un outil de suivi de patrimoine grand public : synthèse en haut, courbe d'évolution, répartition, puis comptes. L'identité visuelle (nom, logo, couleurs, icônes, textes) est propre au projet.

**Why this priority**: c'est la valeur visible du produit et la raison d'être d'un suivi de patrimoine.

**Independent Test**: avec les données du scénario 1, ouvrir le tableau de bord et vérifier que le patrimoine net égale la somme des valeurs des comptes, que la courbe passe par les bonnes valeurs aux dates saisies et que les parts de la répartition totalisent 100 %.

**Acceptance Scenarios**:

1. **Given** plusieurs comptes valorisés, **When** la personne ouvre le tableau de bord, **Then** le patrimoine net est la somme exacte des valeurs de tous les comptes, dans la devise de référence.
2. **Given** un historique d'opérations sur plusieurs années, **When** la personne choisit une période (1 mois, 1 an, depuis le début), **Then** la courbe affiche la valeur du patrimoine à chaque date de la période, recalculée à partir des opérations et des prix connus à cette date.
3. **Given** des actifs de classes différentes (actions/ETF, fonds, SCPI, fonds en euros, liquidités), **When** la personne consulte la répartition, **Then** chaque classe affiche sa valeur et son poids, et la somme des poids est de 100 %.
4. **Given** la liste des comptes, **When** la personne ouvre un compte, **Then** elle voit ses positions, leur valeur, leur prix de revient et l'historique de ses opérations.
5. **Given** une page consultée sur un écran d'ordinateur ou de téléphone, **When** elle s'affiche, **Then** tout le contenu reste lisible sans défilement horizontal.

---

### User Story 3 - Importer ses opérations depuis un fichier CSV (Priority: P2)

La personne dépose un fichier CSV exporté par son courtier ou son établissement. Elle indique à quelle donnée correspond chaque colonne (date, libellé, quantité, montant, etc.), vérifie un aperçu, puis valide. Les opérations sont ajoutées à l'historique ; celles qui existent déjà sont ignorées. Elle peut enregistrer ce paramétrage pour le réutiliser au prochain fichier du même établissement.

**Why this priority**: la saisie manuelle est fastidieuse sur un long historique. L'import rend l'outil praticable, mais le produit reste utilisable sans lui.

**Independent Test**: importer un fichier d'exemple de 50 lignes, vérifier que les 50 opérations apparaissent, puis réimporter le même fichier et vérifier qu'aucune opération n'est ajoutée.

**Acceptance Scenarios**:

1. **Given** un fichier CSV valide, **When** la personne associe chaque colonne à une donnée et valide l'aperçu, **Then** toutes les lignes valides deviennent des opérations du compte choisi.
2. **Given** un fichier déjà importé, **When** la personne l'importe une seconde fois, **Then** aucune opération en double n'est créée et un résumé indique que les lignes existaient déjà.
3. **Given** un fichier contenant des lignes invalides (date illisible, montant manquant), **When** la personne lance l'import, **Then** les lignes valides sont importées si elle le confirme, les lignes invalides sont listées avec la cause, et rien n'est modifié tant qu'elle n'a pas confirmé.
4. **Given** un fichier avec séparateur point-virgule, virgule décimale et dates au format jour/mois/année, **When** la personne l'importe, **Then** les montants et dates sont interprétés correctement.
5. **Given** un fichier contenant des lignes sur un actif que l'application ne connaît pas, **When** l'aperçu s'affiche, **Then** cet actif est listé avec les informations du fichier et la personne choisit de le créer, de le rattacher à un actif existant ou d'ignorer ses lignes, sans qu'aucun actif soit créé avant la validation.
6. **Given** un paramétrage de colonnes enregistré, **When** la personne importe un nouveau fichier du même établissement, **Then** le paramétrage est proposé automatiquement.

---

### User Story 4 - Valoriser les actifs avec des cours et des valeurs liquidatives (Priority: P2)

Pour les actions, ETF et fonds, la personne obtient des cours et valeurs liquidatives à jour pour valoriser ses positions, sans les saisir elle-même. Pour les actifs sans cours public exploitable (SCPI, certains fonds, FCPE), elle saisit manuellement les prix aux dates de son choix : prix de retrait, prix de souscription, valeur liquidative.

**Why this priority**: la valeur de l'historique et des positions dépend des prix. Le produit fonctionne avec des prix saisis à la main, d'où la priorité P2.

**Independent Test**: associer un ETF à son code ISIN, récupérer ses cours, puis vérifier que la valeur de la position égale la quantité multipliée par le dernier cours connu.

**Acceptance Scenarios**:

1. **Given** un ETF identifié par son code ISIN, **When** l'application met à jour les cours, **Then** la valeur de la position utilise le dernier cours disponible, avec sa date affichée.
2. **Given** une source de cours indisponible, **When** la mise à jour échoue, **Then** l'application reste utilisable avec les derniers prix connus et signale que les prix ne sont pas à jour.
3. **Given** une SCPI, **When** la personne saisit un prix de souscription et un prix de retrait, **Then** le prix de revient s'appuie sur le prix de souscription (frais d'entrée inclus), la valorisation sur le prix de retrait, et l'écart initial est visible.
4. **Given** un actif sans prix pour une date, **When** le patrimoine est calculé à cette date, **Then** le dernier prix connu antérieur est utilisé et la valeur est signalée comme estimée.
5. **Given** un actif coté dans une autre devise que l'euro, **When** il est valorisé, **Then** sa valeur est convertie dans la devise de référence avec le taux de change de la date de valorisation.
6. **Given** une première utilisation, **When** la personne atteint la configuration des prix, **Then** la récupération automatique est désactivée, la liste des services contactés (BCE pour les taux, Yahoo Finance pour les cours, OpenFIGI pour la recherche de ticker) et les données envoyées à chacun sont affichées, et rien ne sort tant qu'elle n'a pas activé la récupération.

---

### User Story 5 - Installer l'application et protéger l'accès (Priority: P3)

Une personne un peu technique installe l'application sur sa propre machine ou son propre serveur avec une seule commande, crée son accès protégé par un mot de passe, et retrouve ses données à chaque démarrage. Elle peut exporter l'ensemble de ses données et en faire une sauvegarde.

**Why this priority**: indispensable à l'adoption et à la souveraineté des données, mais le reste du produit peut être validé avant que l'installation soit polie.

**Independent Test**: sur une machine vierge, installer l'application avec la procédure du dépôt, créer l'accès, saisir une donnée, redémarrer et vérifier que la donnée est toujours là et qu'un accès sans mot de passe est refusé.

**Acceptance Scenarios**:

1. **Given** une machine disposant des prérequis documentés, **When** la personne suit la procédure d'installation, **Then** l'application est accessible depuis un navigateur sans autre configuration obligatoire.
2. **Given** l'application installée pour la première fois, **When** la personne l'ouvre, **Then** elle est invitée à créer son mot de passe avant tout accès aux données.
3. **Given** une session non authentifiée, **When** quelqu'un tente d'ouvrir une page de données, **Then** l'accès est refusé.
4. **Given** le choix du mot de passe, **When** la personne le crée, **Then** l'application lui indique qu'un oubli rend les données irrécupérables et l'invite à exporter ses données.
5. **Given** des données saisies, **When** la personne demande un export, **Then** elle obtient un fichier contenant l'intégralité de ses comptes, instruments, opérations et prix, réutilisable pour restaurer ses données.
6. **Given** le choix du mot de passe, **When** la personne en saisit un de moins de 12 caractères ou présent dans la liste des mots de passe courants, **Then** il est refusé avec la règle à respecter.
7. **Given** une session ouverte, **When** 30 minutes passent sans activité, **Then** la session expire et le mot de passe est redemandé.
8. **Given** les réglages, **When** la personne saisit l'ancien mot de passe puis un nouveau valide, **Then** les données restent lisibles avec le nouveau mot de passe et l'ancien est refusé.

---

### Edge Cases

- Un versement ou une vente laisse un compte avec une quantité ou des liquidités négatives : l'application avertit sans bloquer la saisie, puisque l'historique peut être incomplet.
- Un compte est clôturé : il disparaît des totaux courants mais reste dans l'historique et sur la courbe passée.
- Deux opérations réelles et identiques le même jour (deux achats identiques) : l'import ne les confond pas avec des doublons lorsque le fichier fournit un identifiant distinct ou qu'elles apparaissent deux fois dans le même fichier.
- Un fichier avec encodage, séparateur, format de date ou de nombre atypique : l'aperçu permet de corriger ces paramètres avant validation.
- Un fichier très volumineux ou vide : l'application affiche un message clair et ne modifie rien.
- Une opération en devise étrangère sans taux de change connu à sa date : la valeur est signalée comme non convertible plutôt que fausse.
- Le fonds en euros sans solde déclaré : la valeur affichée est nulle avec un message qui invite à déclarer un solde.
- Une SCPI sans prix saisi : la valeur est estimée au prix de revient et signalée comme telle.
- Un PEE avec des sommes bloquées : la date de déblocage est affichée et les montants indisponibles sont distingués des disponibles.
- Cinq échecs de connexion consécutifs : les essais suivants sont retardés (doublement jusqu'à 15 minutes) et l'application indique le délai restant.
- Mot de passe oublié : les données sont irrécupérables ; seule la restauration d'un export antérieur permet de repartir.
- Un patrimoine sans aucune donnée : le tableau de bord présente un état vide qui guide vers la création d'un premier compte.

## Requirements *(mandatory)*

### Functional Requirements

**Comptes et opérations**

- **FR-001**: Le système MUST permettre de créer, modifier et clôturer des comptes des cinq types suivants : PEE, PEA, compte-titres ordinaire, assurance-vie, Livret A.
- **FR-002**: Le système MUST permettre de définir des actifs de types actions, ETF, fonds d'investissement (dont FCPE), SCPI, fonds en euros et liquidités, avec nom, devise et, quand il existe, code ISIN.
- **FR-003**: Le système MUST permettre de saisir des opérations de type versement, retrait, achat, vente, dividende, distribution, intérêt, frais et abondement, avec date, quantité, prix, frais et devise. Il MUST aussi permettre de saisir un virement entre deux comptes de l'utilisateur, relié à un compte source et à un compte destination, distinct d'un versement ou d'un retrait extérieur : le virement ne modifie pas le patrimoine net total et n'est pas compté comme un apport ou une sortie d'argent.
- **FR-004**: Le système MUST permettre de modifier ou d'annuler une opération directement depuis l'interface. Il MUST conserver chaque version antérieure dans un historique des modifications consultable, sans jamais effacer l'information d'origine ; les écrans courants et tous les calculs utilisent la version à jour.
- **FR-005**: Le système MUST calculer, pour chaque compte, la quantité détenue de chaque actif, les liquidités, la valeur et le prix de revient unitaire moyen frais inclus.
- **FR-006**: Le système MUST permettre de déclarer un solde à une date pour les actifs sans cours (fonds en euros, Livret A) et utiliser ce solde, augmenté des flux suivants, comme valeur.

**Particularités par type de compte**

- **FR-007**: Pour un PEE, le système MUST distinguer l'abondement des versements personnels, l'inclure dans le patrimoine, l'exclure du rendement, et afficher la date de déblocage des sommes bloquées.
- **FR-008**: Pour un PEA, le système MUST afficher le cumul des versements et le comparer à un plafond paramétrable.
- **FR-009**: Pour un Livret A, le système MUST afficher le plafond du livret, conserver une table des taux datés modifiable, et estimer les intérêts à partir de cette table tant que les intérêts réels ne sont pas saisis ou importés.
- **FR-010**: Pour une SCPI, le système MUST gérer séparément le prix de souscription et le prix de retrait, utiliser le premier pour le prix de revient et le second pour la valorisation, et enregistrer les distributions périodiques.

**Prix et devises**

- **FR-011**: Le système MUST permettre de saisir manuellement un prix ou une valeur liquidative pour n'importe quel actif à n'importe quelle date.
- **FR-012**: Lorsque l'utilisateur a activé la récupération automatique (FR-029), le système MUST récupérer automatiquement les cours des actions et ETF et les valeurs liquidatives des fonds identifiés par un code ISIN, quand une source publique les fournit, et conserver ces prix localement.
- **FR-013**: Le système MUST rester pleinement utilisable lorsque la récupération de prix échoue, en utilisant les derniers prix connus et en signalant leur ancienneté.
- **FR-014**: Le système MUST valoriser en tenant compte de la devise d'origine de chaque montant et convertir dans la devise de référence avec le taux de la date de valorisation.

**Import CSV**

- **FR-015**: Le système MUST permettre d'importer un fichier CSV dans un compte choisi, avec réglage du séparateur, de l'encodage, du format des dates et du format des nombres.
- **FR-016**: Le système MUST permettre d'associer chaque colonne du fichier à une donnée d'opération et afficher un aperçu avant toute écriture. Lorsque des lignes portent sur des actifs inconnus, l'aperçu MUST les lister avec les informations lues dans le fichier (nom, code ISIN) et permettre, pour chacun, de le créer, de le rattacher à un actif existant ou d'ignorer les lignes concernées ; aucun actif n'est créé avant la validation.
- **FR-017**: Le système MUST rejeter les lignes invalides en indiquant la cause, et ne rien enregistrer sans confirmation explicite.
- **FR-018**: Le système MUST rendre l'import idempotent : réimporter un même fichier ne crée aucune opération en double, et un résumé indique le nombre de lignes ajoutées, ignorées et rejetées.
- **FR-019**: Le système MUST permettre d'enregistrer et de réutiliser un paramétrage d'import par établissement.
- **FR-020**: Chaque opération importée MUST garder la trace de son fichier d'origine.

**Tableau de bord**

- **FR-021**: Le système MUST afficher le patrimoine net total, somme des valeurs de tous les comptes ouverts, dans la devise de référence, accompagné de la mention « hors dettes » : aucune dette n'est déduite dans ce lot.
- **FR-022**: Le système MUST afficher une courbe de l'évolution du patrimoine sur des périodes sélectionnables, calculée à partir de l'historique d'opérations et des prix de chaque date.
- **FR-023**: Le système MUST afficher la répartition du patrimoine par classe d'actifs (actions/ETF, fonds, SCPI, fonds en euros, liquidités) avec valeur et poids, la somme des poids étant 100 %.
- **FR-024**: Le système MUST afficher la liste des comptes avec leur type, leur établissement et leur valeur, et permettre d'ouvrir le détail d'un compte (positions, prix de revient, historique d'opérations).
- **FR-025**: Le système MUST signaler clairement toute valeur estimée ou périmée (prix ancien, solde non déclaré, taux manquant).
- **FR-026**: L'interface MUST être utilisable sur ordinateur et sur téléphone, sans défilement horizontal de la page.
- **FR-027**: L'interface MUST suivre l'organisation générale d'un outil de suivi de patrimoine grand public (synthèse, évolution, répartition, comptes) avec une identité visuelle propre au projet et sans élément de marque d'un tiers.

**Socle**

- **FR-028**: Le système MUST exiger un mot de passe défini à la première utilisation avant tout accès aux données. Les données MUST être illisibles sans ce mot de passe ; il n'existe aucun mécanisme de récupération en cas d'oubli, et l'application MUST l'indiquer à la création du mot de passe et rappeler régulièrement d'exporter les données. Le mot de passe MUST faire au moins 12 caractères (128 au maximum) et ne pas figurer dans la liste des mots de passe courants livrée avec l'application. Après 5 échecs consécutifs, le délai avant un nouvel essai est de 15 secondes puis double à chaque échec, jusqu'à 15 minutes. La session MUST expirer après 30 minutes d'inactivité et au plus 12 heures après la connexion ; le cookie de session est marqué `Secure` dès que l'accès se fait en HTTPS.
- **FR-029**: Le système MUST conserver toutes les données localement. Seules les demandes de cours, de taux de change et de recherche de ticker à partir d'un code ISIN sortent ; elles ne contiennent que des identifiants d'actifs et des devises, jamais de quantités, de montants, de noms de comptes ni de dates d'opérations. Comme ces identifiants révèlent ce qui est détenu, la récupération automatique MUST être désactivée tant que l'utilisateur ne l'a pas activée par un choix explicite à la première utilisation, MUST pouvoir être coupée à tout moment, et l'application MUST afficher la liste des services contactés et ce que chacun reçoit.
- **FR-030**: Le système MUST permettre d'exporter l'intégralité des données dans un format ouvert et de les restaurer.
- **FR-031**: Tous les montants et quantités MUST être calculés avec une précision décimale exacte ; les arrondis ne s'appliquent qu'à l'affichage.
- **FR-032**: Le système MUST afficher un avertissement indiquant que les valeurs et analyses sont indicatives et ne constituent pas un conseil en investissement.
- **FR-033**: Le système MUST permettre de changer le mot de passe depuis les réglages en saisissant l'ancien ; les données sont alors rechiffrées avec le nouveau, qui doit respecter les règles de FR-028. L'ancien mot de passe cesse immédiatement de fonctionner.

### Key Entities

- **Compte** : une enveloppe détenue par l'utilisateur, avec son type, son établissement, sa devise, sa date d'ouverture, éventuellement sa date de clôture et des paramètres propres à son type (plafond du PEA, durée de blocage du PEE).
- **Actif** : ce qui peut être détenu (action, ETF, fonds, FCPE, SCPI, fonds en euros, liquidités), avec nom, devise, code ISIN éventuel et mode de valorisation.
- **Opération** : un événement daté sur un compte (versement, achat, vente, dividende, distribution, intérêt, frais, abondement, ou virement entre deux comptes de l'utilisateur), rattaché à un actif quand il y en a un, avec quantité, prix, frais, devise et provenance (saisie ou fichier importé). L'historique des opérations est la source de vérité.
- **Prix** : une valeur d'un actif à une date, avec sa provenance (source automatique ou saisie manuelle).
- **Solde déclaré** : un solde saisi à une date pour un actif sans cours, utilisé comme point de contrôle et de valorisation.
- **Taux** : un taux réglementaire daté (Livret A) ou un taux de change daté.
- **Import** : le suivi d'un fichier importé (nom, empreinte, date, résultat), qui permet de rejouer sans doublon.
- **Paramétrage d'import** : l'association mémorisée entre les colonnes d'un fichier et les données d'opération pour un établissement.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Une personne qui connaît ses données crée un compte et y saisit une première opération en moins de 2 minutes.
- **SC-002**: Sur un jeu de scénarios de référence couvrant les cinq types de compte, la valeur de chaque compte et le patrimoine net affichés correspondent au centime près à un calcul indépendant.
- **SC-003**: Un fichier de 500 lignes est importé en moins de 1 minute, et sa réimportation ne crée aucune opération en double (0 doublon sur 500 lignes).
- **SC-004**: Le tableau de bord s'affiche en moins de 3 secondes avec 10 ans d'historique et 5 000 opérations.
- **SC-005**: La personne qui découvre le tableau de bord trouve son patrimoine net, la répartition par classe d'actifs et la valeur d'un compte donné en moins de 30 secondes, sans aide.
- **SC-006**: Une personne technique installe l'application et accède à son tableau de bord vide en moins de 10 minutes en suivant la documentation.
- **SC-007**: Lorsque la source de prix est indisponible, 100 % des pages restent consultables et toute valeur issue d'un prix ancien est signalée.
- **SC-008**: Aucune donnée personnelle (comptes, montants, opérations) n'est transmise à un tiers pendant l'usage normal.
- **SC-009**: Un export suivi d'une restauration redonne des valeurs identiques pour tous les comptes et pour le patrimoine net.

## Assumptions

- Une seule personne utilise une instance de l'application (pas de multi-utilisateur) ; le mot de passe protège l'instance.
- La devise de référence est l'euro par défaut et les comptes concernés sont en euros pour la majorité des cas ; les autres devises sont gérées via les taux de change.
- Les données d'entrée sont saisies à la main ou importées par fichier CSV ; l'application ne se connecte jamais aux sites des établissements et n'enregistre aucun identifiant bancaire.
- La gestion des dettes (crédit immobilier, prêts) est hors périmètre de ce lot et arrivera plus tard.
- Les formats OFX, les importeurs dédiés à un établissement précis et les connecteurs automatiques sont hors périmètre de ce lot.
- La performance (rendement pondéré par les flux), la diversification par secteur ou zone, les dividendes en calendrier, le budget, les projections et le rapport fiscal sont hors périmètre de ce lot.
- Les plafonds (PEA, Livret A) et les taux réglementaires sont des valeurs paramétrables initialisées à des valeurs courantes, que l'utilisateur peut mettre à jour ; l'application ne garantit pas leur actualité.
- Les cours des actions, ETF et fonds viennent de sources publiques gratuites ; leur couverture n'est pas garantie, d'où la saisie manuelle toujours possible.
- Les intérêts du Livret A calculés par l'application sont une estimation ; les intérêts réels saisis ou importés prévalent.
- Les cas particuliers de l'assurance-vie (frais de gestion, arbitrages entre supports) sont gérés comme des opérations ordinaires saisies par l'utilisateur ; aucun calcul fiscal n'est fourni.
- L'interface est en français ; la prise en charge d'autres langues est hors périmètre de ce lot.
- Le projet suit la constitution du dépôt (données locales, journal immuable, exactitude décimale, absence de scraping, tests chiffrés).
