from django.urls import path
from .views import fruit_data

urlpatterns = [
    path('fruit-data/', fruit_data, name='fruit-data'),
]