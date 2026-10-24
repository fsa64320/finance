# Politique de sécurité

Finance manipule des données financières personnelles. La sécurité des données de l'utilisateur est
un principe du projet (voir `.specify/memory/constitution.md`).

## Signaler une vulnérabilité

Ne publiez pas de faille dans une issue ni dans une pull request publique.

Utilisez le signalement privé de GitHub : onglet **Security** du dépôt, puis **Report a
vulnerability**. Indiquez la version ou le commit concerné, les étapes pour reproduire et l'impact
que vous estimez.

Vous recevrez un accusé de réception dans un délai raisonnable ; le projet est maintenu
par une seule personne et n'offre aucun délai garanti.

## Ce qui est considéré comme une faille

- Contournement de l'authentification ou lecture des données sans le mot de passe.
- Fuite de données personnelles ou de montants vers un tiers (le projet n'envoie que des
  identifiants d'actifs pour récupérer des prix).
- Injection (SQL, commande, script) via un fichier importé ou un champ de saisie.
- Dépendance vulnérable exploitable dans la configuration livrée.

## Modèle de menace de référence

- L'application est installée par l'utilisateur sur sa propre machine, utilisée par une seule
  personne.
- Les données sont chiffrées au repos ; un mot de passe oublié rend les données irrécupérables,
  c'est voulu.
- Le projet ne stocke aucun identifiant d'établissement financier et ne se connecte à aucun.

## Pour les contributeurs

- Ne jamais committer de secret, de clé, de mot de passe ni de donnée financière réelle, y compris
  dans les fixtures de test.
- Les actions GitHub sont épinglées par empreinte de commit.
- Les modifications de `.github/`, `.claude/`, `Dockerfile`, de l'authentification et de la couche
  base de données demandent une relecture explicite (voir `.github/CODEOWNERS`).

## Revue de sécurité du premier lot (T132)

Réalisée sur l'application servie (backend + interface compilée) et sur l'image Docker.

**Vérifié, conforme**

- **En-têtes** (pages et API) : `Content-Security-Policy` (`default-src 'self'`, `object-src 'none'`,
  `frame-ancestors 'none'`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy: same-origin`, `Permissions-Policy`
  restrictive ; `Cache-Control: no-store` sur l'API. Aucun script ni style externe.
- **Cookie de session** : `HttpOnly`, `SameSite=Strict`, `Secure` dès que l'application voit une
  connexion HTTPS.
- **Contrôle de l'`Origin`** sur les requêtes qui modifient des données : une origine étrangère reçoit
  `403`.
- **Taille des corps** : `413` au-delà de 1 Mio (10 Mio pour l'import, 100 Mio pour la restauration).
- **Pas de documentation d'API exposée** : `/docs`, `/redoc` et `/openapi.json` ne servent que
  l'interface.
- **Authentification** : tous les points d'accès hors `/auth/*` répondent `401` sans session valide
  (test sur l'ensemble des routes) ; essais limités avec délai croissant, y compris pour le
  changement de mot de passe.
- **Base** : SQLCipher 4, clé dérivée de 256 000 itérations ; fichier en `0600`, dossier en `0700`.
- **Secrets** : aucun dans le dépôt (gitleaks en CI) ; le mot de passe n'est jamais journalisé ni
  placé dans l'environnement ; l'export ne contient aucun secret.
- **Dépendances** : `npm audit` (dont développement) et `pip-audit` sur le lockfile figé : aucune
  vulnérabilité connue ; Dependabot actif pour pip, npm, GitHub Actions et Docker.
- **Conteneur** : utilisateur non root (uid 10001), système de fichiers en lecture seule, aucune
  capacité Linux, `no-new-privileges`, port publié sur `127.0.0.1` seulement.
- **Sorties réseau** : voir `specs/001-wealth-dashboard-foundation/quickstart.md`, section 7.

**Risques résiduels, connus**

- Le **fichier d'export n'est pas chiffré** (voulu, signalé à chaque export).
- Derrière un proxy inverse HTTPS, `Secure` n'est posé sur le cookie que si uvicorn fait confiance
  à l'en-tête `X-Forwarded-Proto` du proxy : définir `FORWARDED_ALLOW_IPS` avec l'adresse du proxy
  (voir le README).
- `style-src 'unsafe-inline'` reste nécessaire aux styles en ligne de la bibliothèque de graphiques.
- Les sessions vivent en mémoire d'un seul processus : redémarrer l'application les ferme (voulu).
- La bibliothèque `yfinance` n'est pas auditée au niveau des échanges qu'elle fait elle-même avec
  Yahoo (consentement, jeton).
- Les taux du Livret A livrés avec l'application sont des valeurs à vérifier.
