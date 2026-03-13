"""
本地开发 URL 配置
"""

from django.urls import path
from mysite.api_views_local import fruit_data_local

urlpatterns = [
    path('api/fruit-data/', fruit_data_local, name='fruit-data-local'),
]
