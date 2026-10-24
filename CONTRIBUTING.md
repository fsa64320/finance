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

## Graphe de connaissances (graphify, optionnel)

Le dépôt s'appuie sur [graphify](https://pypi.org/project/graphifyy/) pour que les assistants de
code (Claude Code) naviguent dans le code via un graphe plutôt que par recherche brute. Le graphe
est **local à chaque contributeur** : `graphify-out/` est ignoré par Git et ne se commite jamais.
Sans graphify installé, rien ne casse : les hooks de `.claude/settings.json` ne font rien si la
commande est absente.

Mise en place, une fois par clone :

```bash
uv tool install graphifyy
graphify install
graphify hook install
graphify update .
```

- `graphify install` copie le skill pour Claude Code.
- `graphify hook install` pose les hooks Git (`post-commit`, `post-merge`, `post-checkout`,
  `post-rewrite`) qui régénèrent le graphe après chaque commit, pull, changement de branche ou
  rebase. Il n'y a pas d'appel API : l'extraction du code passe par l'AST. Vérification avec
  `graphify hook status`.
- `graphify update .` construit le premier graphe.

Utilisation : `graphify query "<question>"`, `graphify explain "<concept>"` et
`graphify path "<A>" "<B>"`. Après une modification de code, `graphify update .` remet le graphe à
jour si les hooks ne l'ont pas déjà fait. Pour sauter un hook ponctuellement :
`GRAPHIFY_SKIP_HOOK=1 git commit ...`.
