"""
本地开发视图 - 使用正确的文件路径
"""

from pathlib import Path
from django.http import JsonResponse
import pandas as pd
import os

def fruit_data_local(request):
    # 获取项目根目录 (backend 的上上级)
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    file_path = os.path.join(BASE_DIR, 'data', 'top_100_fruits.csv')
    
    print(f"Looking for file at: {file_path}")
    print(f"Exists: {os.path.exists(file_path)}")
    
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        data = df.to_dict(orient='records')
        return JsonResponse(data, safe=False)
    else:
        return JsonResponse({'error': '文件未找到', 'path': file_path}, status=404)
