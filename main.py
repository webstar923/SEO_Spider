import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import webbrowser
import threading
import json
import os
import time
from spider import Spider
from whois_checker import WhoisChecker
from utils import get_domain
from openpyxl import Workbook

SETTINGS_FILE = "settings.json"
PREDEFINED_SITES = {
    "金融庁": "https://www.fsa.go.jp",
    "経済産業省": "https://www.meti.go.jp",
    "日本銀行": "https://www.boj.or.jp",
    "外務省 (安全情報)": "https://www.anzen.mofa.go.jp",
    "外務省 (本サイト)": "https://www.mofa.go.jp",
    "総務省": "https://www.soumu.go.jp",
    "国民生活センター": "https://www.kokusen.go.jp",
    "国連広報センター": "https://www.unic.or.jp",
    "消費者庁": "https://www.caa.go.jp",
    "タウラス・ファイナンシャル": "https://taurus-financial.com",
    "JETRO": "https://www.jetro.go.jp",
    "J-Net21": "https://j-net21.smrj.go.jp",
}

def load_settings():
    default_settings = {
        "api_key": "",
        "crawl_delay": 0.5,
        "max_depth": 3,
        "crawl_resources": {
            "images": True,
            "documents": True,
            "stylesheets": True,
            "scripts": True,
            "media": True,
            "archives": True
        }
    }
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            loaded_settings = json.load(f)
            # Merge with defaults to ensure all settings exist
            return {**default_settings, **loaded_settings}
    return default_settings

def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)

class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.title("設定")
        self.geometry("400x340")
        self.resizable(False, False)
        self.settings = settings
        self.original_settings = settings.copy()
        self.result = None
        
        # Create main frame
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # WHOIS API Key
        ttk.Label(main_frame, text="WHOIS API Key:").grid(row=0, column=0, sticky="w", pady=5)
        self.api_key_var = tk.StringVar(value=settings["api_key"])
        ttk.Entry(main_frame, textvariable=self.api_key_var, width=40).grid(row=0, column=1, sticky="ew", pady=5)

        # WHOIS API Link
        link = tk.Label(main_frame, text="APIキーを取得する", fg="blue", cursor="hand2", font=("Arial", 9, "underline"))
        link.grid(row=1, column=1, sticky="w", pady=(0, 10))
        link.bind("<Button-1>", lambda e: webbrowser.open_new("https://www.api-ninjas.com/pricing"))
        
        # Crawl Delay
        ttk.Label(main_frame, text="クロール間隔 (秒):").grid(row=2, column=0, sticky="w", pady=5)
        self.delay_var = tk.DoubleVar(value=settings["crawl_delay"])
        ttk.Spinbox(main_frame, from_=0.1, to=5.0, increment=0.1, textvariable=self.delay_var, width=10).grid(row=2, column=1, sticky="w", pady=5)
        
        # Max Depth
        ttk.Label(main_frame, text="クロール深度:").grid(row=3, column=0, sticky="w", pady=5)
        self.depth_var = tk.IntVar(value=settings["max_depth"])
        ttk.Spinbox(main_frame, from_=1, to=10, increment=1, textvariable=self.depth_var, width=10).grid(row=3, column=1, sticky="w", pady=5)
        
        # Resource Options
        ttk.Label(main_frame, text="クロール対象:").grid(row=4, column=0, sticky="w", pady=5)
        resource_frame = ttk.Frame(main_frame)
        resource_frame.grid(row=4, column=1, sticky="w", pady=5)
        
        # Create checkboxes for each resource type
        self.resource_vars = {}
        row = 0
        for resource_type in settings["crawl_resources"]:
            var = tk.BooleanVar(value=settings["crawl_resources"][resource_type])
            self.resource_vars[resource_type] = var
            ttk.Checkbutton(resource_frame, text=self._get_resource_label(resource_type), variable=var).grid(row=row, column=0, sticky="w")
            row += 1
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="保存", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="キャンセル", command=self.destroy).pack(side=tk.LEFT, padx=5)
        
        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def _get_resource_label(self, resource_type):
        """Get the Japanese label for a resource type"""
        labels = {
            "images": "画像",
            "documents": "ドキュメント",
            "stylesheets": "スタイルシート",
            "scripts": "スクリプト",
            "media": "メディア",
            "archives": "アーカイブ"
        }
        return labels.get(resource_type, resource_type)
        
    def save(self):
        # Update API key and other settings
        self.settings.update({
            "api_key": self.api_key_var.get(),
            "crawl_delay": self.delay_var.get(),
            "max_depth": self.depth_var.get(),
            "crawl_resources": {
                resource_type: var.get()
                for resource_type, var in self.resource_vars.items()
            }
        })
        save_settings(self.settings)
        self.destroy()
        
    def has_changes(self):
        current = {
            "api_key": self.api_key_var.get(),
            "crawl_delay": self.delay_var.get(),
            "max_depth": self.depth_var.get(),
            "crawl_resources": {
                resource_type: var.get()
                for resource_type, var in self.resource_vars.items()
            }
        }
        return current != self.original_settings

    def close_without_save(self):
        self.destroy()       

    def on_close(self):
        if self.has_changes():
            answer = messagebox.askyesno("変更の保存", "設定が変更されています。保存しますか？")
            # answer = messagebox.askyesnocancel("変更の保存", "設定が変更されています。保存しますか？")
            if answer is None:
                return  # Cancel close
            elif answer:
                self.save()
            else:
                self.close_without_save()
        else:
            self.destroy() 

