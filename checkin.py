import requests
import json
import os
import time
import logging
import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def send_pushdeer(token, title, msg):
    """
    发送 PushDeer 通知
    官网: https://www.pushdeer.com/
    """
    if not token:
        logger.warning("SENDKEY未设置，跳过通知发送")
        return None
        
    url = "https://api2.pushdeer.com/message/push"
    
    # 准备推送数据
    # text: 标题, desp: 内容, type: markdown
    data = {
        "pushkey": token,
        "text": title,
        "desp": msg,
        "type": "markdown"
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    # 重试机制
    for attempt in range(3):
        try:
            logger.info(f"正在通过 PushDeer 发送通知 (第{attempt + 1}次)")
            # PushDeer 建议使用 POST
            r = requests.post(url, data=data, timeout=20, headers=headers)
            res_json = r.json()
            
            # PushDeer 成功返回通常包含 content
            if r.status_code == 200:
                logger.info("PushDeer 通知发送请求已提交")
                print(f"Response: {r.text}")
                return r.text
            else:
                logger.warning(f"PushDeer 返回状态码异常: {r.status_code}")
                
        except Exception as e:
            logger.error(f"PushDeer 发送异常: {e}")
            if attempt < 2:
                time.sleep(2)
                continue
    
    logger.error("所有 PushDeer 发送尝试都失败了")
    return None

def perform_glados_checkin(cookie, check_in_url, status_url, headers_template, payload):
    """执行单个账号的签到操作"""
    try:
        headers = headers_template.copy()
        headers['cookie'] = cookie
        
        # 1. 执行签到
        logger.info("开始执行签到...")
        checkin = requests.post(
            check_in_url, 
            headers=headers, 
            data=json.dumps(payload),
            timeout=30
        )
        
        # 2. 获取账号状态
        logger.info("获取账号状态...")
        state = requests.get(
            status_url, 
            headers={k: v for k, v in headers.items() if k.lower() != 'content-type'},
            timeout=30
        )
        
        result = {
            'checkin_success': False,
            'status_success': False,
            'email': '未知',
            'points': 0,
            'leftdays': 0,
            'message_status': '未知错误',
            'check_result': '',
            'points_change': 0
        }
        
        # 处理签到结果
        if checkin.status_code == 200:
            result['checkin_success'] = True
            checkin_data = checkin.json()
            result['check_result'] = checkin_data.get('message', '')
            
            checkin_list = checkin_data.get('list', [])
            if checkin_list:
                result['points_change'] = int(float(checkin_list[0].get('change', 0)))
                result['points'] = int(float(checkin_list[0].get('balance', 0)))
            else:
                # 备用积分逻辑
                if "Got" in result['check_result']:
                    result['points_change'] = 1
            
            logger.info(f"签到响应: {result['check_result']}")
        
        # 处理状态查询
        if state.status_code == 200:
            result['status_success'] = True
            data = state.json().get('data', {})
            result['leftdays'] = int(float(data.get('leftDays', 0)))
            result['email'] = data.get('email', 'unknown')
            if result['points'] == 0:
                result['points'] = int(float(data.get('points', 0)))

        # 逻辑判定
        if "Checkin! Got" in result['check_result']:
            result['message_status'] = f"成功 (+{result['points_change']})"
            return result, 'success'
        elif "Checkin Repeats!" in result['check_result']:
            result['message_status'] = "重复签到"
            return result, 'repeat'
        else:
            result['message_status'] = "签到异常"
            return result, 'fail'
            
    except Exception as e:
        logger.error(f"处理账号时出现错误: {e}")
        return {'checkin_success': False, 'message_status': f'错误: {str(e)[:20]}'}, 'fail'

def get_beijing_time():
    """获取北京时间"""
    utc_now = datetime.datetime.utcnow()
    beijing_time = utc_now + datetime.timedelta(hours=8)
    return beijing_time.strftime("%Y-%m-%d %H:%M:%S")

if __name__ == '__main__':
    logger.info("=== GLaDOS 自动签到开始 ===")
    
    # 环境变量
    sckey = os.environ.get("SENDKEY", "")
    cookies_env = os.environ.get("COOKIES", "")
    
    if cookies_env:
        cookies = [c.strip() for c in cookies_env.split("&") if c.strip()]
    else:
        logger.error("未找到 COOKIES 环境变量")
        exit()

    success, fail, repeats = 0, 0, 0
    summary_list = []
    
    # GLaDOS 配置
    check_in_url = 'https://glados.cloud/api/user/checkin'
    status_url = 'https://glados.cloud/api/user/status'
    headers_template = {
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json;charset=UTF-8',
        'Origin': 'https://glados.cloud',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    payload = {'token': 'glados.cloud'}

    for i, cookie in enumerate(cookies):
        logger.info(f"处理第 {i+1}/{len(cookies)} 个账号")
        result, status = perform_glados_checkin(cookie, check_in_url, status_url, headers_template, payload)
        
        if status == 'success': success += 1
        elif status == 'repeat': repeats += 1
        else: fail += 1
        
        # 构建当前账号的通知行
        summary_list.append(
            f"- **账号 {i+1}** ({result.get('email', '未知')}): {result['message_status']}, 剩余 {result.get('leftdays', 0)} 天"
        )
        
        if i < len(cookies) - 1:
            time.sleep(2)

    # 统计信息
    title = f"GLaDOS签到: 成{success} 重{repeats} 败{fail}"
    time_str = get_beijing_time()
    
    # 拼接 Markdown 内容（PushDeer 对 Markdown 支持很好）
    content = f"### GLaDOS 签到报告\n**执行时间**: {time_str}\n\n" + "\n".join(summary_list)
    
    print("\n--- 推送内容 ---\n" + content + "\n---------------")

    # 执行推送
    if sckey:
        send_pushdeer(sckey, title, content)
    else:
        logger.info("未设置 SENDKEY，不执行推送")

    logger.info("=== 任务执行完成 ===")
