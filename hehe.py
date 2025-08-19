import logging
import time
import asyncio
import tkinter as tk
from tkinter import ttk, messagebox, TclError
from datetime import datetime
from urllib.parse import quote_plus
import json
import os
import threading
import requests
from telegram import Bot
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler
import pystray
from PIL import Image, ImageDraw
import webbrowser
import ctypes

# Fix DPI scaling for Windows
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    pass

# === CẤU HÌNH ===
CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "TELEGRAM_TOKEN": "7413526182:AAHbqSltL84gIp3xL60B2RKtu5_zbXk1C-8",
    "CHAT_ID": -4788707953,
    "CHECK_INTERVAL_MINUTES": 30,
    "AUTO_START": True,
    "WINDOW_GEOMETRY": "1500x1000+100+100"
}
NOTIFIED_FILE = "notified_biddings.json"
BIDDINGS_FILE = "biddings.json"

# === SETUP LOGGING ===
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# === Các hàm tiện ích ===
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Lỗi khi lưu cấu hình: {e}")

def load_notified_biddings():
    if os.path.exists(NOTIFIED_FILE):
        try:
            with open(NOTIFIED_FILE, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_notified_biddings(notified_set):
    try:
        with open(NOTIFIED_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(notified_set), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Lỗi khi lưu file notified_biddings: {e}")

def save_biddings(biddings):
    try:
        with open(BIDDINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(biddings, f, ensure_ascii=False, indent=2)
        logger.info(f"Đã lưu {len(biddings)} gói thầu vào {BIDDINGS_FILE}")
    except Exception as e:
        logger.error(f"Lỗi khi lưu file biddings: {e}")

def get_chrome_options():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    return options

def build_bidding_url():
    today = datetime.now().strftime("%d/%m/%Y")
    base_url = "https://dauthau.asia/thongbao/moithau/?"
    params = [
        "q=Chi%E1%BA%BFu+s%C3%A1ng",
        "type_search=1",
        "type_info=1",
        "type_info3=1",
        f"sfrom={quote_plus('05/08/2025')}",
        f"sto={quote_plus(today)}",
        "is_advance=0",
        "is_province=0",
        "is_kqlcnt=0",
        "type_choose_id=0",
        "type_choose_id=0",
        "search_idprovincekq=1",
        "search_idprovince_khtt=1",
        "goods_2=0",
        "searchkind=0",
        "type_view_open=0",
        "sl_nhathau=0",
        "sl_nhathau_cgtt=0",
        "search_idprovince=1",
        "type_org=1",
        "goods=0",
        "cat=0",
        "keyword_id_province=0",
        "oda=-1",
        "khlcnt=0",
        "search_rq_province=-1",
        "search_rq_province=1",
        "rq_form_value=0",
        "searching=1"
    ]
    url = base_url + "&".join(params)
    logger.info(f"URL kiểm tra: {url}")
    return url

def check_new_biddings():
    logger.info("Bắt đầu kiểm tra gói thầu mới...")
    notified = load_notified_biddings()
    logger.info(f"Đã có {len(notified)} gói thầu được thông báo trước đó")
    options = get_chrome_options()
    driver = None
    new_biddings = []
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        url = build_bidding_url()
        logger.info("Đang truy cập trang web...")
        driver.get(url)
        time.sleep(3)
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CLASS_NAME, "bidding-code"))
            )
            logger.info("Trang web đã load thành công, bắt đầu thu thập dữ liệu...")
        except:
            logger.warning("Không tìm thấy element gói thầu - có thể trang chưa load xong")
            return []
        soup = BeautifulSoup(driver.page_source, "html.parser")
        rows = soup.find_all("tr")
        logger.info(f"Tìm thấy {len(rows)} hàng dữ liệu để xử lý")
        for row in rows:
            try:
                code_tag = row.select_one("span.bidding-code")
                title_tag = row.select_one("td[data-column='Gói thầu'] a")
                post_date_tag = row.select_one("td[data-column='Ngày đăng tải']")
                close_date_tag = row.select_one("td[data-column='Ngày đóng thầu']")
                org_tag = row.select_one("td[data-column='Bên mời thầu']")
                if code_tag and title_tag and post_date_tag:
                    code = code_tag.text.strip()
                    title = title_tag.get_text(strip=True)
                    link = "https://dauthau.asia" + title_tag["href"] if title_tag.get("href") else ""
                    post_date = post_date_tag.get_text(strip=True)
                    close_date = close_date_tag.get_text(strip=True) if close_date_tag else "Chưa có thông tin"
                    org = org_tag.get_text(strip=True) if org_tag else "Không rõ"
                    if code not in notified and code and title:
                        logger.info(f"🆕 Phát hiện gói thầu mới: {code}")
                        new_biddings.append({
                            'code': code,
                            'title': title,
                            'post_date': post_date,
                            'close_date': close_date,
                            'link': link,
                            'org': org,
                            'status': 'Mới'
                        })
                        notified.add(code)
            except Exception as e:
                logger.warning(f"Lỗi khi xử lý hàng: {e}")
                continue
        save_notified_biddings(notified)
        logger.info(f"✅ Kết thúc kiểm tra: Tìm thấy {len(new_biddings)} gói thầu mới")
        return new_biddings
    except Exception as e:
        logger.error(f"Lỗi kiểm tra gói thầu: {e}")
        return []
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

