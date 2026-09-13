"""Root URLconf.

Deliberately empty. Business routes are mounted by later phases; the control-plane
admin is mounted by plan 02-02.
"""

from django.urls import path

urlpatterns: list[path] = []
