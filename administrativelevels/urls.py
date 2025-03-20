from django.urls import path

from administrativelevels.infrastructure.home import HomeView

app_name = 'administrativelevels'

urlpatterns = [
    path('', HomeView.as_view(), name='home'),

]

