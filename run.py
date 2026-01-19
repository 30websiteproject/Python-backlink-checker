import threading
import requests
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
from openpyxl import Workbook

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

TIMEOUT = 15


class BacklinkCheckerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Advanced Backlink Checker – Excel Report")
        self.root.geometry("1000x650")

        self.results = []
        self.total = self.good = self.bad = self.cloudflare = 0

        self.build_ui()

    def build_ui(self):
        # Target URL
        tk.Label(self.root, text="Target URL (must exist in backlinks):").pack(anchor="w", padx=10)
        self.target_entry = tk.Entry(self.root)
        self.target_entry.pack(fill="x", padx=10)

        # Workers
        frame_workers = tk.Frame(self.root)
        frame_workers.pack(anchor="w", padx=10, pady=5)
        tk.Label(frame_workers, text="Workers:").pack(side="left")
        self.worker_entry = tk.Entry(frame_workers, width=5)
        self.worker_entry.insert(0, "10")
        self.worker_entry.pack(side="left", padx=5)

        # Backlinks input
        tk.Label(self.root, text="Backlinks (one per line):").pack(anchor="w", padx=10)
        self.backlink_text = tk.Text(self.root, height=10)
        self.backlink_text.pack(fill="both", padx=10, pady=5)

        # Buttons
        frame_btn = tk.Frame(self.root)
        frame_btn.pack(pady=5)

        self.start_btn = tk.Button(frame_btn, text="Start Checking", command=self.start_check)
        self.start_btn.pack(side="left", padx=5)

        self.export_btn = tk.Button(frame_btn, text="Export Excel", command=self.export_excel, state="disabled")
        self.export_btn.pack(side="left", padx=5)

        # Stats
        frame_stats = tk.Frame(self.root)
        frame_stats.pack(fill="x", padx=10)

        self.lbl_total = tk.Label(frame_stats, text="Total: 0")
        self.lbl_total.pack(side="left", padx=10)

        self.lbl_good = tk.Label(frame_stats, text="Good: 0", fg="green")
        self.lbl_good.pack(side="left", padx=10)

        self.lbl_bad = tk.Label(frame_stats, text="Bad: 0", fg="red")
        self.lbl_bad.pack(side="left", padx=10)

        self.lbl_cf = tk.Label(frame_stats, text="Cloudflare: 0", fg="orange")
        self.lbl_cf.pack(side="left", padx=10)

        # Result Table
        cols = ("Backlink", "Status", "Anchor Text", "Link Type")
        self.tree = ttk.Treeview(self.root, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
        self.tree.pack(fill="both", expand=True, padx=10, pady=5)

    def update_stats(self):
        self.lbl_total.config(text=f"Total: {self.total}")
        self.lbl_good.config(text=f"Good: {self.good}")
        self.lbl_bad.config(text=f"Bad: {self.bad}")
        self.lbl_cf.config(text=f"Cloudflare: {self.cloudflare}")

    def start_check(self):
        backlinks = [i.strip() for i in self.backlink_text.get("1.0", tk.END).splitlines() if i.strip()]
        target = self.target_entry.get().strip()

        if not backlinks or not target:
            messagebox.showerror("Error", "Please enter backlinks and target URL")
            return

        try:
            workers = int(self.worker_entry.get())
        except:
            messagebox.showerror("Error", "Invalid workers number")
            return

        self.tree.delete(*self.tree.get_children())
        self.results.clear()

        self.total = len(backlinks)
        self.good = self.bad = self.cloudflare = 0
        self.update_stats()

        self.start_btn.config(state="disabled")
        self.export_btn.config(state="disabled")

        threading.Thread(
            target=self.run_checker,
            args=(backlinks, target, workers),
            daemon=True
        ).start()

    def run_checker(self, backlinks, target, workers):
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for backlink in backlinks:
                executor.submit(self.check_backlink, backlink, target)

        self.start_btn.config(state="normal")
        self.export_btn.config(state="normal")

    def check_backlink(self, backlink, target):
        status = anchor = link_type = http_code = "—"

        try:
            r = requests.get(backlink, headers=HEADERS, timeout=TIMEOUT)
            http_code = r.status_code
            html = r.text.lower()

            if http_code in [403, 429, 503] or "cloudflare" in html or "cf-ray" in html:
                status = "Cloudflare / Not Checked"
                self.cloudflare += 1
            else:
                soup = BeautifulSoup(r.text, "html.parser")
                found = False

                for a in soup.find_all("a", href=True):
                    if target.lower() in a["href"].lower():
                        anchor = a.get_text(strip=True) or "(No Text)"
                        rel = a.get("rel", [])
                        link_type = "Nofollow" if "nofollow" in rel else "Dofollow"
                        status = "GOOD"
                        self.good += 1
                        found = True
                        break

                if not found:
                    status = "BAD"
                    self.bad += 1

        except Exception:
            status = "Cloudflare / Not Checked"
            self.cloudflare += 1

        self.results.append([
            backlink, target, status, anchor, link_type, http_code
        ])

        self.root.after(0, lambda: self.tree.insert(
            "", "end", values=(backlink, status, anchor, link_type)
        ))
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
            "Backlink URL", "Target URL", "Status",
            "Anchor Text (Keyword)", "Link Type", "HTTP Status"
        ]
        ws.append(headers)

        for row in self.results:
            ws.append(row)

        wb.save(path)
        messagebox.showinfo("Done", "Excel report exported successfully!")


if __name__ == "__main__":
    root = tk.Tk()
    app = BacklinkCheckerGUI(root)
    root.mainloop()
