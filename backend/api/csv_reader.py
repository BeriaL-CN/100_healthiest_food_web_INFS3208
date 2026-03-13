# from pyspark.sql import SparkSession

# # 创建 Spark session
# spark = SparkSession.builder \
#     .appName('FruitDataApp') \
#     .master('spark://park-master:7077') \
#     .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:9000") \
#     .config("spark.hadoop.dfs.client.use.datanode.hostname", "true") \
#     .getOrCreate()

# def read_csv(file_path):
#     # 使用 Spark 读取 CSV 文件
#     df = spark.read.csv(file_path, header=True, inferSchema=True)
    
#     return df