settings = load_settings()

app = tk.Tk()
app.title("Broken Link & WHOISチェッカー")
app.geometry("1400x800")

# Create menu bar
menubar = tk.Menu(app)
app.config(menu=menubar)

# File menu
file_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="ファイル", menu=file_menu)
file_menu.add_command(label="設定", command=lambda: SettingsWindow(app, settings))
file_menu.add_separator()
file_menu.add_command(label="終了", command=app.quit)

# Top controls
top_frame = tk.Frame(app)
top_frame.pack(pady=10)

# Domain selection
tk.Label(top_frame, text="ウェブサイト選択:").pack(side="left", padx=5)
dropdown = ttk.Combobox(top_frame, values=list(PREDEFINED_SITES.keys()), width=60)
dropdown.pack(side="left", padx=5)

def run_scan():
    global spider, timer_running, start_time, elapsed_time, main_whois
    api_key = settings["api_key"]
    if not api_key:
        messagebox.showerror("エラー", "API Keyを設定してください")
        return

    selected_label = dropdown.get()
    if not selected_label:
        messagebox.showerror("エラー", "サイトを選択してください")
        return
    url = PREDEFINED_SITES[selected_label]

    output_table.delete(*output_table.get_children())
    log_box.delete("1.0", "end")
    status_label.config(text="スキャン中...", fg="blue")
    export_button.config(state="disabled")
    progress.start()

    # Get current resource settings
    current_resources = {
        "images": settings["crawl_resources"].get("images", False),
        "documents": settings["crawl_resources"].get("documents", False),
        "stylesheets": settings["crawl_resources"].get("stylesheets", False),
        "scripts": settings["crawl_resources"].get("scripts", False),
        "media": settings["crawl_resources"].get("media", False),
        "archives": settings["crawl_resources"].get("archives", False)
    }

    spider = Spider(
        base_url=url, 
        log_callback=log,
        max_depth=settings["max_depth"],
        delay=settings["crawl_delay"],
        crawl_resources=current_resources  # Pass the current resource settings
    )
    whois_checker = WhoisChecker(api_key=api_key)
    timer_running = True
    start_time = time.time()
    elapsed_time = 0
    update_timer()

    # Get main domain WHOIS info
    main_domain = get_domain(url)
    main_whois = whois_checker.check_domain(main_domain)
    print("main_whois", main_whois)

    # Start the crawl in a separate thread
    threading.Thread(target=run_scan_thread, args=(url, whois_checker), daemon=True).start()

def pause_scan():
    global spider, timer_running, elapsed_time
    if spider:
        spider.pause()
        timer_running = False
        elapsed_time += int(time.time() - start_time)

