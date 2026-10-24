## Résumé

<!-- Ce que change cette PR et pourquoi. Lien vers la spécification : specs/NNN-.../spec.md -->

## Vérifications

- [ ] La branche suit la convention (`feat/`, `fix/`, `chore/`, `docs/`) et les commits sont conventionnels
- [ ] Les calculs financiers ont des tests chiffrés écrits avant le code : premier commit rouge, dernier commit vert (principe V)
- [ ] Aucun montant ou taux n'utilise de flottant (principe III)
- [ ] Aucune opération du journal n'est modifiée ni supprimée en base, les corrections ajoutent une version (principe II)
- [ ] Aucune donnée personnelle réelle, aucun secret, aucun identifiant bancaire dans le code, les fixtures ou l'historique
- [ ] Aucune nouvelle sortie réseau, ou elle est décrite ci-dessous et ne transmet aucun montant (principe I)
- [ ] La documentation et le contrat d'API (`contracts/openapi.yaml`) sont à jour si l'interface change

## Impact sécurité

<!-- Authentification, chiffrement, entrées utilisateur, dépendances ajoutées ou mises à jour, nouveaux hooks ou workflows. Écrire « aucun » si c'est le cas. -->

## Tests

<!-- Comment c'est vérifié : tests ajoutés, commande lancée, résultat. -->
