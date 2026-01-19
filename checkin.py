import os
import json
import time
import random
import requests
from pypushdeer import PushDeer

# ================= 配置区 =================
# 建议使用 glados.network 或 glados.cloud，目前这两个接口较为稳定
BASE_URL = "https://glados.cloud" 
CHECKIN_URL = f"{BASE_URL}/api/user/checkin"
STATUS_URL = f"{BASE_URL}/api/user/status"

HEADERS_BASE = {
    "origin": BASE_URL,
    "referer": f"{BASE_URL}/console/checkin",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "content-type": "application/json;charset=UTF-8",
}

PAYLOAD = {"token": "glados.one"}
TIMEOUT = 30
# ==========================================

def push(sckey: str, title: str, text: str):
    if sckey:
        try:
            PushDeer(pushkey=sckey).send_text(title, desp=text)
        except Exception as e:
            print(f"推送失败: {e}")

def safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return {}

def main():
    # 从 GitHub Secrets 获取变量
    sckey = os.getenv("SENDKEY", "")
    cookies_env = os.getenv("COOKIES", "")
    
    # 兼容换行符或 & 分隔的多个 cookie
    if "&" in cookies_env:
        cookies = [c.strip() for c in cookies_env.split("&") if c.strip()]
    else:
        cookies = [c.strip() for c in cookies_env.split("\n") if c.strip()]

    if not cookies:
        msg = "❌ 未检测到 COOKIES，请检查 GitHub Secrets 配置"
        print(msg)
        push(sckey, "GLaDOS 签到失败", msg)
        return

    session = requests.Session()
    ok = fail = repeat = 0
    lines = []

    for idx, cookie in enumerate(cookies, 1):
        headers = dict(HEADERS_BASE)
        headers["cookie"] = cookie

        email = "Unknown"
        points = "-"
        days = "-"
        status = "未知"

        try:
            # 1. 尝试签到
            checkin_resp = session.post(
                CHECKIN_URL,
                headers=headers,
                data=json.dumps(PAYLOAD),
                timeout=TIMEOUT,
            )
            
            # 打印调试信息（GitHub Actions 日志可见）
            print(f"账号 {idx} 签到返回码: {checkin_resp.status_code}")
            
            res_json = safe_json(checkin_resp)
            msg = res_json.get("message", "无返回消息")
            msg_lower = msg.lower()

            if "got" in msg_lower:
                ok += 1
                points = res_json.get("points", "-")
                status = "✅ 成功"
            elif "repeat" in msg_lower or "already" in msg_lower:
                repeat += 1
                status = "🔁 已签到"
            else:
                fail += 1
                status = f"❌ 失败({msg})"

            # 2. 获取账号状态 (获取邮箱和剩余天数)
            time.sleep(1) # 稍微停顿
            status_resp = session.get(STATUS_URL, headers=headers, timeout=TIMEOUT)
            status_json = safe_json(status_resp).get("data") or {}
            
            email = status_json.get("email", email)
            if status_json.get("leftDays") is not None:
                days = f"{int(float(status_json['leftDays']))} 天"

        except Exception as e:
            fail += 1
            status = f"❌ 异常"
            print(f"账号 {idx} 运行出错: {e}")

        result_line = f"{idx}. {email} | {status} | 剩余:{days}"
        lines.append(result_line)
        print(result_line)
        
        # 账号之间随机延迟，防止触发频率限制
        if idx < len(cookies):
            time.sleep(random.uniform(2, 5))

    # 统计结果
    title = f"GLaDOS 签到: 成功{ok} 失败{fail} 重复{repeat}"
    content = "\n".join(lines)
    push(sckey, title, content)

if __name__ == "__main__":
    main()
