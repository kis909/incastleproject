import tkinter as tk
from tkinter import ttk
import sqlite3
import datetime
import os

db_file = 'gap_stock_auto.db'

class KISMonitorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("KIS 갭메우기 봇 모니터링 대시보드 🚀")
        self.root.geometry("850x650")

        # 스타일
        style = ttk.Style()
        style.configure("Treeview.Heading", font=('Malgun Gothic', 10, 'bold'))
        style.configure("Treeview", font=('Malgun Gothic', 9), rowheight=25)

        # Top frame: Controls
        self.top_frame = ttk.Frame(self.root, padding="15")
        self.top_frame.pack(fill=tk.X)
        
        self.lbl_status = ttk.Label(self.top_frame, text="상태: 대기 중", font=('Malgun Gothic', 12, 'bold'))
        self.lbl_status.pack(side=tk.LEFT)
        
        self.btn_refresh = ttk.Button(self.top_frame, text="🔄 수동 새로고침", command=self.refresh_data)
        self.btn_refresh.pack(side=tk.RIGHT, padx=10)

        self.lbl_time = ttk.Label(self.top_frame, text="업데이트 시간: -", font=('Malgun Gothic', 9))
        self.lbl_time.pack(side=tk.RIGHT)

        # Middle frame: Active Positions
        self.mid_frame = ttk.LabelFrame(self.root, text=" 📊 현재 보유 종목 (Active Positions) ", padding="10")
        self.mid_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.tree_pos = ttk.Treeview(self.mid_frame, columns=('symbol', 'buy_date', 'buy_price', 'target_price', 'ma5', 'scaled'), show='headings')
        self.tree_pos.heading('symbol', text='종목코드')
        self.tree_pos.heading('buy_date', text='매수일시')
        self.tree_pos.heading('buy_price', text='매수단가 (원)')
        self.tree_pos.heading('target_price', text='목표가 (50%익절)')
        self.tree_pos.heading('ma5', text='하단추세 (MA5)')
        self.tree_pos.heading('scaled', text='진행 상태')

        self.tree_pos.column('symbol', width=80, anchor='center')
        self.tree_pos.column('buy_date', width=130, anchor='center')
        self.tree_pos.column('buy_price', width=100, anchor='e')
        self.tree_pos.column('target_price', width=100, anchor='e')
        self.tree_pos.column('ma5', width=100, anchor='e')
        self.tree_pos.column('scaled', width=80, anchor='center')

        self.tree_pos.pack(fill=tk.BOTH, expand=True)

        # Bottom frame: Trade History
        self.bot_frame = ttk.LabelFrame(self.root, text=" 📝 최근 매매 내역 (Trade History) ", padding="10")
        self.bot_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.tree_hist = ttk.Treeview(self.bot_frame, columns=('time', 'action', 'symbol', 'price', 'qty', 'memo'), show='headings')
        self.tree_hist.heading('time', text='시간')
        self.tree_hist.heading('action', text='매매구분')
        self.tree_hist.heading('symbol', text='종목')
        self.tree_hist.heading('price', text='상세단가')
        self.tree_hist.heading('qty', text='체결수량')
        self.tree_hist.heading('memo', text='비고/설명')
        
        self.tree_hist.column('time', width=130, anchor='center')
        self.tree_hist.column('action', width=80, anchor='center')
        self.tree_hist.column('symbol', width=80, anchor='center')
        self.tree_hist.column('price', width=100, anchor='e')
        self.tree_hist.column('qty', width=60, anchor='center')
        self.tree_hist.column('memo', width=250, anchor='w')
        
        # Scrollbar for Trade History
        scrollbar = ttk.Scrollbar(self.bot_frame, orient=tk.VERTICAL, command=self.tree_hist.yview)
        self.tree_hist.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_hist.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Initial Load
        self.refresh_data()
        self.auto_refresh()

    def get_db_connection(self):
        if not os.path.exists(db_file):
            return None
        try:
            return sqlite3.connect(db_file)
        except:
            return None

    def refresh_data(self):
        conn = self.get_db_connection()
        if not conn:
            self.lbl_status.config(text="상태: DB 파일 (gap_stock_auto.db) 연결 대기 중...", foreground="red")
            return

        cursor = conn.cursor()
        
        # 1. Update positions
        self.tree_pos.delete(*self.tree_pos.get_children())
        try:
            cursor.execute("SELECT symbol, buy_date, buy_price, target_price, ma5_yesterday, scaled_out FROM active_positions")
            positions = cursor.fetchall()
            for p in positions:
                scaled_str = "절반 익절 완료" if p[5] else "잔여 홀딩"
                self.tree_pos.insert('', tk.END, values=(
                    p[0], p[1], f"{p[2]:,.0f}", f"{p[3]:,.0f}", f"{p[4]:,.0f}", scaled_str
                ))
        except Exception as e:
            print(f"Error loading positions: {e}")

        # 2. Update Trade History
        self.tree_hist.delete(*self.tree_hist.get_children())
        try:
            # Order by ID descending so newest is at the top
            cursor.execute("SELECT timestamp, action, symbol, price, qty, memo FROM trade_history ORDER BY id DESC LIMIT 50")
            history = cursor.fetchall()
            for h in history:
                self.tree_hist.insert('', tk.END, values=(
                    h[0], h[1], h[2], f"{h[3]:,.0f}", h[4], h[5]
                ))
        except Exception as e:
            print(f"Error loading history: {e}")

        conn.close()
        
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.lbl_time.config(text=f"최종 업데이트: {now_str}")
        self.lbl_status.config(text="● 라이브 모니터링 가동 중 (10초 주기)", foreground="blue")

    def auto_refresh(self):
        self.refresh_data()
        self.root.after(10000, self.auto_refresh) # 10초마다 갱신

if __name__ == "__main__":
    root = tk.Tk()
    app = KISMonitorGUI(root)
    root.mainloop()
