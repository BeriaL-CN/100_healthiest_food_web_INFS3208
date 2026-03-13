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

# 使用本地 URL 配置
ROOT_URLCONF = 'mysite.api_urls_local'

# 数据库保持 SQLite
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
