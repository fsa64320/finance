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
