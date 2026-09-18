"""Threat T-02-17 — ordonnance and client data must not ride along in a Sentry event.

`CLAUDE.md` wants every event tagged with client and magasin, because with one database
per client an untagged error report is close to useless. But ordonnances are sensitive
health data under law 09-08, and Sentry is a third party that may store events outside
Morocco and outside the EU.

So: **keep the tag, scrub the body.** These tests are the reason that sentence stays true
— a scrubber with no test is a scrubber that silently stops covering a new field.
"""

import pytest

from plateforme.tenancy.telemetry import REDACTED, before_send


def _event():
    return {
        "request": {
            "url": "https://app.example/api/ordonnances/",
            "data": {
                "client_nom": "Mohamed Alaoui",
                "telephone": "+212600000000",
                "ordonnance": {"sphere_od": "-2.25", "cylindre_od": "-0.75", "axe_od": 90},
                "magasin_id": 4,
            },
            "headers": {"Authorization": "Bearer abc.def.ghi", "User-Agent": "curl/8"},
        },
        "tags": {"client": "opt-001", "magasin": "MAG001"},
        "extra": {"db_password": "hunter2", "facture_numero": "2026-000123"},
        "exception": {
            "values": [
                {
                    "stacktrace": {
                        "frames": [
                            {
                                "function": "creer_ordonnance",
                                "vars": {
                                    "prescription": {"addition": "+2.00"},
                                    "email": "client@example.ma",
                                    "quantite": 2,
                                },
                            }
                        ]
                    }
                }
            ]
        },
    }


def test_tenant_telemetry_scrubs_clinical_and_personal_values():
    """Prescription optics, identity and contact details are redacted wherever they appear."""
    scrubbed = before_send(_event(), hint={})

    data = scrubbed["request"]["data"]
    assert data["client_nom"] == REDACTED
    assert data["telephone"] == REDACTED
    assert data["ordonnance"] == REDACTED, (
        "The ordonnance payload survived. Sphère, cylindre and axe are clinical values "
        "for an identified person — exactly what law 09-08 covers."
    )
    assert scrubbed["request"]["headers"]["Authorization"] == REDACTED
    assert scrubbed["extra"]["db_password"] == REDACTED


def test_tenant_telemetry_scrubs_captured_stack_frame_locals():
    """Frame locals are the leak `send_default_pii = False` does not cover.

    A traceback through a serializer captures the values the request carried, in
    `frame["vars"]`, regardless of the PII setting. That is the path a real ordonnance
    would most plausibly take to Sentry.
    """
    scrubbed = before_send(_event(), hint={})
    frame_vars = scrubbed["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]

    assert frame_vars["prescription"] == REDACTED
    assert frame_vars["email"] == REDACTED
    assert frame_vars["quantite"] == 2, (
        "Non-sensitive locals were redacted too. A scrubber that redacts everything gets "
        "turned off, and then nothing is scrubbed."
    )


def test_tenant_telemetry_keeps_the_client_and_magasin_tags():
    """The tags are the whole point of the integration and must survive untouched.

    They are identifiers we chose, not personal data, and without them an error report
    cannot be traced to a client database.
    """
    scrubbed = before_send(_event(), hint={})
    assert scrubbed["tags"] == {"client": "opt-001", "magasin": "MAG001"}


def test_tenant_telemetry_tolerates_a_sparse_event():
    """Sentry events are not uniform; a missing key must not raise inside `before_send`.

    An exception in the scrubber is dropped by the SDK, which would send the event
    unscrubbed or lose it entirely — both bad, and both silent.
    """
    assert before_send({}, hint={}) is not None
    assert before_send({"request": None, "exception": None}, hint={}) is not None


# ======================================================================================
# CLIENT-09 — le nom du fichier téléversé (plan 04-06)
# ======================================================================================
#: Les six clés sous lesquelles un nom de fichier voyage. **Paramétré et non écrit une
#: fois**, parce que le mode de défaillance est l'alternance *manquante* : un test qui
#: n'en vérifierait qu'une resterait vert avec cinq trous.
CLES_DE_FICHIER = ("photo", "image", "fichier", "scan", "upload", "piece_jointe")

#: Le nom tel qu'un comptoir en produit. Il porte le nom du patient — c'est toute la
#: raison de ce test.
NOM_TELEVERSE = "ordonnance_benali_ahmed.jpg"


@pytest.mark.parametrize("cle", CLES_DE_FICHIER)
def test_client09_un_nom_de_fichier_n_atteint_pas_sentry_en_clair(cle):
    """`SENSITIVE_KEY` ne couvrait aucune de ces six clés. CLIENT-09, `04-RESEARCH.md` §4.6.

    Un nom de fichier téléversé porte couramment le nom du patient, et une trace
    d'exception traversant un sérialiseur de téléversement emporte les variables locales
    de chaque cadre de pile — c'est-à-dire la valeur. `send_default_pii = False` ne
    couvre pas les locales ; ce caviardage-ci, si.

    **Le contrôle positif est dans le même test, et il n'est pas décoratif** : sans lui,
    un `SENSITIVE_KEY` réduit à `.` — donc un caviardage total — serait vert. Un
    caviardage total se fait désactiver, et alors plus rien n'est caviardé.
    """
    evenement = {
        "extra": {cle: NOM_TELEVERSE, "duree_ms": 42},
        "exception": {
            "values": [
                {"stacktrace": {"frames": [{"vars": {cle: NOM_TELEVERSE, "duree_ms": 42}}]}}
            ]
        },
    }
    scrubbed = before_send(evenement, hint={})
    frame_vars = scrubbed["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]

    for endroit, charge in (("extra", scrubbed["extra"]), ("locales", frame_vars)):
        assert charge[cle] == REDACTED, (
            f"La clé « {cle} » survit dans {endroit} avec {charge[cle]!r}. Ce nom de "
            "fichier porte le nom du patient, et Sentry est un tiers qui peut stocker "
            "l'événement hors du Maroc et hors de l'UE."
        )
        assert charge["duree_ms"] == 42, (
            f"« duree_ms » a été caviardée dans {endroit}. Un caviardage qui emporte "
            "tout se fait désactiver, et alors plus rien n'est caviardé."
        )
