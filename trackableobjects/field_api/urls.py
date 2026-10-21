from django.urls import path

from . import views

urlpatterns = [
    path("sync/", views.SyncView.as_view(), name="forms_sync"),
    path("push/", views.PushView.as_view(), name="forms_push"),
    path("attachments/", views.AttachmentUploadView.as_view(), name="forms_attachment_upload"),
    path("attachments/<int:attachment_id>/", views.AttachmentDownloadView.as_view(), name="forms_attachment"),
]
