# Reporté — trouvé pendant l'exécution, hors périmètre du plan

Quatre entrées, toutes issues du plan `04-06` (CLIENT-09, la photo de l'ordonnance).
Aucune n'est un défaut du livré : chacune est une limite **écrite plutôt que découverte
plus tard**, avec sa raison et son reprenant.

| Réf | Ce qui est différé | Raison | Qui reprend |
|---|---|---|---|
| **D-4-1** | TENANT-09 ne couvre pas le magasin de fichiers | le back-end de production est une sortie de la **phase 1** ; étendre l'artefact maintenant serait à refaire | phase 1 pour la juridiction, puis un plan de reprise de TENANT-09 |
| **D-4-2** | La rétention de dix ans (art. 211 CGI) et l'archive d'offboarding de la **phase 12** ont le même trou | même raison | phase 12 |
| **D-4-3** | Aucun PDF accepté en pièce jointe (`04-UI-SPEC.md` §22.1) | un PDF demande une visionneuse, et le chemin documentaire est la phase 9 | phase 9 |
| **D-4-4** | Le nom du fichier envoyé n'est affiché nulle part, alors que `04-UI-SPEC.md` §22.2 le demandait | il porte couramment le nom du patient et n'est donc conservé nulle part | phase 9, si un contrôle de mauvaise pièce jointe reste voulu |

---

## D-4-1 · La sauvegarde par client ne couvre pas les photos

**Trouvé pendant :** plan `04-06`, en lisant `plateforme/control_plane/backup.py` de bout
en bout plutôt qu'en supposant. La recherche de phase l'avait signalé comme *non vérifié*
(`04-RESEARCH.md` §4.5, ligne 8 du tableau des angles morts).

**Constat, mesuré.** `backup_client` produit **un** `pg_dump` et rien d'autre :
un fichier au format custom, son `sha256`, une ligne `BackupRun`. Une photo d'ordonnance
vit hors de la base — c'est même la décision de la zone grise 3, et pour une bonne
raison : une colonne binaire de plusieurs Mo par ordonnance rendrait la sauvegarde par
client et la rétention à dix ans coûteuses. Restaurer ce `.dump` seul rend donc **toutes
les lignes**, chemin de photo compris, et **aucun fichier image**.

La promesse de TENANT-09 — « sauvegarde par client, restauration mono-client
**vérifiée** » — devient donc partiellement fausse pour la phase 4, et c'est cela qu'il
fallait refuser : pas le trou, mais le trou **silencieux**.

**Retenu : consigner, ne pas étendre.** Étendre l'artefact obligerait à passer du `.dump`
unique à une archive, donc à changer le chemin de restauration **et** la comparaison
`tenant_checksum` que la phase 2 a prouvés par un exercice réel — pour un back-end de
stockage que la **phase 1 n'a pas encore choisi**, et qu'il faudrait donc refaire. Le
travail serait fait deux fois, et la seconde fois contre un chemin de restauration qu'on
aurait entre-temps fragilisé.

**Ce qui a été fait à la place :** trois lignes dans la docstring de `backup_client`,
nommant ce que l'artefact ne couvre pas et pointant cette entrée. La garantie ne devient
pas fausse en silence.

**À qui cela revient.** La phase 1 pour la juridiction et le back-end (LEGAL-02), puis un
plan de reprise de TENANT-09 qui décidera entre deux formes : un second artefact par
client à côté du `.dump`, ou un back-end de stockage dont la durabilité est elle-même la
sauvegarde (versionnement et réplication côté objet). La seconde ne coûte rien au chemin
de restauration prouvé ; c'est un argument pour elle, pas une décision.

## D-4-2 · La rétention à dix ans et l'offboarding ont le même trou

**Même cause, deux conséquences de plus.** L'art. 211 CGI impose dix ans de conservation
sur les pièces justificatives, et une photo d'ordonnance en est une — c'est ce qui
justifie un remboursement AMO. L'archive d'offboarding de la phase 12 doit rendre à
l'opticien **tout** ce qui est à lui.

Les deux supposent aujourd'hui que « tout ce qui est à lui » tient dans la base. Ce n'est
plus vrai depuis le plan `04-06`.

**À qui cela revient.** Phase 12, qui doit inclure le préfixe de fichiers du client dans
l'archive d'offboarding — et qui aura, à ce moment-là, un back-end de production à
interroger.

## D-4-3 · Aucun PDF en pièce jointe

`04-UI-SPEC.md` §22.1 le pose : `accept="image/jpeg,image/png,image/webp,image/heic"`, et
**aucun PDF en phase 4**. Le réglage `ORDONNANCE_TYPES_ACCEPTES` le tient côté serveur, et
les octets magiques le tiennent contre un PDF renommé.

**Raison.** Un PDF demande une visionneuse, et le chemin documentaire — génération,
rendu, impression — est la phase 9. L'accepter maintenant produirait une pièce jointe que
l'écran ne sait pas montrer.

**À qui cela revient.** Phase 9, si le besoin se confirme. Un opticien qui reçoit une
ordonnance en PDF peut en attendant en faire une capture.

## D-4-4 · Le nom du fichier envoyé n'est affiché nulle part

**Trouvé pendant :** plan `04-06`, en écrivant le sérialiseur de sortie.

`04-UI-SPEC.md` §22.2 demande que le nom du fichier s'affiche à côté de la vignette,
tronqué à 40 caractères, comme **contrôle de mauvaise pièce jointe** pour la personne qui
voit déjà le dossier. C'est un besoin réel.

**Il n'est pas satisfait, et c'est délibéré.** Le même document, une section plus haut,
dit pourquoi : ce nom porte couramment le nom du patient. Le plan `04-06` en tire la
conséquence entière plutôt que la moitié confortable — le nom n'est conservé **nulle
part** : ni sur le disque (le nom stocké est un `uuid4` fabriqué par le stockage), ni en
colonne, ni dans un message d'erreur. Il n'y a donc rien à afficher, et l'écran de la
phase 4 (`04-09`) n'affichera pas ce contrôle.

**Ce qui le remplace, à moindre risque.** La version et la date d'attache sont servies
(`photo_attachee_le`), et la vignette elle-même est le meilleur contrôle de mauvaise
pièce jointe qui soit : on voit l'image.

**À qui cela revient.** Phase 9, si un contrôle textuel reste voulu. La forme la moins
dangereuse serait une colonne portant le nom **caviardé** ou son seul suffixe, pas le nom
brut.

---

## D-4-5 · Le serveur refuse toujours ce que l'écran ne fait plus qu'avertir

**Trouvé pendant :** plan `04-08`, en appliquant l'amendement Q4 du discriminant 45 mm.

Le propriétaire a décidé (Q4) que le discriminant monoculaire/binoculaire est un
**avertissement** et non un refus. Le plan `04-08` l'applique côté écran : le champ
d'écart pupillaire accepte désormais l'**union** des deux plages servies, et A8/A9
nomment la correction sans bloquer.

**Le serveur, lui, n'a pas bougé.** `domaine/ordonnances/bornes.py` sert
`ep_binoculaire.min = "45.0"` et `ep_monoculaire.max = "44.5"`, et la `CheckConstraint`
dérivée les applique. Un binoculaire de 31,5 franchit donc l'écran, part, et **revient en
400**. C'est exactement le mode de défaillance que §28-Q1 nomme : « un client qui accepte
ce que le serveur refuse est un appel au support sans cause visible » — ici avec un
message de refus serveur, donc visible, mais après un aller-retour et sans la phrase qui
nomme la correction.

**Pourquoi ce n'est pas corrigé ici.** Le plan `04-08` ne touche aucun fichier Python,
par contrat écrit dans sa section `<verification>`. Élargir la contrainte est une
migration et une décision sur une valeur clinique ; elle appartient au même échange avec
l'opticien que §28-Q4.

**À qui cela revient.** Le jour où l'opticien répond :
- s'il **confirme** le seuil → la réversion est d'une ligne côté écran (A8/A9 repassent
  en `severite: "refus"`, la borne du champ redevient la plage propre à chaque forme) et
  le serveur ne change pas ;
- s'il **infirme** le seuil → `BORNES.ep_binoculaire.min` et `BORNES.ep_monoculaire.max`
  s'élargissent à l'union, une migration suit, et l'écran ne change pas.

Les deux issues sont d'un coût connu. Ce qu'il ne faut pas faire entre-temps, c'est
recopier 45,0 dans le SPA pour « faire correspondre » les deux : ce serait un second
endroit nommé, ce que D-4b interdit.
