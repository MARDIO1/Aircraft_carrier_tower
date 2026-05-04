import os
import requests
from dotenv import load_dotenv
import json

def get_tenant_access_token(app_id, app_secret):
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    res = requests.post(url, json={"app_id": app_id, "app_secret": app_secret})
    return res.json().get("tenant_access_token")

def create_table_in_docx():
    load_dotenv()
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    
    # 之前获取到的底层真实文档 Docx Token
    document_id = "EJIHdSJJcoK5wZxlg2FcFiMUnCe" 
    
    token = get_tenant_access_token(app_id, app_secret)
    if not token:
        print("❌ 获取Token失败")
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }

    # 1. 在文档末尾创建一个 2行 11列 的空表格
    print("正在创建普通表格(Docx)...")
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/children"
    table_payload = {
        "children": [
            {
                "block_type": 31, # Table block
                "table": {
                    "property": {
                        "row_size": 2,
                        "column_size": 11
                    }
                }
            }
        ]
    }
    
    res = requests.post(url, headers=headers, json=table_payload)
    if res.status_code != 200 or res.json().get("code") != 0:
        print("❌ 创建表格失败:", res.json())
        return
        
    print("✅ 表格创建成功！(由于飞书API限制，需要分步填入表头，建议直接在飞书文档内操作。后续会自动追加行)")

if __name__ == "__main__":
    create_table_in_docx()
