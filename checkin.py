import requests
import json
import os
import time
import logging
import datetime
from pypushdeer import PushDeer

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def send_pushdeer(token, title, msg):
    """使用 PushDeer 发送通知（按照版本 2 逻辑实现）"""
    if not token:
        logger.warning("SENDKEY (PushDeer Key) 未设置，跳过通知发送")
        return None
    
    try:
        logger.info("正在通过 PushDeer 发送通知...")
        push_deer = PushDeer(pushkey=token)
        # PushDeer 默认发送 text 格式，desp 支持 markdown/多行文本
        result = push_deer.send_text(title, desp=msg)
        logger.info("PushDeer 通知发送尝试完成")
        return result
    except Exception as e:
        logger.error(f"PushDeer 发送失败: {e}")
        return None

def perform_glados_checkin(cookie, check_in_url, status_url, headers_template, payload):
    """执行单个账号的签到操作（完全保留版本 1 的深度解析逻辑）"""
    try:
        headers = headers_template.copy()
        headers['cookie'] = cookie
        
        # 执行签到
        logger.info("开始执行签到...")
        checkin = requests.post(
            check_in_url, 
            headers=headers, 
            data=json.dumps(payload),
            timeout=30
        )
        
        # 获取账号状态
        logger.info("获取账号状态...")
        state = requests.get(
            status_url, 
            headers={k: v for k, v in headers.items() if k != 'content-type'},
            timeout=30
        )
        
        result = {
            'checkin_success': False,
            'status_success':  False,
            'email': '',
            'points': 0,
            'leftdays': 0,
            'message_status': '未知错误',
            'check_result': '',
            'points_change': 0
        }
        
        # 处理签到结果
        if checkin.status_code == 200:
            result['checkin_success'] = True
            try:
                checkin_data = checkin.json()
                result['check_result'] = checkin_data.get('message', '')
                
                checkin_list = checkin_data.get('list', [])
                if checkin_list and len(checkin_list) > 0:
                    if "Checkin Repeats!" in result['check_result']:
                        result['points_change'] = 0
                    else:
                        result['points_change'] = int(float(checkin_list[0].get('change', 0)))
                    result['points'] = int(float(checkin_list[0].get('balance', 0)))
                else: 
                    if "Checkin!  Got" in result['check_result']:
                        try:
                            points_str = result['check_result'].split("Got ")[1].split(" points")[0]
                            result['points_change'] = int(points_str)
                        except:
                            result['points_change'] = 1
                    else:
                        result['points_change'] = 0
                logger.info(f"签到响应: {result['check_result']}")
            except Exception as e:
                logger.error(f"解析失败: {e}")
        
        # 处理状态查询（获取天数）
        if state.status_code == 200:
            result['status_success'] = True
            try:
                state_data = state.json()
                data = state_data.get('data', {})
                result['leftdays'] = int(float(data.get('leftDays', 0)))
                result['email'] = data.get('email', 'unknown')
                if result['points'] == 0:
                    result['points'] = int(float(data.get('points', 0)))
            except:
                result['email'] = 'parse_error'
        
        # 判定状态
        if result['checkin_success']:
            msg = result['check_result']
            if "Checkin!  Got" in msg:
                result['message_status'] = f"签到成功，点数 +{result['points_change']}"
                return result, 'success'
            elif "Checkin Repeats!" in msg:
                result['message_status'] = "重复签到，明天再来"
                return result, 'repeat'
        
        result['message_status'] = "签到失败"
        return result, 'fail'
            
    except Exception as e:
        logger.error(f"异常: {e}")
        return {'checkin_success': False, 'message_status': str(e)}, 'fail'

def get_beijing_time():
    """获取北京时间（UTC+8）"""
    utc_now = datetime.datetime.utcnow()
    beijing_time = utc_now + datetime.timedelta(hours=8)
    return beijing_time.strftime("%Y/%m/%d %H:%M:%S")

if __name__ == '__main__':
    logger.info("开始执行 GLaDOS 签到脚本 (PushDeer 增强版)")
    
    # 获取环境变量
    sckey = os.environ.get("SENDKEY", "")
    cookies_env = os.environ.get("COOKIES", "")
    
    if cookies_env:
        cookies = [c.strip() for c in cookies_env.split("&") if c.strip()]
    else:
        cookies = []

    if cookies:
        logger.info(f"找到 {len(cookies)} 个账号")
        
        success, fail, repeats = 0, 0, 0
        context = ""
        account_results = []

        # 接口配置
        api_endpoints = [{
            'checkin': 'https://glados.cloud/api/user/checkin',
            'status': 'https://glados.cloud/api/user/status',
            'origin': 'https://glados.cloud'
        }]
        
        useragent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
        payload = {'token': 'glados.cloud'}
        
        for i, cookie in enumerate(cookies):
            logger.info(f"正在处理第 {i+1} 个账号...")
            
            # 执行签到逻辑
            headers_template = {
                'Accept': 'application/json, text/plain, */*',
                'Content-Type': 'application/json;charset=UTF-8',
                'Origin': api_endpoints[0]['origin'],
                'User-Agent': useragent
            }
            
            result, status = perform_glados_checkin(
                cookie, api_endpoints[0]['checkin'], api_endpoints[0]['status'], headers_template, payload
            )
            
            # 统计
            if status == 'success': success += 1
            elif status == 'repeat': repeats += 1
            else: fail += 1
            
            account_results.append(result)
            
            # 账号间随机延迟，模拟真人行为（结合了版本 2 的优点）
            if i < len(cookies) - 1:
                time.sleep(2)

        # 构造详细通知内容（保留版本 1 的美化格式）
        time_str = get_beijing_time()
        for i, res in enumerate(account_results):
            account_context = f"--- 账号 {i+1} 签到结果 ---\n"
            if res.get('checkin_success'):
                if res['points_change'] > 0:
                    account_context += f"积分变化: +{res['points_change']}\n"
                elif "Repeat" in res.get('check_result', ''):
                    account_context += "积分变化: +0 (重复签到)\n"
                
                account_context += f"当前余额: {res.get('points', 0)}\n"
            else:
                account_context += f"签到结果: {res.get('message_status')}\n"
                
            if res.get('status_success'):
                account_context += f"剩余天数: {res.get('leftdays')}天\n"
            else:
                account_context += "剩余天数: 获取失败\n"
            
            account_context += f"签到时间: {time_str}\n"
            if i < len(account_results) - 1:
                account_context += "\n"
            context += account_context

        # 构造标题
        if len(cookies) > 1:
            title = f"GLaDOS签到: 成功{success}, 失败{fail}, 重复{repeats}"
        else:
            title = account_results[0]['message_status'] if account_results else "签到结束"

        # 发送 PushDeer 通知
        send_pushdeer(sckey, title, context)
        
    else:
        logger.error("未找到有效的 COOKIES 环境变量")
        send_pushdeer(sckey, "GLaDOS 签到失败", "未找到 COOKIES，请检查配置")

    logger.info("脚本执行完成")
