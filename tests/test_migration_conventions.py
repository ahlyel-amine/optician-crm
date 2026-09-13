"""The two migration-authoring rules, enforced rather than documented.

Both are painful to retrofit, and the first is a silent cross-database write rather than
an error. Django's own documentation states that `model_name` *"is None for the RunPython
and RunSQL operations unless they provide it using hints"* — so the router cannot classify
them, `allow_migrate` is asked about an app rather than a model, and an unguarded data
migration written for the tenant schema **also executes against `default`**.

`.planning/TESTING.md` rule 2 says do not test Django. This is not a Django test: it is a
check that *our* convention is followed, in *our* migrations.
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Names that count as the router guard when they open a RunPython callable.
GUARD_NAMES = frozenset({"migration_allowed", "allow_migrate"})


def migration_files() -> list[Path]:
    """Every migration module in the repository, excluding package markers."""
    return sorted(
        p
        for p in REPO_ROOT.glob("*/*/migrations/*.py")
        if p.name != "__init__.py" and ".venv" not in p.parts
    )


# --------------------------------------------------------------------------------------
# The checks themselves, factored out so the synthetic case can drive them directly
# --------------------------------------------------------------------------------------
def _runpython_callable_names(tree: ast.AST) -> set[str]:
    """Names passed to any `RunPython(...)`, positionally or by keyword."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        attr = getattr(func, "attr", None) or getattr(func, "id", None)
        if attr != "RunPython":
            continue
        for arg in list(node.args) + [kw.value for kw in node.keywords]:
            if isinstance(arg, ast.Name):
                names.add(arg.id)
            elif isinstance(arg, ast.Attribute):
                names.add(arg.attr)
    return names


