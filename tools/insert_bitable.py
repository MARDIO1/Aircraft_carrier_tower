import os
import requests
import json
from dotenv import load_dotenv

def get_tenant_access_token(app_id, app_secret):
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    res = requests.post(url, json={"app_id": app_id, "app_secret": app_secret})
    return res.json().get("tenant_access_token")

def read_local_json(file_name):
    path = os.path.join(os.path.dirname(__file__), '..', file_name)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read() # 读取为字符串即可，方便直接塞进表格
    except FileNotFoundError:
        return "未找到文件"

def insert_to_bitable():
    load_dotenv()
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    
    # 根据刚才找到的 Token 解析出 App_Token 和 Table_ID
    app_token = "P9khbt7CGaOsAEsm3DCcbIutn0R"
    table_id = "tblRAk9tsnRsZBKM"
    
    token = get_tenant_access_token(app_id, app_secret)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }

    # 1. 看看里面有哪些字段 (列)
    print("获取多维表格字段...")
    url_fields = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
    res_fields = requests.get(url_fields, headers=headers).json()
    
    field_names = [f["field_name"] for f in res_fields.get("data", {}).get("items", [])]
    print(f"找到的字段: {field_names}")
    
    # 2. 读取本地参数（你可以根据实际存在的json调整名字）
    pid_params = read_local_json("pid_params.json")
    feedforward_params = read_local_json("feedforward_params.json")
    jacobian_params = read_local_json("jacobian_params.json")

    # 3. 构造一行新数据
    # 注意：我们必须只使用存在的字段名。如果没有该字段会报错。
    # 我们暂且填入基础字段
    from datetime import datetime
    record_fields = {}
    
    if "日期" in field_names:
        record_fields["日期"] = datetime.now().strftime("%Y/%m/%d %H:%M") # 有些日期字段可能需要时间戳，如果报错我们将改为文本格式，前提是你在飞书里没设为强校验的日期类型
    if "pid参数" in field_names or "pid参数" in str(field_names): # 可能是大写/小写
        record_fields["pid参数"] = pid_params
    if "舵面前馈(向下为负数，向上为正数）" in field_names:
        record_fields["舵面前馈(向下为负数，向上为正数）"] = feedforward_params
    elif "舵面前馈" in field_names:
         record_fields["舵面前馈"] = feedforward_params
    if "雅可比矩阵" in field_names:
         record_fields["雅可比矩阵"] = jacobian_params

    # 如果有其他字段需要可以随便加
    record_fields["序号"] = "AI自动录入测试"
    record_fields["风扇动力"] = "未填写"

    print("\n准备写入数据...")
    url_records = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
    payload = {"fields": record_fields}
    
    res = requests.post(url_records, headers=headers, json=payload)
    if res.status_code == 200 and res.json().get("code") == 0:
        print("✅ 成功写入一条数据到飞书多维表格！")
    else:
        print("❌ 写入失败:", res.json())

if __name__ == "__main__":
    insert_to_bitable()