def format_bidding_message(biddings):
    if not biddings:
        return "ℹ️ Không có gói thầu mới trong lần kiểm tra này."
    message = f"🔔 **PHÁT HIỆN {len(biddings)} GÓI THẦU MỚI**\n\n"
    for i, bidding in enumerate(biddings[:5], 1):
        message += f"**{i}. 🆔 {bidding['code']}**\n"
        title = bidding['title'][:120] + "..." if len(bidding['title']) > 120 else bidding['title']
        message += f"📦 **{title}**\n"
        message += f"🏢 **Bên mời thầu:** {bidding['org']}\n"
        message += f"📅 **Ngày đăng:** {bidding['post_date']}\n"
        message += f"⏰ **Ngày đóng thầu:** {bidding['close_date']}\n"
        if bidding['link']:
            message += f"🔗 [Xem chi tiết]({bidding['link']})\n"
        message += "\n" + "─"*40 + "\n\n"
    if len(biddings) > 5:
        message += f"📋 *...và còn {len(biddings) - 5} gói thầu khác nữa*\n\n"
    now = datetime.now().strftime("%H:%M:%S - %d/%m/%Y")
    message += f"🕐 *Cập nhật lúc: {now}*"
    return message

async def send_notification(message):
    config = load_config()
    try:
        bot = Bot(config["TELEGRAM_TOKEN"])
        await bot.send_message(
            chat_id=config["CHAT_ID"],
            text=message,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        logger.info("Đã gửi thông báo Telegram thành công")
    except Exception as e:
        logger.error(f"Lỗi gửi thông báo Telegram: {e}")

class ModernCard:
    @staticmethod
    def create(parent, width=300, height=150, bg='#ffffff', shadow=True):
        container = tk.Frame(parent, bg=parent['bg'])
        if shadow:
            shadow_frame = tk.Frame(container, bg='#d1d5db', height=height+4, width=width+4)
            shadow_frame.place(x=4, y=4)
        card = tk.Frame(container, bg=bg, height=height, width=width, relief='flat', bd=1)
        card.place(x=0, y=0)
        container.configure(width=width+8, height=height+8)
        container.pack_propagate(False)
        return container, card

class ModernButton:
    @staticmethod
    def create(parent, text, command=None, style='primary', width=150, height=50):
        styles = {
            'primary': {'bg': '#2196F3', 'fg': 'white', 'hover': '#1976D2'},
            'success': {'bg': '#4CAF50', 'fg': 'white', 'hover': '#388E3C'},
            'danger': {'bg': '#F44336', 'fg': 'white', 'hover': '#D32F2F'},
            'warning': {'bg': '#FF9800', 'fg': 'white', 'hover': '#F57C00'},
            'secondary': {'bg': '#6C757D', 'fg': 'white', 'hover': '#545B62'}
        }
        style_config = styles.get(style, styles['primary'])
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=style_config['bg'],
            fg=style_config['fg'],
            font=('Segoe UI', 12, 'bold'),
            border=0,
            relief='flat',
            width=width//10,
            height=height//25,
            cursor='hand2'
        )
        def on_enter(e):
            button.configure(bg=style_config['hover'])
        def on_leave(e):
            button.configure(bg=style_config['bg'])
        button.bind('<Enter>', on_enter)
        button.bind('<Leave>', on_leave)
        return button

