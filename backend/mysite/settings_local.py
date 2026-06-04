"""
Django 本地开发配置
不使用 Docker 时使用此配置文件

使用方式: python manage.py runserver --settings=mysite.settings_local
"""

from pathlib import Path
from .settings import *  # 继承所有原有配置

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# 本地开发允许所有主机
ALLOWED_HOSTS = ['*']

# 本地开发 DEBUG 模式
DEBUG = True

# 使用主 URL 配置，保证本地和 Docker 返回同一种 API 格式
ROOT_URLCONF = 'mysite.urls'

# 数据库保持 SQLite
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
