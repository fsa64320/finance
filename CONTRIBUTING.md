# Contribuer

## Flux de travail

Aucun commit direct sur `main`. Tout passe par une branche et une pull request.

1. Partir de `main` à jour et créer une branche : `feat/<sujet>`, `fix/<sujet>`, `chore/<sujet>` ou
   `docs/<sujet>`.
2. Pour une fonctionnalité, suivre le flux Spec Kit : constitution, spécification (`/speckit-specify`),
   plan, tâches, implémentation. Les spécifications vivent dans `specs/NNN-nom/`.
3. Commiter avec des messages conventionnels (`feat:`, `fix:`, `docs:`, `chore:`, `test:`).
4. Ouvrir une pull request vers `main` avec le modèle fourni. La CI (`ci-gate`) doit passer.
5. Fusionner uniquement après relecture et CI verte, puis supprimer la branche.

## Règles de qualité

- Les calculs financiers sont écrits test d'abord, avec des cas chiffrés (principe V) : le premier commit d'une PR contient les tests rouges, le dernier est vert. Aucune PR ne fusionne de test rouge.
- Montants en décimaux exacts, jamais en flottants (principe III).
- Aucune donnée personnelle réelle ni aucun secret dans le dépôt, les fixtures ou les commits.
- Aucun scraping ni stockage d'identifiants d'établissements (principe IV).

## Avant de pousser

Installer les contrôles locaux (détection de secrets, fichiers volumineux, clés privées) :

```bash
pre-commit install
```
