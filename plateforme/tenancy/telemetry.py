"""Sentry scrubbing. Keep the tag, scrub the body.

`CLAUDE.md` wants every Sentry event tagged with client and magasin — that tagging is what
makes an error report actionable with one database per client. But ordonnances are health
data under law 09-08, and Sentry is a third party that may store events outside Morocco
and outside the EU. Event *bodies* must not carry ordonnance values, client names or
telephone numbers (threat T-02-17).

Wired now, while the tagging is being added, rather than later. Retrofitting a scrubber
after a leak is not a fix: the events are already stored, already replicated, and already
outside our control.

`send_default_pii = False` (set in `config/settings/base.py`) is the coarse control — it
stops Sentry attaching request bodies, cookies and user data by default. This scrubber is
the fine one: it redacts anything that looks like clinical or personal data wherever it
appears, including in local variables captured from a stack frame, which
`send_default_pii` does not cover.
"""

from __future__ import annotations

import re

REDACTED = "[redacted]"

#: Key patterns whose *values* are redacted wherever they appear. Ordonnance optics
#: (sphère, cylindre, axe, addition, écart pupillaire), identity and contact details.
SENSITIVE_KEY = re.compile(
    r"(ordonnance|prescription|sph(ere)?|cyl(indre)?|\baxe\b|addition|"
    r"ecart_pupillaire|\bep\b|\bpd\b|acuite|"
    r"nom|prenom|raison_sociale|telephone|tel|gsm|mobile|email|mail|adresse|"
    r"cin|date_naissance|naissance|"
    # CLIENT-09, plan 04-06. Ces six-là ne couvrent pas une valeur clinique : elles
    # couvrent un **nom de fichier**, et un nom de fichier téléversé porte couramment le
    # nom du patient — `ordonnance_benali_ahmed.jpg` est la forme normale, pas le cas
    # tordu. Une trace d'exception traversant un sérialiseur de téléversement emporte
    # les variables locales de chaque cadre de pile, c'est-à-dire la valeur, et c'est
    # exactement le chemin par lequel elle atteindrait Sentry.
    #
    # Six alternances plutôt qu'un caviardage général : un caviardage qui emporte tout
    # se fait désactiver, et alors plus rien n'est caviardé. Le contrôle positif du test
    # paramétré tient cette limite.
    r"photo|image|fichier|scan|piece_jointe|upload|"
    r"password|passwd|secret|token|authorization|api_key|db_password)",
    re.IGNORECASE,
)

#: How deep to walk. Sentry events are shallow; a bound stops a pathological structure
#: from turning error reporting into a denial of service.
MAX_DEPTH = 12


def _scrub(value, depth: int = 0):
    if depth > MAX_DEPTH:
        return REDACTED
    if isinstance(value, dict):
        return {
            key: (
                REDACTED
                if isinstance(key, str) and SENSITIVE_KEY.search(key)
                else _scrub(item, depth + 1)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        scrubbed = [_scrub(item, depth + 1) for item in value]
        return type(value)(scrubbed) if isinstance(value, tuple) else scrubbed
    return value


def before_send(event, hint):
    """Redact clinical and personal values from an event before it leaves the process.

    Tags are left alone on purpose: `client` and `magasin` are identifiers we chose, not
    personal data, and they are the whole reason the integration is worth having.

    Request bodies, query strings, form data, breadcrumb payloads and the local variables
    captured in every stack frame are all scrubbed, because a traceback through a
    serializer carries exactly the values the request carried.
    """
    request = event.get("request")
    if isinstance(request, dict):
        for key in ("data", "query_string", "cookies", "headers", "env"):
            if key in request:
                request[key] = _scrub(request[key])

    event["extra"] = _scrub(event.get("extra", {}))
    event["breadcrumbs"] = _scrub(event.get("breadcrumbs", {}))

    for container in ("exception", "threads"):
        for entry in (event.get(container) or {}).get("values", []) or []:
            for frame in (entry.get("stacktrace") or {}).get("frames", []) or []:
                if "vars" in frame:
                    frame["vars"] = _scrub(frame["vars"])

    return event
