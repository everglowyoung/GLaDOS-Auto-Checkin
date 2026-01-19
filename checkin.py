import os
import json
import time
import random
import requests
from pypushdeer import PushDeer

# ================= 配置区 =================
# 强制使用 .cloud 域名
BASE_URL = "https://glados.cloud" 
CHECKIN_URL = f"{BASE_URL}/api/user/checkin"
STATUS_URL = f"{BASE_URL}/api/user/status"

HEADERS_BASE = {
    # 关键点：Origin 和 Referer 必须严格等于 https://glados.cloud
    "origin": BASE_URL,
    "referer": f"{BASE_URL}/console/checkin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "content-type": "application/json;charset=UTF-8",
    "accept": "application/json, text/plain, */*",
}

# 现在的 token 建议依然使用 glados.one
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
    except:
        return {}

def main():
    sckey = os.getenv("SENDKEY", "")
    cookies_env = os.getenv("COOKIES", "")
    
    # 支持 & 或 换行符 分隔
    if "&" in cookies_env:
        cookies = [c.strip() for c in cookies_env.split("&") if c.strip()]
    else:
        cookies = [c.strip() for c in cookies_env.split("\n") if c.strip()]

    if not cookies:
        print("❌ 未检测到 COOKIES")
        return

    session = requests.Session()
    ok = fail = repeat = 0
    lines = []

    for idx, cookie in enumerate(cookies, 1):
        # 清理 cookie 中的空格和换行
        current_cookie = cookie.replace(' ', '').replace('\n', '').replace('\r', '')
        headers = dict(HEADERS_BASE)
        headers["cookie"] = current_cookie

        email = "Unknown"
        days = "-"
        status = "未知"

        try:
            # 1. 签到请求
            # 注意：这里必须用 json.dumps，确保格式严格
            checkin_resp = session.post(
                CHECKIN_URL,
                headers=headers,
                data=json.dumps(PAYLOAD),
                timeout=TIMEOUT,
            )
            
            res_json = safe_json(checkin_resp)
            msg = res_json.get("message", "No Response")
            
            if "got" in msg.lower():
                ok += 1
                status = "✅ 成功"
            elif "repeat" in msg.lower() or "already" in msg.lower():
                repeat += 1
                status = "🔁 已签到"
            else:
                fail += 1
                status = f"❌ 失败({msg})"

            # 2. 获取状态
            time.sleep(2) 
            status_resp = session.get(STATUS_URL, headers=headers, timeout=TIMEOUT)
            status_data = safe_json(status_resp).get("data", {})
            email = status_data.get("email", email)
            if status_data.get("leftDays") is not None:
                days = f"{int(float(status_data['leftDays']))} 天"

        except Exception as e:
            fail += 1
            status = f"❌ 异常"
            print(f"账号 {idx} 出错: {e}")

        res_line = f"{idx}. {email} | {status} | 剩余:{days}"
        lines.append(res_line)
        print(res_line)
        
        if idx < len(cookies):
            time.sleep(random.uniform(3, 8))

    # 推送
    title = f"GLaDOS 签到: 成功{ok} 失败{fail}"
    push(sckey, title, "\n".join(lines))

if __name__ == "__main__":
    main()
