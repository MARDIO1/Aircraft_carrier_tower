import os
import requests
import json
from dotenv import load_dotenv

def get_tenant_access_token(app_id, app_secret):
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    payload = {
        "app_id": app_id,
        "app_secret": app_secret
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == 0:
            print("✅ 成功获取 飞书 Tenant Access Token!")
            return data.get("tenant_access_token")
        else:
            print(f"❌ 获取 Token 失败, 错误码: {data.get('code')}, 信息: {data.get('msg')}")
            return None
    else:
        print(f"❌ 请求失败, HTTP 状态码: {response.status_code}")
        return None

if __name__ == "__main__":
    load_dotenv()
    
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    
    if not app_id or not app_secret:
        print("❌ 未在 .env 文件中找到 FEISHU_APP_ID 或 FEISHU_APP_SECRET！")
    else:
        print("正在请求飞书 API 获取授权 Token...")
        get_tenant_access_token(app_id, app_secret)