def resume_scan():
    global spider, timer_running, start_time
    if spider:
        spider.resume()
        start_time = time.time()
        timer_running = True
        update_timer()

def cancel_scan():
    global spider, timer_running, main_whois, global_whois_checker
    if spider:
        try:
            # Disable all buttons during cancellation
            export_button.config(state="disabled")
            status_label.config(text="キャンセル処理中...", fg="orange")
            app.update()  # Force UI update
            
            # Get results before canceling
            results = spider.cancel()
            timer_running = False
            progress.stop()
            
            # Process the results we managed to collect
            if results:
                seen_domains = {}
                error_count = 0
                for r in results:
                    try:
                        url = r['url']
                        status = r['status']
                        referrer = r['referrer']
                        type_ = r['type']
                        domain = r['domain']
                        depth = r['depth']

                        if type_ == "external":
                            if domain not in seen_domains:
                                if 'global_whois_checker' in globals():
                                    whois = global_whois_checker.check_domain(domain)
                                else:
                                    whois = {"status": "Unknown", "owner": "Unknown"}
                                seen_domains[domain] = whois
                            else:
                                whois = seen_domains[domain]
                        else:
                            whois = main_whois

                        is_error = isinstance(status, int) and status >= 400 or status == "Request Failed"
                        row_text = f"[{error_count + 1}] {url}" if is_error else url
                        row = output_table.insert("", "end", values=(
                            row_text, status, referrer, type_, domain, whois["status"], whois["owner"]
                        ))
                        if is_error:
                            output_table.item(row, tags=("error",))
                            error_count += 1
                    except Exception as e:
                        log(f"Error processing result for {r.get('url', 'unknown')}: {str(e)}")
                        continue

                status_label.config(text=f"キャンセルされました：{len(results)} 件を検査、問題のあるリンク {error_count} 件", fg="red")
                # Only enable export if we have results
                if len(results) > 0:
                    export_button.config(state="normal")
            else:
                status_label.config(text="キャンセルされました（結果なし）", fg="red")
                export_button.config(state="disabled")
        except Exception as e:
            log(f"Error during cancel: {str(e)}")
            status_label.config(text="キャンセル中にエラーが発生しました", fg="red")
            export_button.config(state="disabled")
        finally:
            # Cleanup after processing results
            if spider:
                spider._cleanup()
            
            # Update UI to show final state
            app.update()

def export_to_excel():
    file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
    if not file_path:
        return

    wb = Workbook()
    ws = wb.active
    ws.append(["URL", "Status", "Referrer", "Type", "Domain", "WHOIS Status", "Registrant"])

    for row_id in output_table.get_children():
        ws.append(output_table.item(row_id)["values"])

    wb.save(file_path)
    messagebox.showinfo("保存完了", f"Excelファイルとして保存されました:\n{file_path}")

# Control buttons
tk.Button(top_frame, text="検査開始", command=run_scan).pack(side="left", padx=5)
tk.Button(top_frame, text="一時停止", command=pause_scan).pack(side="left", padx=5)
tk.Button(top_frame, text="再開", command=resume_scan).pack(side="left", padx=5)
tk.Button(top_frame, text="キャンセル", command=cancel_scan).pack(side="left", padx=5)
export_button = tk.Button(top_frame, text="Excelにエクスポート", command=export_to_excel, state="disabled")
export_button.pack(side="left", padx=5)

# Output area
frame = tk.Frame(app)
frame.pack(fill="both", expand=True, padx=10, pady=10)

columns = ("URL", "Status", "Referrer", "Type", "Domain", "WHOIS Status", "Registrant")
output_table = ttk.Treeview(frame, columns=columns, show="headings", height=17)
for col in columns:
    output_table.heading(col, text=col)
    output_table.column(col, width=180 if col == "URL" else 120)

scroll_y = ttk.Scrollbar(frame, orient="vertical", command=output_table.yview)
output_table.configure(yscrollcommand=scroll_y.set)
scroll_y.pack(side="right", fill="y")
output_table.pack(fill="both", expand=True)

output_table.tag_configure("error", background="#ffdddd", font=("Arial", 10, "bold"))

