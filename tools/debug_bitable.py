import os
import requests
import json
from dotenv import load_dotenv

def get_tenant_access_token(app_id, app_secret):
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    res = requests.post(url, json={"app_id": app_id, "app_secret": app_secret})
    return res.json().get("tenant_access_token")

def debug_forbidden():
    load_dotenv()
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    
    token = get_tenant_access_token(app_id, app_secret)
    app_token = "P9khbt7CGaOsAEsm3DCcbIutn0R"
    table_id = "tblRAk9tsnRsZBKM"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    # 尝试新建记录只包含基础文本字段
    print("准备写入极简数据以测试基础写入权限...")
    url_records = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
    payload = {"fields": {"序号": "123"}}
    
    res = requests.post(url_records, headers=headers, json=payload)
    print("响应:", res.json())
    
    # 如果还是 Forbidden，可能需要申请这篇知识库文档底层的“多维表格 (Advanced Bitable)”权限
    print("提示：如果是 91403 Forbidden，说明依然是权限不足。请确认：")
    print("1. 你是否勾选了 `bitable:app` (编辑多维表格)")
    print("2. 你是否点击了【创建版本】并【申请发布】，并且该版本已经上线通过审核。")
    print("3. 如果这篇文档在某个受限的 Wiki 空间内，可能还需勾选 `drive:wiki` 相关编辑与更新权限。")

if __name__ == "__main__":
    debug_forbidden()
