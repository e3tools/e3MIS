"""REST surface for the field apps and the supervision dashboard (/api/v1/)."""

from django.urls import include, path

from fieldmonitoring.compliance import profile_views as profiles
from fieldmonitoring.compliance import views as compliance
from fieldmonitoring.registry import views as registry
from fieldmonitoring.review import views as review
from fieldmonitoring.visits import views as visits
from fieldmonitoring.warning import views as warning

urlpatterns = [
    path("", include("fieldmonitoring.core.urls")),
    path("auth/", include("fieldmonitoring.accounts.urls")),
    # Field user
    path("me/worksites/", registry.MyWorksitesView.as_view()),
    path("me/presence/", compliance.MyPresenceView.as_view()),
    path("me/quota/", compliance.MyQuotaView.as_view()),
    path("me/visits/", visits.MyVisitsView.as_view()),
    path("me/visits/open/", visits.OpenVisitView.as_view()),
    path("me/visits/history/", visits.MyVisitHistoryView.as_view()),
    # Registry
    path("worksites/nearby/", registry.NearbyWorksitesView.as_view()),
    path("worksites/provisional/", registry.ProvisionalWorksiteView.as_view()),
    path("worksites/<uuid:worksite_id>/high-risk/", registry.HighRiskProposeView.as_view()),
    path("villages/", registry.VillagesView.as_view()),
    path("high-risk/", registry.HighRiskListView.as_view()),
    path(
        "high-risk/<uuid:change_id>/<str:decision>/",
        registry.HighRiskDecideView.as_view(),
    ),
    path("coordinates/pending/", registry.PendingCoordinatesView.as_view()),
    path(
        "coordinates/<uuid:coordinate_id>/<str:decision>/",
        registry.CoordinateDecideView.as_view(),
    ),
    # Visits
    path("photos/capture-token/", visits.CaptureTokenView.as_view()),
    path("photos/", visits.PhotoUploadView.as_view()),
    path("visits/check-in/", visits.CheckInView.as_view()),
    path("visits/<uuid:visit_id>/", visits.VisitDetailView.as_view()),
    path("visits/<uuid:visit_id>/photo/", visits.PhotoView.as_view()),
    path("visits/<uuid:visit_id>/status/", visits.VisitStatusView.as_view()),
    path("visits/<uuid:visit_id>/check-out/", visits.CheckOutView.as_view()),
    path("visits/<uuid:visit_id>/reason/", visits.ReasonView.as_view()),
    # Review
    path("review/queue/", review.ReviewQueueView.as_view()),
    path("review/<uuid:visit_id>/", review.ResolveView.as_view()),
    # Supervision
    path("team/presence/", compliance.TeamPresenceView.as_view()),
    path("users/<int:user_id>/pauses/", compliance.UserPausesView.as_view()),
    path("users/<int:user_id>/profile/", profiles.UserProfileView.as_view()),
    path("users/<int:user_id>/worksites/", profiles.UserWorksitesView.as_view()),
    path("users/<int:user_id>/visits/", profiles.UserVisitsView.as_view()),
    path("worksites/<uuid:worksite_id>/", profiles.WorksiteDetailView.as_view()),
    path("worksites/<uuid:worksite_id>/visits/", profiles.WorksiteVisitsView.as_view()),
    path("pauses/<uuid:pause_id>/cancel/", compliance.CancelPauseView.as_view()),
    path("warnings/", warning.WarningListView.as_view()),
    path("warnings/generate/", warning.GenerateWarningView.as_view()),
    path("warnings/<str:week_of>/", warning.WarningDetailView.as_view()),
    path("compliance/baseline/", compliance.BaselineView.as_view()),
    # Configuration
    path("config/thresholds/", compliance.ThresholdsView.as_view()),
    path("config/programme/", compliance.ProgrammeConfigView.as_view()),
    path("config/history/", compliance.ConfigHistoryView.as_view()),
]
