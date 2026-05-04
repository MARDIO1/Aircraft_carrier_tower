import os
import requests
import json
from dotenv import load_dotenv

def re_auth_and_test():
    """
    检查多维表格底部的文档级分享（Bitable自身的分享设置）
    """
    load_dotenv()
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    
    # 重新获取Token
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    res = requests.post(url, json={"app_id": app_id, "app_secret": app_secret})
    token = res.json().get("tenant_access_token")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }

    # Bitable 的标识
    app_token = "P9khbt7CGaOsAEsm3DCcbIutn0R"
    table_id = "tblRAk9tsnRsZBKM"

    # 第一步：获取 Bitable Meta 信息，看机器人究竟能读到什么程度的主表信息
    print("1. 获取 Bitable 基础信息 (Meta)...")
    url_meta = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}"
    res_meta = requests.get(url_meta, headers=headers)
    print("Meta 响应:", res_meta.json())
    
    # 第二步：尝试增加新的一行，如果 Forbidden，打印最完整的错误头
    print("\n2. 尝试强制写入空行...")
    url_records = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
    payload = {"fields": {}}
    res_post = requests.post(url_records, headers=headers, json=payload)
    print("写入响应:", res_post.json())

if __name__ == "__main__":
    re_auth_and_test()