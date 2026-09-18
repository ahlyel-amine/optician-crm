"""Les jeux de données partagés par plusieurs fichiers de tests.

Un paquet, et non un simple dossier, parce que `tests/fixtures/noms_marocains.py` est
importé par `tests/test_recherche_clients.py` et le sera par `04-07` : un module sans
`__init__.py` ne serait pas importable sous `from tests.fixtures import …`.
"""
