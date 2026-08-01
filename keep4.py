#!/usr/bin/env python3
"""
سكربت للحفاظ على نشاط مشروع Replit مع دعم الكوكيز
"""

import sys
import time
import http.cookiejar
import re
import os
import signal
import threading
import json
import requests
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

# ==================== إعدادات Replit ====================
REPLIT_PROJECT_URL = "https://replit.com/@sednyu9sidni/v2ray-telegram-bot-fixedzip"
REPLIT_EMAIL = "sednyu9@gmail.com"
REPLIT_PASSWORD = "karimdeka92"
COOKIE_FILE = "cookies_replit.txt"
REFRESH_INTERVAL = 30  # ثواني

# ==================== إعدادات عامة ====================
KEEP_ALIVE_PORT = 8080

# متغيرات عامة
last_webview_url = None
last_status = None
last_update_time = None
running = True


class KeepAliveHandler(BaseHTTPRequestHandler):
    """معالج طلبات HTTP لخدمة Keep Alive"""
    
    def do_GET(self):
        """معالجة طلبات GET"""
        parsed = urlparse(self.path)
        
        if parsed.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta http-equiv="refresh" content="30">
                <title>Replit Keep Alive</title>
                <style>
                    body {{ font-family: Arial; text-align: center; padding: 50px; background: #0a0a0a; color: #00ff88; }}
                    h1 {{ font-size: 2.5em; }}
                    .status {{ font-size: 1.5em; margin: 20px 0; }}
                    .time {{ color: #888; font-size: 0.8em; }}
                    .success {{ color: #00ff88; }}
                    .error {{ color: #ff4444; }}
                    .info {{ color: #666; font-size: 0.9em; margin: 10px 0; }}
                    .box {{ background: #1a1a2e; padding: 20px; border-radius: 10px; margin: 20px 0; border: 1px solid #333; }}
                    .box-title {{ color: #00ccff; font-size: 1.2em; margin-bottom: 10px; }}
                    .url {{ color: #00ccff; word-break: break-all; }}
                </style>
            </head>
            <body>
                <h1>🚀 Replit Keep Alive</h1>
                <div class="status success">✅ المشروع قيد التشغيل</div>
                <div class="time">آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
                
                <div class="box">
                    <div class="box-title">📂 مشروع Replit</div>
                    <div style="font-size: 0.9em; color: #888;">{REPLIT_PROJECT_URL}</div>
                    <div class="info">📊 الحالة: <span class="success">{last_status or '⏳ جاري التشغيل...'}</span></div>
                    <div class="info">🌐 رابط Webview: <span class="url">{last_webview_url or '⏳ جاري البحث...'}</span></div>
                    <div class="info">⏱️ آخر تحديث: {last_update_time or 'لم يتم التحديث'}</div>
                </div>
                
                <div class="box">
                    <div class="box-title">📋 معلومات</div>
                    <div style="color: #888; font-size: 0.9em; text-align: left; padding: 10px;">
                        <p>✅ يتم تشغيل مشروع Replit تلقائياً</p>
                        <p>🍪 استخدام الكوكيز للحفاظ على الجلسة</p>
                        <p>📁 ملف الكوكيز: {COOKIE_FILE}</p>
                        <p>🔄 التحديث كل {REFRESH_INTERVAL} ثانية</p>
                    </div>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html_content.encode('utf-8'))
            
        elif parsed.path == '/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            status = {
                "status": "running",
                "timestamp": datetime.now().isoformat(),
                "replit": {
                    "project": REPLIT_PROJECT_URL,
                    "webview_url": last_webview_url,
                    "status": last_status,
                    "last_update": last_update_time,
                    "interval": REFRESH_INTERVAL
                }
            }
            self.wfile.write(json.dumps(status).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')
    
    def log_message(self, format, *args):
        pass


def log(msg: str):
    """طباعة رسالة مع الطابع الزمني"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def clean_cookie(cookie):
    """تنظيف الكوكي وإزالة الحقول غير الصالحة لـ Playwright"""
    allowed_fields = ['name', 'value', 'domain', 'path', 'expires', 'httpOnly', 'secure', 'sameSite']
    
    cleaned = {}
    for field in allowed_fields:
        if field in cookie:
            if field == 'expires':
                if isinstance(cookie[field], (int, float)):
                    cleaned[field] = cookie[field]
                elif isinstance(cookie[field], str):
                    try:
                        dt = datetime.fromisoformat(cookie[field].replace('Z', '+00:00'))
                        cleaned[field] = int(dt.timestamp())
                    except:
                        pass
            elif field == 'httpOnly':
                cleaned[field] = bool(cookie[field])
            elif field == 'secure':
                cleaned[field] = bool(cookie[field])
            elif field == 'sameSite':
                if cookie[field] in ['Strict', 'Lax', 'None']:
                    cleaned[field] = cookie[field]
            else:
                cleaned[field] = str(cookie[field])
    
    if 'name' not in cleaned or 'value' not in cleaned:
        return None
    
    if 'domain' in cleaned:
        cleaned['domain'] = cleaned['domain'].lstrip('.')
    
    return cleaned


def save_cookies(cookies):
    """حفظ الكوكيز في ملف"""
    try:
        # تنظيف الكوكيز أولاً
        cleaned_cookies = []
        for cookie in cookies:
            cleaned = clean_cookie(cookie)
            if cleaned:
                cleaned_cookies.append(cleaned)
        
        with open(COOKIE_FILE, 'w') as f:
            json.dump(cleaned_cookies, f, indent=2)
        log(f"✅ تم حفظ {len(cleaned_cookies)} كوكي")
        return True
    except Exception as e:
        log(f"❌ خطأ في حفظ الكوكيز: {e}")
        return False


def load_cookies():
    """تحميل الكوكيز من ملف"""
    if not os.path.exists(COOKIE_FILE):
        log("📂 لا يوجد ملف كوكيز")
        return []
    
    try:
        with open(COOKIE_FILE, 'r') as f:
            cookies = json.load(f)
        log(f"✅ تم تحميل {len(cookies)} كوكي")
        return cookies
    except Exception as e:
        log(f"❌ خطأ في تحميل الكوكيز: {e}")
        return []


def login_to_replit():
    """تسجيل الدخول إلى Replit والحصول على كوكيز جديدة"""
    log("🔑 تسجيل الدخول إلى Replit...")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
            )
            
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            
            page = context.new_page()
            
            log("🌐 فتح صفحة تسجيل الدخول...")
            page.goto("https://replit.com/login", wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            
            # إدخال البريد الإلكتروني
            log("📧 إدخال البريد الإلكتروني...")
            try:
                page.fill('input[type="email"]', REPLIT_EMAIL)
                page.wait_for_timeout(1000)
            except:
                try:
                    page.evaluate(f"""
                        const emailInput = document.querySelector('input[type="email"]');
                        if (emailInput) {{
                            emailInput.value = '{REPLIT_EMAIL}';
                            emailInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        }}
                    """)
                except Exception as e:
                    log(f"⚠️ خطأ في إدخال البريد: {e}")
            
            # إدخال كلمة المرور
            log("🔒 إدخال كلمة المرور...")
            try:
                page.fill('input[type="password"]', REPLIT_PASSWORD)
                page.wait_for_timeout(1000)
            except:
                try:
                    page.evaluate(f"""
                        const passInput = document.querySelector('input[type="password"]');
                        if (passInput) {{
                            passInput.value = '{REPLIT_PASSWORD}';
                            passInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        }}
                    """)
                except Exception as e:
                    log(f"⚠️ خطأ في إدخال كلمة المرور: {e}")
            
            # الضغط على زر تسجيل الدخول
            log("🖱️ الضغط على زر تسجيل الدخول...")
            try:
                page.click('button:has-text("Log in")')
                page.wait_for_timeout(5000)
            except:
                try:
                    page.click('button[type="submit"]')
                    page.wait_for_timeout(5000)
                except:
                    try:
                        page.evaluate("""
                            document.querySelector('button[type="submit"]')?.click();
                        """)
                        page.wait_for_timeout(5000)
                    except Exception as e:
                        log(f"⚠️ خطأ في الضغط على زر تسجيل الدخول: {e}")
            
            # انتظار تحميل الصفحة
            page.wait_for_timeout(5000)
            
            # التحقق من نجاح تسجيل الدخول
            if "/login" in page.url:
                log("❌ فشل تسجيل الدخول")
                browser.close()
                return False
            
            log("✅ تم تسجيل الدخول بنجاح!")
            
            # حفظ الكوكيز
            cookies = context.cookies()
            if cookies:
                save_cookies(cookies)
                browser.close()
                return True
            else:
                log("❌ لم يتم الحصول على كوكيز")
                browser.close()
                return False
    
    except Exception as e:
        log(f"❌ خطأ في تسجيل الدخول: {e}")
        return False


def press_run_button(page):
    """الضغط على زر Run في Replit"""
    log("🔍 جاري البحث عن زر Run...")
    
    for attempt in range(15):
        page.wait_for_timeout(2000)
        
        # قائمة محددات زر Run
        selectors = [
            "button:has-text('Run')",
            "button[aria-label='Run']",
            "button[data-testid='run-button']",
            "button[data-cy='run-button']",
            "button[class*='run']",
            "button:has(svg[viewBox*='play'])",
            "button:has(span:has-text('Run'))",
            "header button:has-text('Run')",
            "[data-testid='run-button']",
            ".run-button",
            "button:has-text('Start')",
            "button[aria-label*='Run' i]"
        ]
        
        # محاولة العثور على زر Run
        for selector in selectors:
            try:
                btn = page.locator(selector).first
                if btn.count() > 0 and btn.is_visible(timeout=1000):
                    btn.click()
                    log(f"✅ تم الضغط على زر Run")
                    page.wait_for_timeout(5000)
                    return True
            except:
                continue
        
        # محاولة JavaScript
        try:
            result = page.evaluate("""
                () => {
                    const buttons = document.querySelectorAll('button');
                    for (let btn of buttons) {
                        const text = (btn.textContent || '').toLowerCase();
                        const label = (btn.getAttribute('aria-label') || '').toLowerCase();
                        if (text.includes('run') || label.includes('run')) {
                            btn.click();
                            return 'clicked';
                        }
                    }
                    return 'not_found';
                }
            """)
            if result == 'clicked':
                log("✅ تم الضغط على زر Run عن طريق JavaScript")
                page.wait_for_timeout(5000)
                return True
        except:
            pass
        
        # التحقق من وجود زر Stop (يعني أن المشروع يعمل)
        try:
            stop_btn = page.locator("button:has-text('Stop')").first
            if stop_btn.count() > 0 and stop_btn.is_visible(timeout=2000):
                log("✅ المشروع قيد التشغيل بالفعل")
                return True
        except:
            pass
        
        # محاولة العثور على زر Run في iframe
        try:
            iframes = page.locator("iframe").all()
            for iframe in iframes:
                try:
                    iframe_content = iframe.content_frame
                    if iframe_content:
                        run_btn = iframe_content.locator("button:has-text('Run')").first
                        if run_btn.count() > 0 and run_btn.is_visible(timeout=1000):
                            run_btn.click()
                            log("✅ تم الضغط على زر Run في iframe")
                            page.wait_for_timeout(5000)
                            return True
                except:
                    continue
        except:
            pass
        
        if attempt < 14:
            log(f"⚠️ محاولة {attempt + 1}/15... إعادة تحميل الصفحة")
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
    
    log("❌ فشل في العثور على زر Run")
    return False


def get_webview_url(page):
    """استخراج رابط Webview من Replit"""
    log("🔍 البحث عن رابط Webview...")
    
    # البحث عن iframe
    try:
        iframes = page.locator("iframe[src*='replit.dev']").all()
        for iframe in iframes:
            src = iframe.get_attribute("src") or ""
            match = re.search(r"https?://[a-f0-9\-]+\.replit\.dev:\d+", src)
            if match:
                url = match.group(0)
                log(f"✅ تم العثور على رابط Webview: {url}")
                return url
    except:
        pass
    
    # البحث في النص
    try:
        body = page.text_content("body") or ""
        matches = re.findall(r"https?://[a-f0-9\-]+\.replit\.dev:\d+", body)
        if matches:
            url = matches[0]
            log(f"✅ تم العثور على رابط Webview: {url}")
            return url
    except:
        pass
    
    # استخدام JavaScript
    try:
        result = page.evaluate("""
            () => {
                const text = document.body.innerText || '';
                const match = text.match(/https?:\\/\\/[a-f0-9\\-]+\\.replit\\.dev:\\d+/);
                if (match) return match[0];
                
                const iframes = document.querySelectorAll('iframe');
                for (let iframe of iframes) {
                    const match = (iframe.src || '').match(/https?:\\/\\/[a-f0-9\\-]+\\.replit\\.dev:\\d+/);
                    if (match) return match[0];
                }
                return null;
            }
        """)
        if result:
            log(f"✅ تم العثور على رابط Webview: {result}")
            return result
    except:
        pass
    
    return None


def run_replit_project():
    """تشغيل مشروع Replit"""
    global last_webview_url, last_status, last_update_time
    
    log("🔄 بدء تشغيل مشروع Replit")
    
    # التحقق من الكوكيز
    cookies = load_cookies()
    if not cookies:
        log("📂 لا توجد كوكيز - جاري تسجيل الدخول...")
        if not login_to_replit():
            log("❌ فشل تسجيل الدخول")
            last_status = "Login Failed"
            last_update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return False
        cookies = load_cookies()
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
            )
            
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # إضافة الكوكيز
            valid_cookies = 0
            for cookie in cookies:
                try:
                    context.add_cookies([cookie])
                    valid_cookies += 1
                except:
                    continue
            
            if valid_cookies == 0:
                log("❌ لا توجد كوكيز صالحة - جاري تسجيل الدخول...")
                browser.close()
                if login_to_replit():
                    return run_replit_project()
                return False
            
            page = context.new_page()
            
            log(f"📂 فتح مشروع Replit")
            page.goto(REPLIT_PROJECT_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
            
            # التحقق من صفحة تسجيل الدخول
            if "/login" in page.url:
                log("❌ الكوكيز منتهية - جاري تسجيل الدخول...")
                browser.close()
                if login_to_replit():
                    return run_replit_project()
                return False
            
            log("✅ تم الدخول إلى مشروع Replit")
            
            # الضغط على زر Run
            if press_run_button(page):
                log("✅ تم تشغيل مشروع Replit")
                last_status = "Running"
            else:
                log("⚠️ فشل في تشغيل المشروع")
                last_status = "Run Failed"
            
            # البحث عن رابط Webview
            webview_url = None
            for attempt in range(8):
                webview_url = get_webview_url(page)
                if webview_url:
                    break
                page.wait_for_timeout(3000)
            
            if webview_url:
                last_webview_url = webview_url
                log(f"🌐 رابط Webview: {webview_url}")
                # حفظ الرابط في ملف
                with open("webview_url.txt", "w") as f:
                    f.write(f"{webview_url}\n")
                    f.write(f"آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            else:
                log("⚠️ لم يتم العثور على رابط Webview")
            
            last_update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            browser.close()
            return True
    
    except Exception as e:
        log(f"❌ خطأ في تشغيل المشروع: {e}")
        last_status = f"Error: {str(e)[:50]}"
        last_update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return False


def keep_alive_request():
    """إرسال طلب للحفاظ على النشاط"""
    global last_status
    
    if not last_webview_url:
        log("⚠️ لا يوجد رابط Webview للحفاظ على النشاط")
        return False
    
    try:
        log(f"🔄 إرسال طلب إلى {last_webview_url}")
        response = requests.get(
            last_webview_url,
            timeout=10,
            allow_redirects=True
        )
        
        if response.status_code == 200:
            log(f"✅ طلب الحفاظ على النشاط ناجح (HTTP {response.status_code})")
            return True
        else:
            log(f"⚠️ استجابة غير متوقعة: {response.status_code}")
            return False
            
    except Exception as e:
        log(f"⚠️ خطأ في طلب الحفاظ على النشاط: {e}")
        return False


def run_keep_alive_server():
    """تشغيل خادم Keep Alive"""
    try:
        server = HTTPServer(('0.0.0.0', KEEP_ALIVE_PORT), KeepAliveHandler)
        log(f"🔌 خادم Keep Alive يعمل على المنفذ {KEEP_ALIVE_PORT}")
        server.serve_forever()
    except Exception as e:
        log(f"⚠️ خطأ في خادم Keep Alive: {e}")


def main():
    """الحلقة الرئيسية"""
    global running
    
    log("🔥 بدء تشغيل خدمة الحفاظ على مشروع Replit")
    log(f"📂 المشروع: {REPLIT_PROJECT_URL}")
    log(f"⏱️ التحديث كل {REFRESH_INTERVAL} ثانية")
    log(f"📁 ملف الكوكيز: {COOKIE_FILE}")
    log(f"🔌 خادم Keep Alive على المنفذ {KEEP_ALIVE_PORT}")
    log("=" * 50)
    
    # تشغيل خادم Keep Alive
    keep_alive_thread = threading.Thread(target=run_keep_alive_server, daemon=True)
    keep_alive_thread.start()
    
    # تشغيل المشروع أول مرة
    log("🔄 تشغيل المشروع لأول مرة...")
    run_replit_project()
    
    # الحلقة الرئيسية
    counter = 0
    while running:
        try:
            # إعادة تشغيل المشروع كل 5 دقائق
            if counter % 10 == 0:  # كل 10 دورات (5 دقائق)
                log("🔄 إعادة تشغيل المشروع...")
                run_replit_project()
            
            # الحفاظ على النشاط
            if last_webview_url:
                keep_alive_request()
            else:
                log("⚠️ لا يوجد رابط Webview - محاولة إعادة التشغيل...")
                run_replit_project()
            
            counter += 1
            
            # الانتظار
            log(f"⏳ الانتظار {REFRESH_INTERVAL} ثانية...")
            for i in range(REFRESH_INTERVAL, 0, -1):
                if i % 10 == 0 or i <= 1:
                    log(f"⏳ {i}s")
                time.sleep(1)
            
            log("🔄 بدء دورة جديدة...")
            print("-" * 50)
            
        except KeyboardInterrupt:
            log("⏹️ تم الإيقاف")
            running = False
            break
        except Exception as e:
            log(f"❌ خطأ: {e}")
            time.sleep(5)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(0))
    main()