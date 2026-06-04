from django.urls import path
from .views import fruit_data

urlpatterns = [
    path('food-data/', fruit_data, name='food-data'),
    path('fruit-data/', fruit_data, name='fruit-data'),
]
