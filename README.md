# Finance

Application web **auto-hébergée** et **open source** de suivi de patrimoine : PEE, PEA, compte-titres,
assurance-vie, Livret A, avec actions et ETF, fonds et SCPI. Vos données restent chez vous,
**chiffrées au repos**, et rien ne sort de votre ordinateur sans que vous l'ayez décidé.

Les valeurs et analyses affichées sont indicatives et ne constituent pas un conseil en investissement.

## Ce que l'application fait

- Un tableau de bord du **patrimoine net** (hors dettes), de son évolution et de sa répartition.
- La saisie à la main des opérations, ou l'**import d'un fichier CSV** exporté par votre courtier,
  sans doublon si vous réimportez le même fichier.
- Des cours et des taux de change **récupérés seulement si vous l'activez**, ou saisis à la main
  (SCPI, fonds).
- L'estimation des intérêts du Livret A, la valorisation des SCPI au prix de retrait.
- Un **export** complet de vos données et leur **restauration**.

## Installer

### Ce qu'il vous faut

- Un ordinateur sous Windows, macOS ou Linux.
- **Docker** : sous Windows et macOS, installez [Docker Desktop](https://www.docker.com/products/docker-desktop/)
  (gratuit pour un usage personnel), lancez-le et attendez que son icône indique « Docker Desktop is
  running ». Sous Linux, installez Docker Engine et le plugin Compose.

### Étape par étape

1. **Récupérez le code.** Sur la page GitHub du projet, cliquez sur **Code**, puis **Download ZIP**,
   et décompressez l'archive où vous voulez (par exemple dans vos Documents).
2. **Ouvrez un terminal dans ce dossier.**
   - Windows : ouvrez le dossier dans l'Explorateur, tapez `cmd` dans la barre d'adresse, Entrée.
   - macOS : clic droit sur le dossier, **Nouveau terminal au dossier**.
   - Linux : clic droit dans le dossier, **Ouvrir dans un terminal**.
3. **Lancez l'application** en une commande :

   ```bash
   docker compose up -d --build
   ```

   La première fois, la construction prend quelques minutes (téléchargement de l'interface et des
   bibliothèques). Les fois suivantes, le démarrage est immédiat.
4. **Ouvrez <http://localhost:8000>** dans votre navigateur.
5. **Créez votre mot de passe** (12 caractères au moins). Voir l'avertissement ci-dessous.

L'application redémarre toute seule avec votre ordinateur tant que Docker tourne.

> **Aucune image toute faite n'est publiée pour l'instant** : la construction se fait donc sur votre
> machine, avec la commande ci-dessus.

### Votre mot de passe protège toutes vos données

Il sert de clé pour chiffrer la base de données. **Il n'existe aucun moyen de le récupérer** : si vous
l'oubliez, vos données sont définitivement illisibles. Choisissez-le avec soin, conservez-le dans un
gestionnaire de mots de passe, et **exportez régulièrement vos données** (voir plus bas).

Après un redémarrage de l'application (ou de l'ordinateur), l'instance est **verrouillée** : il faut
ressaisir le mot de passe. Après 5 essais ratés, un délai s'impose entre deux essais.

## Utiliser

- **Comptes** : créez vos comptes, puis saisissez les opérations (versements, achats, ventes,
  dividendes, virements entre comptes…). Une erreur se corrige : l'ancienne version reste dans
  l'historique.
- **Actifs** : ajoutez vos actions, ETF, fonds, SCPI. Pour les cours, saisissez un prix à la main ou
  activez la récupération automatique (voir *Confidentialité*).
- **Importer** : déposez un fichier CSV de votre courtier, indiquez à quelle donnée correspond chaque
  colonne, vérifiez l'aperçu, validez. Le réglage est mémorisé pour le prochain fichier du même
  établissement.
- **Réglages** : récupération automatique des cours, taux du Livret A, rappel d'export, changement
  de mot de passe, export et restauration.

## Sauvegarder et restaurer

**Exporter** : *Réglages › Exporter mes données* télécharge un fichier JSON complet. Attention : ce
fichier **n'est pas chiffré**. Toute personne qui le détient lit tout votre patrimoine : rangez-le
dans un endroit sûr (coffre chiffré, par exemple). L'application vous rappelle d'exporter à
intervalle régulier.

**Restaurer** : sur une installation **neuve** (aucun compte), *Réglages › Restaurer* accepte le
fichier d'export. La restauration est refusée si l'instance contient déjà des données, et le fichier
est vérifié en entier avant toute écriture : en cas de problème, rien n'est modifié.

Vos données vivent dans le volume Docker `finance-data` (dossier `/data` du conteneur). Pour changer
d'ordinateur, le plus simple est d'exporter puis de restaurer.

## Confidentialité

- Toutes les données restent sur votre machine.
- Les cours et les taux **ne sont jamais récupérés tant que vous ne l'avez pas activé** dans
  *Réglages*. L'écran liste alors chaque service contacté et ce qui lui est envoyé : la BCE (taux de
  change, requête sans paramètre), Yahoo Finance (le ticker de vos actifs et une période grossière),
  OpenFIGI (le code ISIN, seulement quand vous cherchez un ticker).
- Jamais de quantités, de montants, de noms de comptes ni de dates d'opération.
- L'application ne se connecte jamais aux sites de vos établissements et ne vous demande aucun
  identifiant bancaire.

## Arrêter, mettre à jour, désinstaller

```bash
docker compose stop            # arrêter (les données sont conservées)
docker compose up -d --build   # redémarrer, ou mettre à jour après avoir remplacé le code
docker compose down            # supprimer le conteneur (les données sont conservées)
docker compose down -v         # supprimer aussi les données : irréversible, exportez d'abord
```

## Accès depuis un autre appareil

Par défaut, l'application n'est joignable que depuis l'ordinateur qui l'héberge
(`127.0.0.1:8000`). Si vous l'ouvrez au réseau, faites-le derrière un **proxy inverse en HTTPS** (le
cookie de session est alors marqué `Secure`) et déclarez son adresse :

```yaml
environment:
  FINANCE_ALLOWED_ORIGINS: "https://finance.exemple.fr"
```

Pour que le cookie de session soit marqué `Secure` derrière votre proxy, indiquez à l'application
de faire confiance à son adresse (`FORWARDED_ALLOW_IPS`, variable d'uvicorn) :

```yaml
environment:
  FORWARDED_ALLOW_IPS: "172.18.0.1"   # adresse du proxy vue depuis le conteneur
```

N'exposez jamais l'application directement sur Internet sans HTTPS.

## Contribuer

Le projet suit [Spec Kit](https://github.com/github/spec-kit) : la constitution, la spécification et
le plan sont dans [`.specify/memory/constitution.md`](.specify/memory/constitution.md) et
[`specs/001-wealth-dashboard-foundation/`](specs/001-wealth-dashboard-foundation/). Voir
[CONTRIBUTING.md](CONTRIBUTING.md). Pour signaler une faille, voir [SECURITY.md](SECURITY.md).

## Licence

Ce projet est distribué sous licence [GNU Affero General Public License v3.0](LICENSE).