def _first_statement_is_guard(func: ast.FunctionDef) -> bool:
    """True when the function's first statement is an early-return router guard.

    A docstring does not count as a statement for this purpose — it is documentation, not
    behaviour, and requiring the guard to precede it would be a style rule rather than a
    safety one.
    """
    body = list(func.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    if not body:
        return False
    stmt = body[0]
    if not isinstance(stmt, ast.If):
        return False
    calls = [n for n in ast.walk(stmt.test) if isinstance(n, ast.Call)]
    called = {
        getattr(c.func, "attr", None) or getattr(c.func, "id", None) for c in calls
    }
    if not (called & GUARD_NAMES):
        return False
    # The guard has to actually stop the migration, not merely be consulted.
    return any(isinstance(n, (ast.Return, ast.Raise)) for n in ast.walk(stmt))


def unguarded_runpython_callables(source: str) -> list[str]:
    """Names of `RunPython` callables in `source` that do not open with the guard."""
    tree = ast.parse(source)
    wanted = _runpython_callable_names(tree)
    if not wanted:
        return []
    defined = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    return sorted(
        name
        for name in wanted
        if name in defined and not _first_statement_is_guard(defined[name])
    )


def irreversible_runsql(source: str) -> int:
    """How many `RunSQL(...)` calls supply neither `reverse_sql` nor a marker comment."""
    tree = ast.parse(source)
    lines = source.splitlines()
    offenders = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        attr = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        if attr != "RunSQL":
            continue
        if any(kw.arg == "reverse_sql" for kw in node.keywords):
            continue
        if len(node.args) >= 2:  # positional reverse_sql
            continue
        window = "\n".join(lines[max(0, node.lineno - 3) : node.end_lineno + 1])
        if "# irreversible:" in window:
            continue
        offenders += 1
    return offenders


# --------------------------------------------------------------------------------------
# The real checks, over the real tree
# --------------------------------------------------------------------------------------
def test_tenant03_every_runpython_callable_guards_on_allow_migrate():
    """No data migration may execute against the control-plane database.

    Django passes `model_name=None` for `RunPython` and `RunSQL`, so the router has no
    model to classify and the operation runs against every alias the router does not veto
    — including `default`. A migration written to backfill a tenant table would therefore
    also run against the control plane (threat T-02-31).

    There are no `RunPython` migrations in the tree yet, so this passes vacuously today.
    That is exactly why `test_tenant03_the_runpython_check_is_proven_to_fire` exists
    below: a check that can never fail is not a check.
    """
    offenders: dict[str, list[str]] = {}
    for path in migration_files():
        bad = unguarded_runpython_callables(path.read_text(encoding="utf-8"))
        if bad:
            offenders[str(path.relative_to(REPO_ROOT))] = bad

    assert not offenders, (
        "These RunPython callables do not start with the router guard:\n"
        + "\n".join(f"  {f}: {', '.join(n)}" for f, n in offenders.items())
        + "\n\nAdd, as the first statement:\n"
        "    if not migration_allowed(schema_editor, '<app_label>'):\n"
        "        return\n"
        "See docs/migration-conventions.md."
    )


def test_tenant03_every_runsql_operation_is_reversible_or_explicitly_marked():
    """A fan-out across hundreds of databases must not be a one-way door.

    Either supply `reverse_sql`, or write `# irreversible: <reason>` beside the operation
    so the choice is visible in review rather than discovered during a rollback.
    """
    offenders = {}
    for path in migration_files():
        count = irreversible_runsql(path.read_text(encoding="utf-8"))
        if count:
            offenders[str(path.relative_to(REPO_ROOT))] = count

    assert not offenders, (
        f"RunSQL without reverse_sql and without an `# irreversible:` note: {offenders}"
    )


# --------------------------------------------------------------------------------------
# Proof that the checks fire
# --------------------------------------------------------------------------------------
UNGUARDED = textwrap.dedent(
    '''
    from django.db import migrations

    def backfill(apps, schema_editor):
        """Fill in the new column."""
        Mouvement = apps.get_model("stock", "MouvementStock")
        Mouvement.objects.all().update(motif="")

    class Migration(migrations.Migration):
        operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
    '''
)

GUARDED = textwrap.dedent(
    '''
    from django.db import migrations
    from plateforme.tenancy.migration_guard import migration_allowed

    def backfill(apps, schema_editor):
        """Fill in the new column."""
        if not migration_allowed(schema_editor, "stock"):
            return
        Mouvement = apps.get_model("stock", "MouvementStock")
        Mouvement.objects.all().update(motif="")

    class Migration(migrations.Migration):
        operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
    '''
)

CONSULTED_BUT_IGNORED = textwrap.dedent(
    """
    from django.db import migrations
    from plateforme.tenancy.migration_guard import migration_allowed

    def backfill(apps, schema_editor):
        if migration_allowed(schema_editor, "stock"):
            pass
        Mouvement = apps.get_model("stock", "MouvementStock")
        Mouvement.objects.all().update(motif="")

    class Migration(migrations.Migration):
        operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
    """
)


@pytest.mark.parametrize(
    ("label", "source", "expected"),
    [
        ("unguarded", UNGUARDED, ["backfill"]),
        ("guarded", GUARDED, []),
        ("consulted-but-ignored", CONSULTED_BUT_IGNORED, ["backfill"]),
    ],
)
def test_tenant03_the_runpython_check_is_proven_to_fire_on_synthetic_modules(
    label, source, expected
):
    """The guard check rejects an unguarded module and accepts a guarded one.

    The third case is the one worth having: a migration that *calls* the guard but does
    not act on it reads as compliant to a grep and is not. The check requires a `return`
    or `raise` inside the `if`, so it fails.

    Without these three cases the real check above is vacuous — there are no `RunPython`
    migrations in the tree yet, and a check that can never fail is not a check.
    """
    assert unguarded_runpython_callables(source) == expected, label


@pytest.mark.parametrize(
    ("label", "source", "expected"),
    [
        ("bare", "from django.db import migrations\nx = migrations.RunSQL('SELECT 1')", 1),
        (
            "reversible",
            "from django.db import migrations\n"
            "x = migrations.RunSQL('SELECT 1', reverse_sql='SELECT 2')",
            0,
        ),
        (
            "marked",
            "from django.db import migrations\n"
            "# irreversible: drops a column whose data cannot be reconstructed\n"
            "x = migrations.RunSQL('SELECT 1')",
            0,
        ),
    ],
)
def test_tenant03_the_runsql_check_is_proven_to_fire_on_synthetic_modules(
    label, source, expected
):
    """Same reasoning: prove the reversibility check can say no before trusting its yes."""
    assert irreversible_runsql(source) == expected, label


def test_tenant03_migration_allowed_answers_the_router_not_a_constant():
    """The helper the convention names must exist and must actually consult the router.

    Both directions, because a guard that always returns True is worse than none: it
    makes every migration look compliant while changing nothing. `magasins` is a business
    app, so it is allowed on a tenant alias and refused on `default`.
    """
    from types import SimpleNamespace

    from plateforme.tenancy.migration_guard import migration_allowed

    def editor(alias):
        return SimpleNamespace(connection=SimpleNamespace(alias=alias))

    assert migration_allowed(editor("tenant_7"), "magasins") is True
    assert migration_allowed(editor("default"), "magasins") is False
    assert migration_allowed(editor("default"), "control_plane") is True
    assert migration_allowed(editor("tenant_7"), "control_plane") is False


def test_tenant03_the_migration_scan_actually_finds_the_repositorys_migrations():
    """The AST checks are only meaningful if they are reading real files.

    A glob that silently matches nothing makes both checks above pass forever. This one
    turns red if the layout moves.
    """
    found = {p.name for p in migration_files()}
    assert "0001_initial.py" in found, f"the migration glob found only {found}"
    assert len(migration_files()) >= 3, (
        f"expected at least control_plane 0001+0002 and magasins 0001, found {found}"
    )
