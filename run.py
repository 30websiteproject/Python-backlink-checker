import threading
import requests
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
from openpyxl import Workbook
import time

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

TIMEOUT = 15

BG_COLOR = "#1a1a2e"
CARD_COLOR = "#16213e"
ACCENT_COLOR = "#0f3460"
TEXT_COLOR = "#e8e8e8"
GREEN = "#4ade80"
RED = "#f87171"
ORANGE = "#fb923c"
BLUE = "#60a5fa"


class BacklinkCheckerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Advanced Backlink Checker")
        self.root.geometry("1100x800")
        self.root.configure(bg=BG_COLOR)

        self.results = []
        self.total = self.good = self.bad = self.cloudflare = 0
        self.lock = threading.Lock()
        self.use_browser = tk.BooleanVar(value=False)
        self.checked_count = 0

        self.setup_styles()
        self.build_ui()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background=BG_COLOR)
        style.configure("Card.TFrame", background=CARD_COLOR)

        style.configure("TLabel", background=BG_COLOR, foreground=TEXT_COLOR, font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=BG_COLOR, foreground=TEXT_COLOR, font=("Segoe UI", 14, "bold"))
        style.configure("Card.TLabel", background=CARD_COLOR, foreground=TEXT_COLOR, font=("Segoe UI", 10))

        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=10)
        style.map("TButton",
                  background=[("active", ACCENT_COLOR), ("!active", ACCENT_COLOR)],
                  foreground=[("active", TEXT_COLOR), ("!active", TEXT_COLOR)])

        style.configure("Accent.TButton", background=GREEN, foreground="#000000")
        style.map("Accent.TButton",
                  background=[("active", "#22c55e"), ("!active", GREEN)])

        style.configure("TCheckbutton", background=CARD_COLOR, foreground=TEXT_COLOR, font=("Segoe UI", 10))
        style.map("TCheckbutton",
                  background=[("active", CARD_COLOR), ("!active", CARD_COLOR)],
                  foreground=[("active", TEXT_COLOR), ("!active", TEXT_COLOR)])

        style.configure("Treeview",
                        background=CARD_COLOR,
                        foreground=TEXT_COLOR,
                        fieldbackground=CARD_COLOR,
                        font=("Segoe UI", 9),
                        rowheight=28)
        style.configure("Treeview.Heading",
                        background=ACCENT_COLOR,
                        foreground=TEXT_COLOR,
                        font=("Segoe UI", 10, "bold"))
        style.map("Treeview",
                  background=[("selected", ACCENT_COLOR)],
                  foreground=[("selected", TEXT_COLOR)])

    def build_ui(self):
        main_frame = ttk.Frame(self.root, style="TFrame")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        header = ttk.Label(main_frame, text="Backlink Checker", style="Header.TLabel")
        header.pack(anchor="w", pady=(0, 15))

        input_container = ttk.Frame(main_frame, style="TFrame")
        input_container.pack(fill="x", pady=(0, 15))

        left_input = ttk.Frame(input_container, style="Card.TFrame")
        left_input.pack(side="left", fill="both", expand=True, padx=(0, 10))

        right_input = ttk.Frame(input_container, style="Card.TFrame")
        right_input.pack(side="right", fill="both", expand=True, padx=(10, 0))

        ttk.Label(left_input, text="Target URLs to find (one per line):", style="Card.TLabel").pack(anchor="w", padx=15, pady=(15, 5))
        self.target_text = tk.Text(left_input, height=6, bg=ACCENT_COLOR, fg=TEXT_COLOR,
                                   insertbackground=TEXT_COLOR, font=("Consolas", 10),
                                   relief="flat", padx=10, pady=10)
        self.target_text.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        ttk.Label(right_input, text="Backlinks to Check (one per line):", style="Card.TLabel").pack(anchor="w", padx=15, pady=(15, 5))
        self.backlink_text = tk.Text(right_input, height=6, bg=ACCENT_COLOR, fg=TEXT_COLOR,
                                     insertbackground=TEXT_COLOR, font=("Consolas", 10),
                                     relief="flat", padx=10, pady=10)
        self.backlink_text.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        control_frame = ttk.Frame(main_frame, style="Card.TFrame")
        control_frame.pack(fill="x", pady=(0, 15))

        inner_control = ttk.Frame(control_frame, style="Card.TFrame")
        inner_control.pack(pady=15, padx=15)

        ttk.Label(inner_control, text="Workers:", style="Card.TLabel").pack(side="left", padx=(0, 5))
        self.worker_entry = tk.Entry(inner_control, width=6, bg=ACCENT_COLOR, fg=TEXT_COLOR,
                                     insertbackground=TEXT_COLOR, font=("Segoe UI", 10),
                                     relief="flat", justify="center")
        self.worker_entry.insert(0, "10")
        self.worker_entry.pack(side="left", padx=(0, 20))

        browser_check = tk.Checkbutton(inner_control, text="Browser Mode (Cloudflare/JS)",
                                       variable=self.use_browser, bg=CARD_COLOR, fg=TEXT_COLOR,
                                       selectcolor=ACCENT_COLOR, activebackground=CARD_COLOR,
                                       activeforeground=TEXT_COLOR, font=("Segoe UI", 10))
        browser_check.pack(side="left", padx=(0, 20))

        self.start_btn = ttk.Button(inner_control, text="Start Checking", command=self.start_check, style="Accent.TButton")
        self.start_btn.pack(side="left", padx=5)

        self.export_btn = ttk.Button(inner_control, text="Export Excel", command=self.export_excel, state="disabled")
        self.export_btn.pack(side="left", padx=5)

        self.clear_btn = ttk.Button(inner_control, text="Clear Results", command=self.clear_results)
        self.clear_btn.pack(side="left", padx=5)

        stats_frame = ttk.Frame(main_frame, style="TFrame")
        stats_frame.pack(fill="x", pady=(0, 10))

        self.stat_cards = {}
        stats_data = [
            ("total", "Total Checked", "0", BLUE),
            ("good", "Contains Target", "0", GREEN),
            ("bad", "No Target Found", "0", RED),
            ("cloudflare", "Cloudflare/Error", "0", ORANGE)
        ]

        for key, label, value, color in stats_data:
            card = ttk.Frame(stats_frame, style="Card.TFrame")
            card.pack(side="left", fill="x", expand=True, padx=5)

            lbl = tk.Label(card, text=label, bg=CARD_COLOR, fg="#a0a0a0", font=("Segoe UI", 9))
            lbl.pack(pady=(10, 0))

            val = tk.Label(card, text=value, bg=CARD_COLOR, fg=color, font=("Segoe UI", 18, "bold"))
            val.pack(pady=(0, 10))

            self.stat_cards[key] = val

        progress_frame = ttk.Frame(main_frame, style="TFrame")
        progress_frame.pack(fill="x", pady=(0, 10))

        self.progress_label = tk.Label(progress_frame, text="", bg=BG_COLOR, fg=TEXT_COLOR, font=("Segoe UI", 9))
        self.progress_label.pack(side="left")

        tree_frame = ttk.Frame(main_frame, style="Card.TFrame")
        tree_frame.pack(fill="both", expand=True)

        cols = ("Backlink", "Status", "Found Targets", "Anchor Text", "Link Type")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings")

        col_widths = {"Backlink": 300, "Status": 100, "Found Targets": 250, "Anchor Text": 200, "Link Type": 100}
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=col_widths.get(c, 150), minwidth=80)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True, padx=(15, 0), pady=15)
        scrollbar.pack(side="right", fill="y", pady=15, padx=(0, 15))

        self.tree.tag_configure("good", foreground=GREEN)
        self.tree.tag_configure("bad", foreground=RED)
        self.tree.tag_configure("cloudflare", foreground=ORANGE)

    def update_stats(self):
        self.stat_cards["total"].config(text=str(self.total))
        self.stat_cards["good"].config(text=str(self.good))
        self.stat_cards["bad"].config(text=str(self.bad))
        self.stat_cards["cloudflare"].config(text=str(self.cloudflare))

    def update_progress(self, current, total):
        self.progress_label.config(text=f"Checking: {current}/{total}")

    def clear_results(self):
        self.tree.delete(*self.tree.get_children())
        self.results.clear()
        self.total = self.good = self.bad = self.cloudflare = 0
        self.update_stats()
        self.progress_label.config(text="")

    def start_check(self):
        backlinks = [i.strip() for i in self.backlink_text.get("1.0", tk.END).splitlines() if i.strip()]
        targets = [i.strip() for i in self.target_text.get("1.0", tk.END).splitlines() if i.strip()]

        if not backlinks or not targets:
            messagebox.showerror("Error", "Please enter both backlinks and at least one target URL")
            return

        try:
            workers = int(self.worker_entry.get())
        except:
            messagebox.showerror("Error", "Invalid workers number")
            return

        if self.use_browser.get() and not SELENIUM_AVAILABLE:
            messagebox.showerror("Error", "Browser mode requires selenium. Please install it first.")
            return

        if self.use_browser.get() and workers > 3:
            workers = 3

        self.tree.delete(*self.tree.get_children())
        self.results.clear()

        self.total = len(backlinks)
        self.good = self.bad = self.cloudflare = 0
        self.checked_count = 0
        self.update_stats()

        self.start_btn.config(state="disabled")
        self.export_btn.config(state="disabled")

        use_browser = self.use_browser.get()

        threading.Thread(
            target=self.run_checker,
            args=(backlinks, targets, workers, use_browser),
            daemon=True
        ).start()

    def create_browser(self):
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        return webdriver.Chrome(options=options)

    def run_checker(self, backlinks, targets, workers, use_browser):
        if use_browser:
            for idx, backlink in enumerate(backlinks):
                self.check_backlink_browser(idx, backlink, targets)
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                for idx, backlink in enumerate(backlinks):
                    executor.submit(self.check_backlink, idx, backlink, targets)

        self.root.after(0, self.display_sorted_results)
        self.root.after(0, lambda: self.start_btn.config(state="normal"))
        self.root.after(0, lambda: self.export_btn.config(state="normal"))
        self.root.after(0, lambda: self.progress_label.config(text="Done!"))

    def display_sorted_results(self):
        self.tree.delete(*self.tree.get_children())
        sorted_results = sorted(self.results, key=lambda x: x[0])
        for result in sorted_results:
            idx, backlink, status, found_str, anchor_str, type_str, http_code = result
            tag = "good" if status == "GOOD" else ("bad" if status == "BAD" else "cloudflare")
            self.tree.insert("", "end", values=(backlink, status, found_str, anchor_str, type_str), tags=(tag,))

    def check_backlink_browser(self, idx, backlink, targets):
        status = ""
        found_targets = []
        anchor_texts = []
        link_types = []
        http_code = ""
        tag = ""

        driver = None
        try:
            driver = self.create_browser()
            driver.set_page_load_timeout(30)
            driver.get(backlink)
            time.sleep(5)

            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")

            for target in targets:
                for a in soup.find_all("a", href=True):
                    if target.lower() in a["href"].lower():
                        found_targets.append(target)
                        anchor = a.get_text(strip=True) or "(No Text)"
                        anchor_texts.append(anchor)
                        rel = a.get("rel", [])
                        link_type = "Nofollow" if "nofollow" in rel else "Dofollow"
                        link_types.append(link_type)
                        break

            if found_targets:
                status = "GOOD"
                tag = "good"
                with self.lock:
                    self.good += 1
            else:
                status = "BAD"
                tag = "bad"
                with self.lock:
                    self.bad += 1

        except Exception as e:
            status = "Error"
            tag = "cloudflare"
            with self.lock:
                self.cloudflare += 1
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

        found_str = ", ".join(found_targets) if found_targets else ""
        anchor_str = ", ".join(anchor_texts) if anchor_texts else ""
        type_str = ", ".join(link_types) if link_types else ""

        with self.lock:
            self.results.append([
                idx, backlink, status, found_str, anchor_str, type_str, http_code
            ])
            self.checked_count += 1
            count = self.checked_count

        self.root.after(0, lambda: self.update_progress(count, self.total))
        self.root.after(0, self.update_stats)

    def check_backlink(self, idx, backlink, targets):
        status = ""
        found_targets = []
        anchor_texts = []
        link_types = []
        http_code = ""
        tag = ""

        try:
            r = requests.get(backlink, headers=HEADERS, timeout=TIMEOUT)
            http_code = r.status_code
            html = r.text.lower()

            if http_code in [403, 429, 503] or "cloudflare" in html or "cf-ray" in html:
                status = "Cloudflare"
                tag = "cloudflare"
                with self.lock:
                    self.cloudflare += 1
            else:
                soup = BeautifulSoup(r.text, "html.parser")

                for target in targets:
                    for a in soup.find_all("a", href=True):
                        if target.lower() in a["href"].lower():
                            found_targets.append(target)
                            anchor = a.get_text(strip=True) or "(No Text)"
                            anchor_texts.append(anchor)
                            rel = a.get("rel", [])
                            link_type = "Nofollow" if "nofollow" in rel else "Dofollow"
                            link_types.append(link_type)
                            break

                if found_targets:
                    status = "GOOD"
                    tag = "good"
                    with self.lock:
                        self.good += 1
                else:
                    status = "BAD"
                    tag = "bad"
                    with self.lock:
                        self.bad += 1

        except Exception:
            status = "Error"
            tag = "cloudflare"
            with self.lock:
                self.cloudflare += 1

        found_str = ", ".join(found_targets) if found_targets else ""
        anchor_str = ", ".join(anchor_texts) if anchor_texts else ""
        type_str = ", ".join(link_types) if link_types else ""

        with self.lock:
            self.results.append([
                idx, backlink, status, found_str, anchor_str, type_str, http_code
            ])
            self.checked_count += 1
            count = self.checked_count

        self.root.after(0, lambda: self.update_progress(count, self.total))
        self.root.after(0, self.update_stats)

    def export_excel(self):
        if not self.results:
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel File", "*.xlsx")]
        )

        if not path:
            return

        wb = Workbook()
        ws = wb.active
        ws.title = "Backlink Report"

        headers = [
            "Backlink URL", "Status", "Found Targets",
            "Anchor Text", "Link Type", "HTTP Status"
        ]
        ws.append(headers)

        sorted_results = sorted(self.results, key=lambda x: x[0])
        for row in sorted_results:
            ws.append(row[1:])

        wb.save(path)
        messagebox.showinfo("Done", "Excel report exported successfully!")


if __name__ == "__main__":
    root = tk.Tk()
    app = BacklinkCheckerGUI(root)
    root.mainloop()