class ModernApp:
    def __init__(self, root):
        self.root = root
        self.setup_window()
        self.setup_variables()
        self.create_interface()
        self.load_initial_data()
        self.update_time()
        if self.config.get("AUTO_START", False):
            self.root.after(2000, self.start_bot)

    def setup_window(self):
        self.root.title("🤖 Bot Theo Dõi Gói Thầu 2025")
        self.root.configure(bg='#f8fafc')
        try:
            self.root.iconbitmap('icon.ico')
        except:
            pass
        self.config = load_config()
        try:
            self.root.geometry(self.config["WINDOW_GEOMETRY"])
        except:
            self.root.geometry("1500x1000+100+100")
        self.root.minsize(1200, 800)

    def setup_variables(self):
        self.scheduler = None
        self.is_running = False
        self.biddings = []
        self.last_check_time = "Chưa kiểm tra"
        self.total_biddings = 0
        self.is_minimized = False

    def show_custom_notification(self, message, biddings):
        try:
            logger.info("Chuẩn bị hiển thị thông báo tùy chỉnh")
            
            # Tạo popup window
            popup = tk.Toplevel(self.root)
            popup.overrideredirect(True)
            popup.configure(bg='#ffffff')
            
            # Đặt kích thước cố định cho popup
            popup_width = 400
            popup_height = 200
            
            # Tính toán vị trí hiển thị (góc dưới bên phải màn hình)
            screen_width = popup.winfo_screenwidth()
            screen_height = popup.winfo_screenheight()
            x = screen_width - popup_width - 20
            y = screen_height - popup_height - 100
            
            popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
            
            # Tạo frame chính với border
            main_frame = tk.Frame(
                popup, 
                bg='#ffffff', 
                relief='solid', 
                bd=2,
                highlightbackground='#e5e7eb',
                highlightthickness=1
            )
            main_frame.pack(fill='both', expand=True, padx=2, pady=2)
            
            # Header với gradient effect (simulate bằng màu background)
            header_frame = tk.Frame(main_frame, bg='#3b82f6', height=50)
            header_frame.pack(fill='x')
            header_frame.pack_propagate(False)
            
            # Icon và title
            title_frame = tk.Frame(header_frame, bg='#3b82f6')
            title_frame.pack(expand=True, fill='both')
            
            title_label = tk.Label(
                title_frame,
                text="🔔 THÔNG BÁO GÓI THẦU",
                bg='#3b82f6',
                fg='#ffffff',
                font=('Segoe UI', 14, 'bold')
            )
            title_label.pack(expand=True)
            
            # Content area
            content_frame = tk.Frame(main_frame, bg='#ffffff')
            content_frame.pack(fill='both', expand=True, padx=20, pady=15)
            
            # Hiển thị thông tin chính
            if biddings and len(biddings) > 0:
                main_text = f"Phát hiện {len(biddings)} gói thầu mới!"
                detail_text = f"• {biddings[0]['title'][:60]}..." if len(biddings[0]['title']) > 60 else f"• {biddings[0]['title']}"
            else:
                main_text = message
                detail_text = ""
            
            # Label thông báo chính
            main_label = tk.Label(
                content_frame,
                text=main_text,
                bg='#ffffff',
                fg='#059669',
                font=('Segoe UI', 12, 'bold'),
                wraplength=350
            )
            main_label.pack(pady=(10, 5))
            
            # Label chi tiết (nếu có)
            if detail_text:
                detail_label = tk.Label(
                    content_frame,
                    text=detail_text,
                    bg='#ffffff',
                    fg='#6b7280',
                    font=('Segoe UI', 10),
                    wraplength=350
                )
                detail_label.pack(pady=5)
            
            # Thời gian
            time_text = f"⏰ {datetime.now().strftime('%H:%M:%S - %d/%m/%Y')}"
            time_label = tk.Label(
                content_frame,
                text=time_text,
                bg='#ffffff',
                fg='#9ca3af',
                font=('Segoe UI', 9)
            )
            time_label.pack(pady=(5, 10))
            
            # Nút đóng
            close_frame = tk.Frame(content_frame, bg='#ffffff')
            close_frame.pack(pady=(5, 0))
            
            close_btn = tk.Button(
                close_frame,
                text="✖ Đóng",
                command=popup.destroy,
                bg='#ef4444',
                fg='#ffffff',
                font=('Segoe UI', 10, 'bold'),
                relief='flat',
                bd=0,
                padx=20,
                pady=8,
                cursor='hand2'
            )
            close_btn.pack()
            
            # Hover effects cho nút đóng
            def on_close_enter(e):
                close_btn.configure(bg='#dc2626')
            def on_close_leave(e):
                close_btn.configure(bg='#ef4444')
            
            close_btn.bind('<Enter>', on_close_enter)
            close_btn.bind('<Leave>', on_close_leave)
            
            # Đưa popup lên trên cùng
            popup.lift()
            popup.attributes('-topmost', True)
            
            # Hiệu ứng fade-in
            popup.attributes("-alpha", 0.0)
            def fade_in(alpha=0.0):
                try:
                    alpha += 0.1
                    if alpha <= 1.0 and popup.winfo_exists():
                        popup.attributes("-alpha", alpha)
                        popup.after(50, lambda: fade_in(alpha))
                except tk.TclError:
                    pass  # Window đã bị destroy
            
            # Hiệu ứng fade-out sau 8 giây
            def fade_out_delayed():
                try:
                    if popup.winfo_exists():
                        fade_out()
                except tk.TclError:
                    pass
            
            def fade_out(alpha=1.0):
                try:
                    alpha -= 0.05
                    if alpha > 0 and popup.winfo_exists():
                        popup.attributes("-alpha", alpha)
                        popup.after(50, lambda: fade_out(alpha))
                    elif popup.winfo_exists():
                        popup.destroy()
                except tk.TclError:
                    pass  # Window đã bị destroy
            
            # Bắt đầu hiệu ứng
            popup.after(100, fade_in)
            popup.after(8000, fade_out_delayed)  # Tự động đóng sau 8 giây
            
            # Cho phép click để đóng
            def close_on_click(event):
                popup.destroy()
            
            popup.bind('<Button-1>', close_on_click)
            main_frame.bind('<Button-1>', close_on_click)
            
            # Force update để đảm bảo hiển thị
            popup.update_idletasks()
            popup.update()
            
            logger.info("Đã hiển thị thông báo tùy chỉnh thành công")
            
        except Exception as e:
            logger.error(f"Lỗi hiển thị thông báo tùy chỉnh: {e}")
            # Fallback notification
            try:
                messagebox.showinfo(
                    "Thông báo gói thầu", 
                    f"Có {len(biddings)} gói thầu mới!" if biddings else message
                )
            except Exception as e2:
                logger.error(f"Lỗi fallback notification: {e2}")

    def create_interface(self):
        main_container = tk.Frame(self.root, bg='#f8fafc')
        main_container.pack(fill='both', expand=True, padx=0, pady=0)
        self.create_header(main_container)
        self.create_content_area(main_container)

    def create_header(self, parent):
        header = tk.Frame(parent, bg='#1e293b', height=100)
        header.pack(fill='x', padx=0, pady=0)
        header.pack_propagate(False)
        header_content = tk.Frame(header, bg='#1e293b')
        header_content.pack(fill='both', expand=True, padx=40, pady=20)
        left_frame = tk.Frame(header_content, bg='#1e293b')
        left_frame.pack(side='left', fill='y')
        title = tk.Label(
            left_frame,
            text="🤖 Bot Theo Dõi Gói Thầu",
            bg='#1e293b',
            fg='#ffffff',
            font=('Segoe UI', 24, 'bold')
        )
        title.pack(anchor='w')
        self.status_label = tk.Label(
            left_frame,
            text="● Trạng thái: Đã dừng",
            bg='#1e293b',
            fg='#94a3b8',
            font=('Segoe UI', 14)
        )
        self.status_label.pack(anchor='w', pady=(5, 0))
        right_frame = tk.Frame(header_content, bg='#1e293b')
        right_frame.pack(side='right', fill='y')
        self.time_label = tk.Label(
            right_frame,
            text="",
            bg='#1e293b',
            fg='#ffffff',
            font=('Segoe UI', 20, 'bold')
        )
        self.time_label.pack(anchor='e')
        self.date_label = tk.Label(
            right_frame,
            text="",
            bg='#1e293b',
            fg='#94a3b8',
            font=('Segoe UI', 12)
        )
        self.date_label.pack(anchor='e', pady=(5, 0))

    def create_content_area(self, parent):
        canvas = tk.Canvas(parent, bg='#f8fafc', highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient='vertical', command=canvas.yview)
        self.scrollable_frame = tk.Frame(canvas, bg='#f8fafc')
        self.scrollable_frame.bind(
            '<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all'))
        )
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self.create_dashboard()
        self.create_control_panel()
        self.create_config_section()
        self.create_biddings_section()

    def create_dashboard(self):
        dashboard_container = tk.Frame(self.scrollable_frame, bg='#f8fafc')
        dashboard_container.pack(fill='x', padx=40, pady=30)
        title = tk.Label(
            dashboard_container,
            text="📊 Thống Kê Tổng Quan",
            bg='#f8fafc',
            fg='#1e293b',
            font=('Segoe UI', 18, 'bold')
        )
        title.pack(anchor='w', pady=(0, 20))
        stats_container = tk.Frame(dashboard_container, bg='#f8fafc')
        stats_container.pack(fill='x')
        self.create_stat_card(stats_container, "📈 Tổng Gói Thầu", "0", "#2196F3", 0)
        self.create_stat_card(stats_container, "🆕 Mới Hôm Nay", "0", "#4CAF50", 1)
        self.create_stat_card(stats_container, "🕐 Kiểm Tra Cuối", "Chưa kiểm tra", "#FF9800", 2)
        self.create_stat_card(stats_container, "🌐 Kết Nối", "Offline", "#9C27B0", 3)

    def create_stat_card(self, parent, title, value, color, column):
        card_container = tk.Frame(parent, bg='#f8fafc')
        card_container.grid(row=0, column=column, padx=15, pady=10, sticky='ew')
        parent.grid_columnconfigure(column, weight=1)
        card = tk.Frame(
            card_container,
            bg='#ffffff',
            relief='flat',
            bd=0,
            width=280,
            height=120
        )
        card.pack(padx=5, pady=5)
        card.pack_propagate(False)
        card.configure(highlightbackground='#e2e8f0', highlightthickness=1)
        header_frame = tk.Frame(card, bg='#ffffff')
        header_frame.pack(fill='x', padx=20, pady=(20, 5))
        title_label = tk.Label(
            header_frame,
            text=title,
            bg='#ffffff',
            fg='#64748b',
            font=('Segoe UI', 12, 'bold')
        )
        title_label.pack(anchor='w')
        value_label = tk.Label(
            card,
            text=value,
            bg='#ffffff',
            fg=color,
            font=('Segoe UI', 24, 'bold')
        )
        value_label.pack(padx=20, pady=(0, 20), anchor='w')
        if column == 0:
            self.total_stat_label = value_label
        elif column == 1:
            self.new_today_stat_label = value_label
        elif column == 2:
            self.last_check_stat_label = value_label
        elif column == 3:
            self.connection_stat_label = value_label

    def create_control_panel(self):
        control_container = tk.Frame(self.scrollable_frame, bg='#f8fafc')
        control_container.pack(fill='x', padx=40, pady=30)
        title = tk.Label(
            control_container,
            text="🎮 Điều Khiển Bot",
            bg='#f8fafc',
            fg='#1e293b',
            font=('Segoe UI', 18, 'bold')
        )
        title.pack(anchor='w', pady=(0, 20))
        card = tk.Frame(control_container, bg='#ffffff', relief='flat', bd=0)
        card.pack(fill='x', pady=10)
        card.configure(highlightbackground='#e2e8f0', highlightthickness=1)
        buttons_frame = tk.Frame(card, bg='#ffffff')
        buttons_frame.pack(fill='x', padx=30, pady=30)
        self.start_btn = ModernButton.create(
            buttons_frame, "🚀 BẬT BOT", self.start_bot, 'success'
        )
        self.start_btn.pack(side='left', padx=(0, 20))
        self.stop_btn = ModernButton.create(
            buttons_frame, "⏹️ TẮT BOT", self.stop_bot, 'danger'
        )
        self.stop_btn.pack(side='left', padx=20)
        self.stop_btn.configure(state='disabled')
        self.check_btn = ModernButton.create(
            buttons_frame, "🔍 KIỂM TRA NGAY", self.check_now, 'primary'
        )
        self.check_btn.pack(side='left', padx=20)
        self.refresh_btn = ModernButton.create(
            buttons_frame, "🔄 TẢI LẠI", self.refresh_data, 'warning'
        )
        self.refresh_btn.pack(side='left', padx=20)
        self.status_text = tk.Label(
            buttons_frame,
            text="Sẵn sàng - Nhấn 'Bật Bot' để bắt đầu theo dõi",
            bg='#ffffff',
            fg='#64748b',
            font=('Arial', 12)
        )
        self.status_text.pack(side='right', padx=20)

    def create_config_section(self):
        config_container = tk.Frame(self.scrollable_frame, bg='#f8fafc')
        config_container.pack(fill='x', padx=40, pady=30)
        title = tk.Label(
            config_container,
            text="⚙️ Cấu Hình Bot",
            bg='#f8fafc',
            fg='#1e293b',
            font=('Arial', 18, 'bold')
        )
        title.pack(anchor='w', pady=(0, 20))
        card = tk.Frame(config_container, bg='#ffffff', relief='flat', bd=0)
        card.pack(fill='x', pady=10)
        card.configure(highlightbackground='#e2e8f0', highlightthickness=1)
        form_frame = tk.Frame(card, bg='#ffffff')
        form_frame.pack(fill='x', padx=30, pady=30)
        self.create_config_field(form_frame, "Telegram Bot Token:", "token", show_password=True, row=0)
        self.create_config_field(form_frame, "Chat ID:", "chat_id", row=1)
        self.create_config_field(form_frame, "Khoảng thời gian kiểm tra (phút):", "interval", row=2)
        auto_frame = tk.Frame(form_frame, bg='#ffffff')
        auto_frame.grid(row=3, column=0, columnspan=2, sticky='w', pady=15)
        self.auto_start_var = tk.BooleanVar(value=self.config.get("AUTO_START", False))
        auto_check = tk.Checkbutton(
            auto_frame,
            text="Tự động chạy bot khi khởi động",
            variable=self.auto_start_var,
            bg='#ffffff',
            font=('Arial', 12),
            fg='#374151'
        )
        auto_check.pack(anchor='w')
        save_btn = ModernButton.create(
            form_frame, "💾 LƯU CẤU HÌNH", self.save_config, 'primary'
        )
        save_btn.grid(row=4, column=1, sticky='e', pady=20)
        form_frame.grid_columnconfigure(1, weight=1)

    def create_config_field(self, parent, label_text, field_name, show_password=False, row=0):
        label = tk.Label(
            parent,
            text=label_text,
            bg='#ffffff',
            fg='#374151',
            font=('Arial', 12, 'bold')
        )
        label.grid(row=row, column=0, sticky='w', pady=15, padx=(0, 20))
        entry = tk.Entry(
            parent,
            font=('Arial', 12),
            bg='#f9fafb',
            fg='#374151',
            relief='flat',
            bd=5,
            width=40,
            show='*' if show_password else ''
        )
        entry.grid(row=row, column=1, sticky='ew', pady=15)
        if field_name == "token":
            entry.insert(0, self.config["TELEGRAM_TOKEN"])
            self.token_entry = entry
        elif field_name == "chat_id":
            entry.insert(0, str(self.config["CHAT_ID"]))
            self.chat_id_entry = entry
        elif field_name == "interval":
            entry.insert(0, str(self.config["CHECK_INTERVAL_MINUTES"]))
            self.interval_entry = entry

    def create_biddings_section(self):
        biddings_container = tk.Frame(self.scrollable_frame, bg='#f8fafc')
        biddings_container.pack(fill='both', expand=True, padx=40, pady=30)
        title = tk.Label(
            biddings_container,
            text="📋 Danh Sách Gói Thầu Mới Nhất",
            bg='#f8fafc',
            fg='#1e293b',
            font=('Arial', 18, 'bold')
        )
        title.pack(anchor='w', pady=(0, 20))
        table_card = tk.Frame(biddings_container, bg='#ffffff', relief='flat', bd=0)
        table_card.pack(fill='both', expand=True, pady=10)
        table_card.configure(highlightbackground='#e2e8f0', highlightthickness=1)
        tree_frame = tk.Frame(table_card, bg='#ffffff')
        tree_frame.pack(fill='both', expand=True, padx=20, pady=20)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            "Modern.Treeview",
            background="#ffffff",
            foreground="#374151",
            rowheight=35,
            fieldbackground="#ffffff",
            borderwidth=0,
            relief="flat"
        )
        style.configure(
            "Modern.Treeview.Heading",
            background="#f8fafc",
            foreground="#1e293b",
            font=('Arial', 11, 'bold'),
            borderwidth=1,
            relief="solid"
        )
        style.map(
            "Modern.Treeview",
            background=[('selected', '#dbeafe')],
            foreground=[('selected', '#1e40af')]
        )
        columns = ('code', 'title', 'org', 'post_date', 'close_date', 'status')
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show='headings',
            style="Modern.Treeview",
            height=15
        )
        self.tree.heading('code', text='Mã Gói Thầu')
        self.tree.heading('title', text='Tên Gói Thầu')
        self.tree.heading('org', text='Bên Mời Thầu')
        self.tree.heading('post_date', text='Ngày Đăng')
        self.tree.heading('close_date', text='Ngày Đóng Thầu')
        self.tree.heading('status', text='Trạng Thái')
        self.tree.column('code', width=150, anchor='center')
        self.tree.column('title', width=400)
        self.tree.column('org', width=250)
        self.tree.column('post_date', width=120, anchor='center')
        self.tree.column('close_date', width=120, anchor='center')
        self.tree.column('status', width=100, anchor='center')
        v_scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        self.tree.bind('<Double-1>', self.open_bidding_link)

    def update_time(self):
        now = datetime.now()
        self.time_label.config(text=now.strftime("%H:%M:%S"))
        days = ['Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy', 'Chủ Nhật']
        weekday = days[now.weekday()]
        self.date_label.config(text=f"{weekday}, {now.strftime('%d/%m/%Y')}")
        self.root.after(1000, self.update_time)

    def load_initial_data(self):
        try:
            notified = load_notified_biddings()
            self.total_stat_label.config(text=str(len(notified)))
            self.connection_stat_label.config(text="Online", fg="#4CAF50")
            if os.path.exists(BIDDINGS_FILE):
                with open(BIDDINGS_FILE, 'r', encoding='utf-8') as f:
                    self.biddings = json.load(f)
                    self.update_biddings_display()
        except Exception as e:
            logger.error(f"Lỗi load dữ liệu: {e}")

    def update_biddings_display(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for bidding in self.biddings:
            status = bidding.get('status', 'N/A')
            title = bidding.get('title', 'N/A')
            if len(title) > 50:
                title = title[:50] + '...'
            org = bidding.get('org', 'N/A')
            if len(org) > 30:
                org = org[:30] + '...'
            item = self.tree.insert('', 'end', values=(
                bidding.get('code', 'N/A'),
                title,
                org,
                bidding.get('post_date', 'N/A'),
                bidding.get('close_date', 'N/A'),
                status
            ))
            if status == 'Mới':
                self.tree.set(item, 'status', '🆕 Mới')
            elif status == 'Đã xem':
                self.tree.set(item, 'status', '👁️ Đã xem')

    def open_bidding_link(self, event):
        try:
            item = self.tree.selection()[0]
            index = self.tree.index(item)
            if index < len(self.biddings) and self.biddings[index].get('link'):
                webbrowser.open(self.biddings[index]['link'])
                self.biddings[index]['status'] = 'Đã xem'
                self.update_biddings_display()
                save_biddings(self.biddings)
        except (IndexError, KeyError):
            pass

    def start_bot(self):
        if not self.is_running:
            try:
                self.scheduler = BackgroundScheduler()
                interval = int(self.interval_entry.get())
                self.scheduler.add_job(
                    self.auto_check_job,
                    'interval',
                    minutes=interval
                )
                self.scheduler.start()
                self.is_running = True
                self.status_label.config(text="● Trạng thái: Đang chạy", fg="#4CAF50")
                self.start_btn.configure(state='disabled')
                self.stop_btn.configure(state='normal')
                self.status_text.config(text=f"Bot đang hoạt động - Kiểm tra mỗi {interval} phút")
                logger.info("Bot đã được bật")
                messagebox.showinfo("Thành công", "Bot đã được bật và bắt đầu theo dõi!")
            except Exception as e:
                logger.error(f"Lỗi khi bật bot: {e}")
                messagebox.showerror("Lỗi", f"Không thể bật bot: {str(e)}")

    def stop_bot(self):
        if self.is_running:
            try:
                if self.scheduler:
                    self.scheduler.shutdown()
                self.is_running = False
                self.status_label.config(text="● Trạng thái: Đã dừng", fg="#F44336")
                self.start_btn.configure(state='normal')
                self.stop_btn.configure(state='disabled')
                self.status_text.config(text="Bot đã dừng - Nhấn 'Bật Bot' để tiếp tục")
                logger.info("Bot đã được tắt")
                messagebox.showinfo("Thành công", "Bot đã được dừng!")
            except Exception as e:
                logger.error(f"Lỗi khi tắt bot: {e}")
                messagebox.showerror("Lỗi", f"Không thể tắt bot: {str(e)}")

    def check_now(self):
        self.status_text.config(text="Đang kiểm tra gói thầu mới...")
        self.root.update()
        threading.Thread(target=self.run_check_now, daemon=True).start()

    def run_check_now(self):
        try:
            new_biddings = check_new_biddings()
            self.root.after(0, lambda: self.handle_check_result(new_biddings))
        except Exception as e:
            logger.error(f"Lỗi kiểm tra: {e}")
            self.root.after(0, lambda: self.status_text.config(text=f"Lỗi: {str(e)}"))

    def handle_check_result(self, new_biddings):
        now = datetime.now().strftime("%H:%M:%S")
        self.last_check_stat_label.config(text=now)
        if new_biddings:
            self.new_today_stat_label.config(text=str(len(new_biddings)))
            self.biddings = new_biddings + self.biddings
            self.update_biddings_display()
            self.status_text.config(text=f"✅ Tìm thấy {len(new_biddings)} gói thầu mới!")
            message = format_bidding_message(new_biddings)
            threading.Thread(
                target=lambda: asyncio.run(send_notification(message)),
                daemon=True
            ).start()
            notification_message = f"Có {len(new_biddings)} gói thầu mới"
            self.root.after(0, lambda: self.show_custom_notification(notification_message, new_biddings))
            messagebox.showinfo("Thành công", f"Tìm thấy {len(new_biddings)} gói thầu mới!")
            save_biddings(self.biddings)
        else:
            self.status_text.config(text="ℹ️ Không có gói thầu mới")
            messagebox.showinfo("Thông báo", "Không có gói thầu mới trong lần kiểm tra này.")
        notified = load_notified_biddings()
        self.total_stat_label.config(text=str(len(notified)))

    def refresh_data(self):
        self.status_text.config(text="Đang tải lại dữ liệu...")
        self.root.update()
        try:
            self.load_initial_data()
            self.status_text.config(text="✅ Đã tải lại dữ liệu thành công")
        except Exception as e:
            logger.error(f"Lỗi tải lại: {e}")
            self.status_text.config(text=f"❌ Lỗi tải lại: {str(e)}")

    def save_config(self):
        try:
            geometry = f"{self.root.winfo_width()}x{self.root.winfo_height()}+{self.root.winfo_x()}+{self.root.winfo_y()}"
            self.config = {
                "TELEGRAM_TOKEN": self.token_entry.get(),
                "CHAT_ID": int(self.chat_id_entry.get()),
                "CHECK_INTERVAL_MINUTES": int(self.interval_entry.get()),
                "AUTO_START": self.auto_start_var.get(),
                "WINDOW_GEOMETRY": geometry
            }
            save_config(self.config)
            self.status_text.config(text="✅ Đã lưu cấu hình thành công!")
            messagebox.showinfo("Thành công", "Đã lưu cấu hình!")
        except ValueError as e:
            messagebox.showerror("Lỗi", "Vui lòng kiểm tra lại các giá trị số!")
        except Exception as e:
            logger.error(f"Lỗi lưu cấu hình: {e}")
            messagebox.showerror("Lỗi", f"Không thể lưu cấu hình: {str(e)}")

    def auto_check_job(self):
        logger.info(f"=== Bắt đầu kiểm tra tự động: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')} ===")
        try:
            new_biddings = check_new_biddings()
            self.root.after(0, lambda: self.handle_auto_check_result(new_biddings))
            if new_biddings:
                message = format_bidding_message(new_biddings)
                asyncio.run(send_notification(message))
                notification_message = f"Có {len(new_biddings)} gói thầu mới"
                self.root.after(0, lambda: self.show_custom_notification(notification_message, new_biddings))
        except Exception as e:
            logger.error(f"Lỗi kiểm tra tự động: {e}")
            self.root.after(0, lambda: self.status_text.config(text=f"❌ Lỗi kiểm tra tự động: {str(e)}"))
        logger.info("=== Kết thúc kiểm tra tự động ===")

    def handle_auto_check_result(self, new_biddings):
        now = datetime.now().strftime("%H:%M:%S")
        self.last_check_stat_label.config(text=now)
        if new_biddings:
            self.new_today_stat_label.config(text=str(len(new_biddings)))
            self.biddings = new_biddings + self.biddings
            self.update_biddings_display()
            self.status_text.config(text=f"🔄 Kiểm tra tự động: Tìm thấy {len(new_biddings)} gói thầu mới!")
            save_biddings(self.biddings)
        else:
            self.status_text.config(text=f"🔄 Kiểm tra tự động: Không có gói thầu mới ({now})")
        notified = load_notified_biddings()
        self.total_stat_label.config(text=str(len(notified)))

def setup_system_tray(app):
    try:
        import pystray
        from PIL import Image, ImageDraw
        image = Image.new('RGB', (64, 64), color='#2196F3')
        draw = ImageDraw.Draw(image)
        draw.rectangle((16, 16, 48, 48), fill='white')
        draw.text((20, 25), "BT", fill='#2196F3')
        def show_window(icon, item):
            app.is_minimized = False
            app.root.deiconify()
            icon.stop()
        def quit_app(icon, item):
            if app.is_running:
                app.stop_bot()
            icon.stop()
            app.root.destroy()
        menu = pystray.Menu(
            pystray.MenuItem("Hiển thị", show_window),
            pystray.MenuItem("Thoát", quit_app)
        )
        icon = pystray.Icon("Bot Theo Dõi", image, "Bot Theo Dõi Gói Thầu", menu)
        def hide_to_tray():
            try:
                app.is_minimized = True
                app.root.withdraw()
                app.root.after(0, lambda: icon.run())
                logger.info("Đã thu nhỏ ứng dụng vào khay hệ thống")
            except Exception as e:
                logger.error(f"Lỗi khi thu nhỏ vào khay hệ thống: {e}")
                messagebox.showerror("Lỗi", "Không thể thu nhỏ vào khay hệ thống. Ứng dụng sẽ đóng.")
                app.root.destroy()
        return hide_to_tray
    except ImportError:
        logger.warning("Thư viện pystray không được cài đặt. Chức năng khay hệ thống bị vô hiệu hóa.")
        return None

def main():
    try:
        root = tk.Tk()
        app = ModernApp(root)
        hide_to_tray = setup_system_tray(app)
        def on_closing():
            if app.is_running:
                if hide_to_tray and messagebox.askokcancel(
                    "Thu nhỏ",
                    "Bot đang chạy. Bạn có muốn thu nhỏ vào khay hệ thống không?"
                ):
                    hide_to_tray()
                else:
                    app.stop_bot()
                    root.destroy()
            else:
                root.destroy()
        root.protocol("WM_DELETE_WINDOW", on_closing)
        root.update_idletasks()
        width = 1500
        height = 1000
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f'{width}x{height}+{x}+{y}')
        print("🚀 Khởi động Bot Theo Dõi Gói Thầu 2025")
        print("✨ Giao diện hiện đại đã sẵn sàng!")
        print("⚙️ Cấu hình bot và nhấn 'Bật Bot' để bắt đầu")
        root.mainloop()
    except Exception as e:
        logger.error(f"Lỗi khởi động: {e}")
        messagebox.showerror("Lỗi", f"Không thể khởi động ứng dụng:\n{str(e)}")

if __name__ == '__main__':
    main()