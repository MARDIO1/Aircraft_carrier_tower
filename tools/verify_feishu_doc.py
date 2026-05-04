import os
import requests
from dotenv import load_dotenv
import json

def verify_feishu_doc():
    load_dotenv()
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    wiki_token = os.getenv("FEISHU_WIKI_TOKEN") or "FbB7weqTBiZlMiko0FhcGqwBnRf"

    print("1. 获取飞书 Tenant Access Token...")
    auth_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    auth_res = requests.post(auth_url, json={"app_id": app_id, "app_secret": app_secret})
    
    if auth_res.status_code != 200 or auth_res.json().get("code") != 0:
        print("❌ 获取 Token 失败：", auth_res.json())
        return
        
    token = auth_res.json().get("tenant_access_token")

    print("\n2. 测试访问 Wiki 表格节点...")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    # 获取 Wiki 节点信息
    wiki_url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?token={wiki_token}"
    wiki_res = requests.get(wiki_url, headers=headers)
    data = wiki_res.json()
    
    if data.get("code") == 0:
        print("✅ 成功连上目标文档！机器人已具备权限。")
        node = data.get("data", {}).get("node", {})
        print(f"文档类型: {node.get('obj_type')}")
        print(f"底层真实 Token: {node.get('obj_token')}")
    else:
        print(f"❌ 访问该表格失败！(如果没有权限通常会报错 13012 或提示未授权)")
        print(f"错误码: {data.get('code')}")
        print(f"错误信息: {data.get('msg')}")

if __name__ == "__main__":
    verify_feishu_doc()
