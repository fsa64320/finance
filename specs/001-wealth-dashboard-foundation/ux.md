# UX : Socle de suivi de patrimoine et tableau de bord

**Feature** : [spec.md](spec.md) | **Plan** : [plan.md](plan.md)
**Source** : [découverte UX](../../docs/ux-discovery/2026-10-24-finance-discovery.md)
**Exigences** : FR-026, FR-034, FR-035, FR-036, SC-005, SC-006, SC-010

## Persona et parcours de référence

Persona primaire : épargnant salarié multi-enveloppes, débutant technique, sur ordinateur. Job principal : consolider son patrimoine pour le point mensuel (J1). Parcours : ouvrir l'application, importer ou saisir, lire le patrimoine net, décider.

## Règles transverses

- **Quatre états par écran de données** : vide (avec l'action suivante), chargement, erreur (cause et action possible), succès ou confirmation. Composants : `EmptyState`, `LoadingState`, `ErrorState`, retour de succès dans `LiveAnnouncer`.
- **Formats** : `1 234,56 €`, `24/10/2026`, pourcentages `fr-FR`, montants alignés à droite avec chiffres tabulaires.
- **Clavier et focus** : tout élément interactif atteignable et utilisable au clavier, focus visible, ordre de tabulation logique, boîtes de dialogue avec focus piégé et fermeture par Échap.
- **Libellés et erreurs** : chaque champ a un libellé associé ; chaque message d'erreur est lié à son champ et dit quoi faire.
- **Couleur** : « estimé » et « périmé » portent un libellé ou une icône en plus de la couleur.
- **Graphiques** : la courbe et la répartition ont un résumé textuel et un tableau de données (`ChartSummary`).
- **Annonces** : import terminé, erreur et expiration de session sont annoncés aux technologies d'assistance (`LiveAnnouncer`).
- **Confirmations** : restauration d'un export (rappel que les données actuelles seront remplacées), clôture d'un compte, changement de mot de passe. Annuler une opération est immédiat (historique, FR-004).
- **Responsive** : ordinateur d'abord ; consultation lisible dès 375 px sans défilement horizontal.

## Écrans

| Écran | Vide | Chargement | Erreur | Succès / confirmation | Notes d'accessibilité |
|---|---|---|---|---|---|
| Connexion | Invite à créer le mot de passe, avec l'avertissement « un oubli rend les données irrécupérables » | Bouton désactivé avec libellé « Connexion… » | Mot de passe refusé (règle à respecter) ; délai restant après 5 échecs | Accès au tableau de bord | Règles du mot de passe lisibles avant la saisie ; erreur liée au champ |
| Tableau de bord | Guide vers la création d'un premier compte | Squelettes pour la synthèse, la courbe, la répartition, les comptes | Message avec action « Réessayer » ; valeurs estimées signalées | – | Résumé textuel et tableau pour chaque graphique ; mention « hors dettes » |
| Comptes | Propose de créer le premier compte | Squelette de liste | Cause et « Réessayer » | Compte créé annoncé | Formulaire étiqueté, clavier complet |
| Détail de compte | Compte sans opération : invite à saisir ou importer | Squelette des positions et de l'historique | Cause et action | Opération enregistrée annoncée ; clôture confirmée par boîte de dialogue | Tableaux avec en-têtes ; historique des modifications accessible |
| Actifs et prix | Aucun actif : invite à en créer un | Indicateur pendant la mise à jour des cours | Source indisponible : derniers prix conservés et signalés | Prix enregistré annoncé | ISIN invalide expliqué dans le champ |
| Import | Invite à déposer un fichier, avec un modèle d'exemple | Progression de l'analyse du fichier | Lignes rejetées listées avec la cause et la correction | Résumé : lignes ajoutées, ignorées, rejetées, annoncé | Aperçu en tableau navigable au clavier ; actifs inconnus : choix explicite par actif |
| Réglages et export | Récupération des prix désactivée par défaut | Indicateur pendant l'export ou la restauration | Fichier de restauration invalide expliqué | Export prêt ; restauration confirmée par boîte de dialogue | Boîtes de dialogue avec focus piégé ; rappel d'export non bloquant |

## Valeurs par défaut

- **Rappel d'export** : toutes les 4 semaines, bannière non bloquante modifiable dans les réglages.
- **Avertissement « indicatif »** (FR-032) : bandeau permanent discret dans la mise en page, plus mention sur le tableau de bord.
- **Valeur estimée ou périmée** (FR-025) : pastille « estimé » avec icône et libellé, info-bulle donnant la date du dernier prix.

## Vérification

- Tests : `jest-axe` par écran (T142), parcours clavier Playwright (T143), états d'écran (T148), formats (T149), confirmations (T151).
- Mesures : SC-005 et SC-006 avec un testeur débutant (T130, T152).
