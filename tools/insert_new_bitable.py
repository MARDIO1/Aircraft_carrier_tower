"""
插入数据到飞书多维表格（新表格，通过 Wiki 节点解析）。

支持作为独立脚本或 import 调用。
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv
from datetime import datetime

# ── 新表格标识 ──
WIKI_TOKEN = "MDqhwja48izCo6koEhkc26yanId"
TABLE_ID = "tblhDfegHWMG2w8n"


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    res = requests.post(url, json={"app_id": app_id, "app_secret": app_secret})
    return res.json().get("tenant_access_token")


def resolve_app_token(wiki_token: str, headers: dict) -> str:
    """通过 Wiki 节点解析获取真实的 Bitable App Token。"""
    wiki_url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?token={wiki_token}"
    wiki_res = requests.get(wiki_url, headers=headers).json()
    if wiki_res.get("code") != 0:
        raise RuntimeError(f"获取Wiki节点失败: {wiki_res}")
    node = wiki_res.get("data", {}).get("node", {})
    app_token = node.get("obj_token")
    if not app_token:
        raise RuntimeError(f"Wiki节点无 obj_token: {node}")
    return app_token


def read_local_json(file_name: str) -> str:
    """读取项目根目录下的 JSON 文件，返回字符串。"""
    path = os.path.join(os.path.dirname(__file__), "..", file_name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "未找到文件"


def sync_to_feishu(
    *,
    grid_count: float = 0,
    distance: float = 0,
    fan_speed: int = 1500,
) -> dict:
    """
    向飞书多维表格写入一条打表记录（新表格，通过 Wiki 节点解析）。

    参数：
        grid_count: 镖架格数
        distance:   距离 (m)
        fan_speed:  风扇转速

    返回：
        {"success": bool, "logs": str, "error": str}
    """
    load_dotenv()
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")

    token = get_tenant_access_token(app_id, app_secret)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }

    logs: list[str] = []

    # 1. 解析 Wiki 节点获取真实的 App Token
    logs.append(f"解析 Wiki 节点: {WIKI_TOKEN}")
    try:
        app_token = resolve_app_token(WIKI_TOKEN, headers)
        logs.append(f"App Token: {app_token}")
    except RuntimeError as e:
        return {"success": False, "logs": "\n".join(logs), "error": str(e)}

    # 2. 获取表格字段
    logs.append(f"获取字段: app={app_token} table={TABLE_ID}")
    url_fields = (
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}"
        f"/tables/{TABLE_ID}/fields"
    )
    res_fields = requests.get(url_fields, headers=headers).json()
    if res_fields.get("code") != 0:
        return {"success": False, "logs": str(res_fields), "error": "获取字段失败"}

    field_list = res_fields.get("data", {}).get("items", [])
    field_names = [f["field_name"] for f in field_list]
    logs.append(f"字段列表: {field_names}")

    # 3. 读取本地参数
    pid_params = read_local_json("pid_params.json")
    feedforward_params = read_local_json("feedforward_params.json")
    jacobian_params = read_local_json("jacobian_params.json")
    servo_params = read_local_json("servo_params.json")
    surface_limit_params = read_local_json("surface_limit_params.json")

    # 4. 构造要写入的字段
    record_fields: dict[str, str] = {}

    if "日期" in field_names:
        record_fields["日期"] = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    if "序号" in field_names:
        record_fields["序号"] = f"AI-{datetime.now().strftime('%H%M%S')}"

    # ── 参数数据 ──
    if "pid参数" in field_names:
        record_fields["pid参数"] = pid_params
    if "舵面前馈" in field_names:
        record_fields["舵面前馈"] = feedforward_params
    if "雅可比矩阵" in field_names:
        record_fields["雅可比矩阵"] = jacobian_params

    # ★ 新增：伺服参数 → "初始舵面" 列
    if "初始舵面" in field_names:
        record_fields["初始舵面"] = servo_params

    # ★ 新增：限幅参数 → "限幅和need" 列
    if "限幅和need" in field_names:
        record_fields["限幅和need"] = surface_limit_params

    # ── 格数 / 距离 / 风扇 ──
    if "镖架格数" in field_names:
        record_fields["镖架格数"] = str(grid_count)
    if "距离" in field_names:
        record_fields["距离"] = str(distance)
    if "风扇动力" in field_names:
        record_fields["风扇动力"] = str(fan_speed)

    logs.append(f"写入字段: {json.dumps(record_fields, ensure_ascii=False)}")

    # 5. 写入飞书
    url_records = (
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}"
        f"/tables/{TABLE_ID}/records"
    )
    payload = {"fields": record_fields}
    res = requests.post(url_records, headers=headers, json=payload)

    if res.status_code == 200 and res.json().get("code") == 0:
        logs.append("[OK] 成功写入一条数据到飞书多维表格！")
        return {"success": True, "logs": "\n".join(logs), "error": ""}
    else:
        err = json.dumps(res.json(), ensure_ascii=False)
        logs.append(f"[ERR] 写入失败: {err}")
        return {"success": False, "logs": "\n".join(logs), "error": err}


if __name__ == "__main__":
    # CLI 使用: python tools/insert_new_bitable.py [格数] [距离] [风扇转速]
    grid = float(sys.argv[1]) if len(sys.argv) > 1 else 0
    dist = float(sys.argv[2]) if len(sys.argv) > 2 else 0
    fan = int(sys.argv[3]) if len(sys.argv) > 3 else 1500
    result = sync_to_feishu(grid_count=grid, distance=dist, fan_speed=fan)
    print(result.get("logs", ""))
    if not result.get("success"):
        sys.exit(1)
