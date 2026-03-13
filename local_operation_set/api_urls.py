"""
本地开发 URL 配置
"""

from django.urls import path
from local_dev.api_views import fruit_data_local

urlpatterns = [
    path('fruit-data/', fruit_data_local, name='fruit-data-local'),
]
