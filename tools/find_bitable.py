import os
import requests
from dotenv import load_dotenv

def get_tenant_access_token(app_id, app_secret):
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    res = requests.post(url, json={"app_id": app_id, "app_secret": app_secret})
    return res.json().get("tenant_access_token")

def find_bitable_in_docx():
    load_dotenv()
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    document_id = "EJIHdSJJcoK5wZxlg2FcFiMUnCe" 
    
    token = get_tenant_access_token(app_id, app_secret)
    headers = {"Authorization": f"Bearer {token}"}

    print("正在扫描文档中的多维表格...")
    page_token = ""
    has_more = True
    
    while has_more:
        url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks?page_size=500"
        if page_token:
            url += f"&page_token={page_token}"
            
        res = requests.get(url, headers=headers)
        data = res.json()
        
        if data.get("code") != 0:
            print("读取文档块失败:", data)
            return
            
        items = data.get("data", {}).get("items", [])
        for item in items:
            # block_type 43 是 undefined / bitable (新版可能是别的，通常是 43, 44 等，具体看文档或直接按字符串搜)
            block_type = item.get("block_type")
            if block_type in [43, "bitable", "view"]: # 尝试各种可能
                pass
            
            # 或者直接看有没有 bitable 属性
            if "bitable" in item:
                bitable_token = item["bitable"]["token"]
                print(f"✅ 找到多维表格！Token: {bitable_token}")
                
                # 顺便获取其所有表 (table_id)
                t_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{bitable_token}/tables"
                t_res = requests.get(t_url, headers=headers)
                print("多维表格的Tables信息:", t_res.json())
                return
                
        has_more = data.get("data", {}).get("has_more", False)
        page_token = data.get("data", {}).get("page_token", "")

    print("❌ 未在文档中找到多维表格 (Bitable)。请确认是否真的插入了'多维表格'")

if __name__ == "__main__":
    find_bitable_in_docx()
