import os
import requests
import json
from dotenv import load_dotenv
from datetime import datetime

def get_tenant_access_token(app_id, app_secret):
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    res = requests.post(url, json={"app_id": app_id, "app_secret": app_secret})
    return res.json().get("tenant_access_token")

def read_local_json(file_name):
    path = os.path.join(os.path.dirname(__file__), '..', file_name)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "未找到文件"

def insert_to_new_bitable():
    load_dotenv()
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    
    token = get_tenant_access_token(app_id, app_secret)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }

    # 首先，解析 Wiki 节点获取真实的 Bitable App Token
    wiki_token = "MDqhwja48izCo6koEhkc26yanId"
    print("1. 解析 Wiki 节点以获取真实表格 Token...")
    wiki_url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?token={wiki_token}"
    wiki_res = requests.get(wiki_url, headers=headers).json()
    
    if wiki_res.get("code") != 0:
        print("获取Wiki节点失败:", wiki_res)
        return
        
    node = wiki_res.get("data", {}).get("node", {})
    obj_type = node.get("obj_type")
    app_token = node.get("obj_token")
    
    print(f"节点类型: {obj_type}, App Token: {app_token}")
    
    table_id = "tblhDfegHWMG2w8n" # 来自你的链接

    # 1. 看看里面有哪些字段 (列)
    print("\n2. 获取多维表格字段...")
    url_fields = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
    res_fields = requests.get(url_fields, headers=headers).json()
    
    if res_fields.get("code") != 0:
        print("获取字段失败:", res_fields)
        return
        
    field_names = [f["field_name"] for f in res_fields.get("data", {}).get("items", [])]
    print(f"找到的字段: {field_names}")
    
    # 2. 读取本地参数
    pid_params = read_local_json("pid_params.json")
    feedforward_params = read_local_json("feedforward_params.json")
    jacobian_params = read_local_json("jacobian_params.json")

    # 3. 构造一行新数据
    record_fields = {}
    
    if "日期" in field_names:
         # 由于列类型在飞书中被设成了多行文本，所以我们传格式化的字符串
         record_fields["日期"] = datetime.now().strftime("%Y/%m/%d %H:%M:%S") 
    
    for f in field_names:
        if "pid" in f.lower():
            record_fields[f] = pid_params
        elif "前馈" in f:
            record_fields[f] = feedforward_params
        elif "雅可比" in f:
            record_fields[f] = jacobian_params
    
    if "序号" in field_names:
        record_fields["序号"] = "1" # 改为字符串以适应多行文本字段

    if "风扇动力" in field_names:
        record_fields["风扇动力"] = "1500" # 必须传字符串

    print("\n3. 准备写入数据...")
    url_records = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
    payload = {"fields": record_fields}
    
    res = requests.post(url_records, headers=headers, json=payload)
    if res.status_code == 200 and res.json().get("code") == 0:
        print("OK: 成功写入一条数据到飞书高级多维表格！")
    else:
        print("Error 写入失败:", res.json())

if __name__ == "__main__":
    insert_to_new_bitable()