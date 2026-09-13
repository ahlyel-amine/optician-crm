"""Root URLconf.

Only the operator admin so far. Business routes are mounted by Phases 3 onward, behind
the API, and `resolve_client` deliberately returns `None` for this path — the admin is
fleet management, not one optician's data, so leaving the tenant context unbound here is
correct. A business query reached from an admin page *should* raise.
"""

from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