# Log box
log_frame = tk.LabelFrame(app, text="ログ")
log_frame.pack(fill="both", expand=False, padx=20, pady=5)

log_box = tk.Text(log_frame, height=10, wrap="word", bg="#f7f7f7")
log_box.pack(fill="both", expand=True)
log_scroll = ttk.Scrollbar(log_frame, command=log_box.yview)
log_box.configure(yscrollcommand=log_scroll.set)
log_scroll.pack(side="right", fill="y")

def log(message):
    log_box.insert("end", f"{message}\n")
    log_box.see("end")

# Global vars
spider = None
timer_running = False
start_time = 0
elapsed_time = 0

def update_timer():
    if timer_running:
        elapsed = int(time.time() - start_time + elapsed_time)
        timer_label.config(text=f"経過時間: {elapsed} 秒")
        app.after(1000, update_timer)

def start_scan():
    global spider, timer_running, start_time, elapsed_time
    api_key = settings["api_key"]
    if not api_key:
        messagebox.showerror("エラー", "API Keyを設定してください")
        return

    selected_label = dropdown.get()
    if not selected_label:
        messagebox.showerror("エラー", "サイトを選択してください")
        return
    url = PREDEFINED_SITES[selected_label]

    output_table.delete(*output_table.get_children())
    log_box.delete("1.0", "end")
    status_label.config(text="スキャン中...", fg="blue")
    export_button.config(state="disabled")
    progress.start()

    spider = Spider(
        base_url=url, 
        log_callback=log,
        max_depth=settings["max_depth"],
        delay=settings["crawl_delay"],
        crawl_resources=settings["crawl_resources"]
    )
    whois_checker = WhoisChecker(api_key=api_key)
    timer_running = True
    start_time = time.time()
    elapsed_time = 0
    update_timer()

    threading.Thread(target=run_scan, args=(url, whois_checker), daemon=True).start()

def run_scan_thread(url, whois_checker):
    global spider, timer_running, elapsed_time, main_whois, global_whois_checker
    global_whois_checker = whois_checker  # Store whois_checker globally
    spider.crawl(url)
    
    # Wait for the crawl to complete
    while True:
        # Check if any threads are still alive
        with spider.thread_lock:
            active_threads = sum(1 for t in spider.threads if t.is_alive())
            if active_threads == 0:
                break
        time.sleep(1)  # Wait a bit before checking again
    
    # Get the results after crawl is complete
    results = spider.get_results()
    log(f"クロール完了: {len(results)} 件のURLを検査しました")

    seen_domains = {}
    error_count = 0
    for r in results:
        try:
            url = r['url']
            status = r['status']
            referrer = r['referrer']
            type_ = r['type']
            domain = r['domain']
            depth = r['depth']

            if type_ == "external":
                if domain not in seen_domains:
                    whois = whois_checker.check_domain(domain)
                    seen_domains[domain] = whois
                else:
                    whois = seen_domains[domain]
            else:
                whois = main_whois

            is_error = isinstance(status, int) and status >= 400 or status == "Request Failed"
            row_text = f"[{error_count + 1}] {url}" if is_error else url
            row = output_table.insert("", "end", values=(
                row_text, status, referrer, type_, domain, whois["status"], whois["owner"]
            ))
            if is_error:
                output_table.item(row, tags=("error",))
                error_count += 1
        except Exception as e:
            log(f"Error processing result for {r.get('url', 'unknown')}: {str(e)}")
            continue

    timer_running = False
    elapsed_time += int(time.time() - start_time)
    status_label.config(text=f"完了：{len(results)} 件を検査、問題のあるリンク {error_count} 件", fg="green")
    export_button.config(state="normal")
    progress.stop()
    
    # Cleanup after processing results
    if spider:
        spider._cleanup()

# Controls
progress = ttk.Progressbar(app, mode="indeterminate")
progress.pack(fill="x", padx=20, pady=5)

timer_label = tk.Label(app, text="経過時間: 0 秒", anchor="w")
timer_label.pack(fill="x", padx=20)

status_label = tk.Label(app, text="ステータス: 待機中", anchor="w")
status_label.pack(fill="x", padx=20, pady=5)

app.mainloop()
