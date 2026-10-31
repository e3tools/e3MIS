from django.urls import path

from cdd.infrastructure.views.cycle_detail import CycleDetailView
from cdd.infrastructure.views.cycle_facilitators import CycleFacilitatorsView
from cdd.infrastructure.views.cycle_list import CycleListView
from cdd.infrastructure.views.cycle_start import CycleCommunitiesView, CycleStartView
from cdd.infrastructure.views.cycle_status import CycleStatusView
from cdd.infrastructure.views.node_delete import NodeDeleteView
from cdd.infrastructure.views.node_edit import NodeEditView
from cdd.infrastructure.views.task_edit import TaskEditView
from cdd.infrastructure.views.template_create import CycleTemplateCreateView
from cdd.infrastructure.views.template_detail import CycleTemplateDetailView
from cdd.infrastructure.views.template_edit import CycleTemplateEditView
from cdd.infrastructure.views.template_list import CycleTemplateListView
from cdd.infrastructure.views.tree_reorder import TreeReorderView

app_name = "cdd"
urlpatterns = [
    path("", CycleListView.as_view(), name="cycle_list"),
    path("start/", CycleStartView.as_view(), name="cycle_start"),
    path("start/communities/", CycleCommunitiesView.as_view(), name="cycle_communities"),
    path("<int:pk>/", CycleDetailView.as_view(), name="cycle_detail"),
    path("<int:pk>/status/", CycleStatusView.as_view(), name="cycle_status"),
    path("<int:pk>/facilitators/", CycleFacilitatorsView.as_view(), name="cycle_facilitators"),
    path("designer/", CycleTemplateListView.as_view(), name="template_list"),
    path("designer/create/", CycleTemplateCreateView.as_view(), name="template_create"),
    path("designer/<int:pk>/", CycleTemplateDetailView.as_view(), name="template_detail"),
    path("designer/<int:pk>/edit/", CycleTemplateEditView.as_view(), name="template_edit"),
    path("designer/<int:pk>/reorder/", TreeReorderView.as_view(), name="tree_reorder"),
    path("designer/<int:parent>/phase/add/", NodeEditView.as_view(), {"kind": "phase"}, name="phase_add"),
    path("designer/phase/<int:pk>/edit/", NodeEditView.as_view(), {"kind": "phase"}, name="phase_edit"),
    path("designer/phase/<int:parent>/activity/add/", NodeEditView.as_view(), {"kind": "activity"},
         name="activity_add"),
    path("designer/activity/<int:pk>/edit/", NodeEditView.as_view(), {"kind": "activity"}, name="activity_edit"),
    path("designer/activity/<int:activity>/task/add/", TaskEditView.as_view(), name="task_add"),
    path("designer/task/<int:pk>/edit/", TaskEditView.as_view(), name="task_edit"),
    path("designer/<str:kind>/<int:pk>/delete/", NodeDeleteView.as_view(), name="node_delete"),
]
