import base64
import os
import socket
import json
import csv
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from threading import Thread
import queue
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import pandas as pd
import win32gui
import win32.lib.win32con as win32con

hideterminal = win32gui.GetForegroundWindow()
win32gui.ShowWindow(hideterminal, win32con.SW_HIDE)

class ClientGUI:
    def __init__(self, master):
        self.master = master
        master.title("HSR Damage Analyzer GUI")
        master.geometry("1200x800")

        self.client_socket = None
        self.csv_file = None
        self.csv_writer = None
        self.avatar_names = []
        self.running = False
        self.log_queue = queue.Queue()
        self.data_buffer = pd.DataFrame()
        self.current_file = ""

        self.create_widgets()
        self.setup_plots()
        self.update_log()

    def create_widgets(self):
        self.notebook = ttk.Notebook(self.master)
        self.notebook.pack(fill="both", expand=True)

        log_tab = ttk.Frame(self.notebook)
        self.notebook.add(log_tab, text="Logs")

        conn_frame = ttk.Frame(log_tab, padding=10)
        conn_frame.pack(fill="x")

        ttk.Label(conn_frame, text="Server:").grid(row=0, column=0)
        self.server_entry = ttk.Entry(conn_frame, width=15)
        self.server_entry.grid(row=0, column=1, padx=5)
        self.server_entry.insert(0, "127.0.0.1")

        ttk.Label(conn_frame, text="Port:").grid(row=0, column=2)
        self.port_entry = ttk.Entry(conn_frame, width=8)
        self.port_entry.grid(row=0, column=3, padx=5)
        self.port_entry.insert(0, "1305")

        self.connect_btn = ttk.Button(conn_frame, text="Connect", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=4, padx=5)

        self.status_label = ttk.Label(conn_frame, text="Not Connected", foreground="red")
        self.status_label.grid(row=0, column=5, padx=10)

        self.pin_btn = ttk.Button(conn_frame, text="Pin Window", command=self.toggle_pin)
        self.pin_btn.grid(row=0, column=6, padx=5)

        self.log_area = scrolledtext.ScrolledText(log_tab, wrap=tk.WORD)
        self.log_area.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_area.configure(state='disabled')

        vis_tab = ttk.Frame(self.notebook)
        self.notebook.add(vis_tab, text="Analytics")

        self.figure = Figure(figsize=(12, 8), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=vis_tab)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        self.ax1 = self.figure.add_subplot(221)
        self.ax2 = self.figure.add_subplot(222)
        self.ax3 = self.figure.add_subplot(212)
        self.figure.tight_layout(pad=3.0)

    def toggle_pin(self):
        current_state = self.master.attributes("-topmost")
        new_state = not current_state
        self.master.attributes("-topmost", new_state)
        if new_state:
            self.pin_btn.config(text="Unpin Window")
            self.log_message("Window pinned on top")
        else:
            self.pin_btn.config(text="Pin Window")
            self.log_message("Window unpinned")


    def setup_plots(self):
        """Initialize plot configurations"""
        self.ax1.set_title("Real-time Damage")
        self.ax1.set_xlabel("Time Sequence")
        self.ax1.set_ylabel("Damage")
        
        self.ax2.set_title("Damage Distribution")
        
        self.ax3.set_title("Total Damage by Avatar")
        self.ax3.set_ylabel("Total Damage")
        
        self.canvas.draw()

    def toggle_connection(self):
        if self.running:
            self.stop_client()
        else:
            self.start_client()

    def start_client(self):
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server = (self.server_entry.get(), int(self.port_entry.get()))
            self.client_socket.connect(server)
            
            self.running = True
            self.connect_btn.config(text="Disconnect")
            self.status_label.config(text="Connected", foreground="green")
            
            Thread(target=self.receive_loop, daemon=True).start()
            self.log_message(f"Connected to {server[0]}:{server[1]}")
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))

    def stop_client(self):
        self.running = False
        if self.client_socket:
            self.client_socket.close()
        if self.csv_file:
            self.csv_file.close()
            self.csv_file = None
        self.connect_btn.config(text="Connect")
        self.status_label.config(text="Not Connected", foreground="red")
        self.log_message("Disconnected")

    def receive_loop(self):
        try:
            buffer = bytearray()
            
            while self.running:
                response = self.client_socket.recv(1024)
                if not response:
                    break
                
                buffer.extend(response)

                while len(buffer) >= 4:
                    size = int.from_bytes(buffer[0:4], byteorder='little')
                    
                    if len(buffer) < size + 4:
                        break

                    try:
                        packet_data = buffer[4:size+4]
                        data = json.loads(packet_data)
                        
                        self.process_message(data)
                        self.update_plots()
                        
                        buffer = buffer[size+4:]
                        
                    except json.JSONDecodeError as e:
                        self.log_message(f"JSON decode error: {str(e)}")
                        buffer = buffer[4:]
                    except Exception as e:
                        self.log_message(f"Packet processing error: {str(e)}")
                        buffer = buffer[4:]

        except (ConnectionResetError, ConnectionAbortedError):
            self.log_message("Connection closed by server")
        except Exception as e:
            self.log_message(f"Error: {str(e)}")
        finally:
            self.stop_client()

    def process_message(self, data):
        packet_type = data["type"]
        packet_data = data["data"]

        if packet_type == "SetBattleLineup":
            self.handle_lineup(packet_data)
        elif packet_type == "OnDamage": 
            self.handle_damage(packet_data)
        elif packet_type == "TurnEnd":
            self.handle_turn_end(packet_data)
        elif packet_type == "OnKill":
            self.handle_kill(packet_data)
        elif packet_type == "BattleEnd":
            self.handle_battle_end()

    def handle_lineup(self, data):
        os.makedirs("damage_logs", exist_ok=True)
        
        filename = f"HSR_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        full_path = os.path.join("damage_logs", filename)
        
        self.current_file = full_path
        self.csv_file = open(full_path, mode='w', newline='', encoding='utf-8')
        self.csv_writer = csv.writer(self.csv_file)
        self.avatar_names = [avatar["name"] for avatar in data["avatars"]]
        self.csv_writer.writerow(self.avatar_names)
        self.data_buffer = pd.DataFrame(columns=self.avatar_names)
        self.log_message(f"Created CSV: {filename}")
        self.log_message(f"Headers: {self.avatar_names}")

    def handle_damage(self, data):
        if self.csv_writer and self.avatar_names:
            row = [0] * len(self.avatar_names)
            attacker = data["attacker"]["name"]
            damage = data["damage"]
            
            if damage > 0:
                self.log_message(f"{attacker} dealt {damage} damage")
            if attacker in self.avatar_names:
                row[self.avatar_names.index(attacker)] += damage

            self.csv_writer.writerow(row)
            self.csv_file.flush()

            new_row = pd.DataFrame([row], columns=self.avatar_names)
            if self.data_buffer.empty:
                self.data_buffer = new_row
            else:
                self.data_buffer = pd.concat([self.data_buffer, new_row], ignore_index=True)

    def handle_turn_end(self, data):
        avatars = data["avatars"]
        damages = data["avatars_damage"]
        total = data["total_damage"]
        
        for avatar, damage in zip(avatars, damages):
            if damage > 0:
                self.log_message(f"Turn summary - {avatar['name']}: {damage} damage")
        self.log_message(f"Total turn damage: {total}")

    def handle_kill(self, data):
        self.log_message(f"{data['attacker']['name']} has killed")

    def handle_battle_end(self):
        if self.csv_file:
            self.csv_file.close()
            self.csv_file = None
            self.log_message("Battle ended - CSV file closed") 
        self.stop_client()

    def update_plots(self):
        if not self.data_buffer.empty:
            try:
                self.ax1.clear()
                self.ax2.clear()
                self.ax3.clear()
    
                time_seq = range(1, len(self.data_buffer) + 1)
    
                for avatar in self.avatar_names:
                    self.ax1.plot(time_seq, self.data_buffer[avatar].cumsum(), label=avatar)
                self.ax1.legend()
                self.ax1.set_title("Cumulative Damage Over Time")
                self.ax1.set_xlabel("Attack Sequence")
                self.ax1.set_ylabel("Total Damage")
    
                total_damage = self.data_buffer.sum()
                self.ax2.pie(total_damage, labels=self.avatar_names, autopct='%1.1f%%')
                self.ax2.set_title("Damage Distribution")
    
                self.ax3.bar(self.avatar_names, total_damage)
                self.ax3.set_title("Total Damage by Avatar")
                self.ax3.set_ylabel("Total Damage")
    
                def format_damage(x, pos):
                    if x >= 1_000_000:
                        return f'{x/1e6:.1f}M'.replace(".0M", "M")
                    elif x >= 1_000:
                        return f'{x/1e3:.0f}k'
                    else:
                        return f'{int(x)}'
                
                self.ax1.yaxis.set_major_formatter(plt.FuncFormatter(format_damage))
                self.ax3.yaxis.set_major_formatter(plt.FuncFormatter(format_damage))
                
                self.canvas.draw()
            except Exception as e:
                self.log_message(f"Plot Error: {str(e)}")

    def log_message(self, message):
        self.log_queue.put(f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")

    def update_log(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.log_area.configure(state='normal')
            self.log_area.insert(tk.END, msg)
            self.log_area.see(tk.END)
            self.log_area.configure(state='disabled')
        self.master.after(100, self.update_log)

    def on_close(self):
        self.stop_client()
        self.master.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ClientGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()