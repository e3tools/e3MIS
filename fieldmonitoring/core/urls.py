from django.urls import path

from .views import health, run_jobs

urlpatterns = [
    path("health/", health, name="health"),
    path("jobs/run/", run_jobs, name="run_jobs"),
]
