# from .csv_reader import read_csv  # 导入Spark处理函数
from pathlib import Path
from django.http import JsonResponse
import pandas as pd
import os

def fruit_data(request):
    file_path = os.path.join(Path(__file__).resolve().parent.parent, 'data', 'top_100_fruits.csv')
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        data = df.to_dict(orient='records')  # 转换为字典格式
        return JsonResponse(data, safe=False)  # 返回 JSON 响应
    else:
        return JsonResponse({'error': '文件未找到'}, status=404)
