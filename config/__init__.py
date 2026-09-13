"""Project configuration package.

Exporting `celery_app` here is what makes `@shared_task` work: Celery's shared-task
proxy binds to the app registered when the project package is imported, and Django
imports this package for every management command and every WSGI worker.
"""

from config.celery import app as celery_app

__all__ = ("celery_app",)
