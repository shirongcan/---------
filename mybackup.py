import os
import shutil
import hashlib
import json
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import queue



def check_backup_status(source_dir, backup_dir, message_queue, backup_mode):
    """检查需要备份和删除的文件数量"""
    # 获取用户选择的备份模式
    files_to_copy = []
    files_to_delete = []
    # 上一次的备份信息
    backup_info = set()
    backup_info_file = os.path.join(backup_dir, "backup_info.txt")

    if os.path.exists(backup_info_file):
        with open(backup_info_file, "r", encoding='utf-8') as f:
            for line in f:
                backup_info.add(line.strip())
                

    for root, _, files in os.walk(source_dir):
        for file in files:
            source_path = os.path.join(root, file)
            relative_path = os.path.relpath(source_path, source_dir)
            
            # 如果相对路径不在备份信息中，说明这是一个新文件或已修改的文件
            if relative_path not in backup_info:
                 # 将该文件添加到需要复制的文件列表中
                 files_to_copy.append(relative_path)
                
              
            

    for root, _, files in os.walk(backup_dir):
        for file in files:
            if file == "backup_info.txt":
                continue
            backup_path = os.path.join(root, file)
            relative_path = os.path.relpath(backup_path, backup_dir)
            source_path = os.path.join(source_dir, relative_path)

            if not os.path.exists(source_path):
                files_to_delete.append(relative_path)

    message_queue.put(f"需要复制的文件数: {len(files_to_copy)}")
    if backup_mode == "sync":
        message_queue.put(f"需要删除的文件数: {len(files_to_delete)}")

    return files_to_copy, files_to_delete

def incremental_backup(source_dir, backup_dir, message_queue, backup_mode,files_to_copy=None, files_to_delete=None):
    """执行增量备份"""
     # 获取用户选择的备份模式
     
    
    backup_info = set()
    backup_info_file = os.path.join(backup_dir, "backup_info.txt")

    if os.path.exists(backup_info_file):
        with open(backup_info_file, "r", encoding='utf-8') as f:
            for line in f:
                backup_info.add(line.strip())

    if files_to_copy is None or files_to_delete is None:
        files_to_copy, files_to_delete = check_backup_status(source_dir, backup_dir, message_queue, backup_mode)

    # 复制文件
    for relative_path in files_to_copy:
        source_path = os.path.join(source_dir, relative_path)
        backup_path = os.path.join(backup_dir, relative_path)
        
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        shutil.copy2(source_path, backup_path)
        backup_info.add(relative_path)
        
        message_queue.put(f"已备份: {relative_path}")

        
    # 判断是增量模式还是同步模式，如果是同步模式才删除文件
    # 删除多余的文件
    if backup_mode == 'sync':
        for relative_path in files_to_delete:
            backup_path = os.path.join(backup_dir, relative_path)
            os.remove(backup_path)
            if relative_path in backup_info:
                backup_info.remove(relative_path)
            message_queue.put(f"已删除: {relative_path}")

            

    # 更新备份信息文件
    with open(backup_info_file, "w", encoding='utf-8') as f:
        for item in backup_info:
            f.write(f"{item}\n")

    message_queue.put("备份完成。")

class BackupGUI:
    def __init__(self, master):
        self.master = master
        master.title("增量备份系统")
        master.geometry("600x450")
        master.configure(bg='#f0f0f0')

        # 添加菜单栏
        self.menu_bar = tk.Menu(master)
        master.config(menu=self.menu_bar)

        # 创建"关于"菜单
        self.about_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="关于", menu=self.about_menu)
        self.about_menu.add_command(label="关于本程序", command=self.show_about)

        self.config_file = "backup_config.json"
        

        style = ttk.Style()
        style.theme_use('clam')

        frame = ttk.Frame(master, padding="10")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=1)

        # 添加备份模式选择
        self.backup_mode = tk.StringVar(value="incremental")

        self.load_config()
        
        self.mode_frame = ttk.LabelFrame(frame, text="备份模式")
        self.mode_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        self.incremental_radio = ttk.Radiobutton(
            self.mode_frame, 
            text="增量备份", 
            variable=self.backup_mode, 
            value="incremental",
            command=self.save_config
        )
        self.incremental_radio.pack(side="left", padx=10)

        self.sync_radio = ttk.Radiobutton(
            self.mode_frame, 
            text="同步", 
            variable=self.backup_mode, 
            value="sync",
            command=self.save_config
        )
        
        self.sync_radio.pack(side="left", padx=10)

        self.source_label = ttk.Label(frame, text="源目录:")
        self.source_label.grid(row=1, column=0, sticky=tk.W, pady=5)

        self.source_entry = ttk.Entry(frame, width=50)
        self.source_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
        if self.source_dir:
            self.source_entry.insert(0, self.source_dir)

        self.source_button = ttk.Button(frame, text="浏览", command=self.browse_source)
        self.source_button.grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)

        self.backup_label = ttk.Label(frame, text="备份目录:")
        self.backup_label.grid(row=2, column=0, sticky=tk.W, pady=5)

        self.backup_entry = ttk.Entry(frame, width=50)
        self.backup_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)
        if self.backup_dir:
            self.backup_entry.insert(0, self.backup_dir)

        self.backup_button = ttk.Button(frame, text="浏览", command=self.browse_backup)
        self.backup_button.grid(row=2, column=2, sticky=tk.W, padx=5, pady=5)

        self.check_button = ttk.Button(frame, text="检查状态", command=self.check_status)
        self.check_button.grid(row=3, column=0, pady=10)

        self.start_button = ttk.Button(frame, text="开始备份", command=self.start_backup)
        self.start_button.grid(row=3, column=1, pady=10)

        self.info_text = tk.Text(frame, height=15, width=70, wrap=tk.WORD)
        self.info_text.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        self.info_text.config(state=tk.DISABLED)

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.info_text.yview)
        scrollbar.grid(row=4, column=3, sticky=(tk.N, tk.S))
        self.info_text.configure(yscrollcommand=scrollbar.set)

        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(4, weight=1)

        self.message_queue = queue.Queue()
        self.master.after(100, self.check_queue)

        self.files_to_copy = None
        self.files_to_delete = None

    def load_config(self):
        self.source_dir = ""
        self.backup_dir = ""
        if os.path.exists(self.config_file):
            with open(self.config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.source_dir = config.get("source_dir", "")
                self.backup_dir = config.get("backup_dir", "")
                self.backup_mode.set(config.get("backup_mode", "incremental"))
            
            # 检查目录是否存在，以及源目录是否为备份目录
            if not os.path.exists(self.source_dir) or self.is_backup_folder(self.source_dir):
                self.source_dir = ""
            if not os.path.exists(self.backup_dir):
                self.backup_dir = ""

    def save_config(self):
        config = {
            "source_dir": self.source_entry.get(),
            "backup_dir": self.backup_entry.get(),
            "backup_mode": self.backup_mode.get()
        }
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(config, f)

    # radio button 的选择要更新config
    

    def browse_source(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            if folder_selected == self.backup_entry.get():
                messagebox.showerror("错误", "源文件夹不能与备份文件夹相同")
                return
            if self.is_backup_folder(folder_selected):
                messagebox.showerror("错误", "不能选择备份文件夹作为源文件夹")
                return
            self.source_entry.delete(0, tk.END)
            self.source_entry.insert(0, folder_selected)
            self.save_config()

    def browse_backup(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            if folder_selected == self.source_entry.get():
                messagebox.showerror("错误", "备份文件夹不能与源文件夹相同")
                return
            self.backup_entry.delete(0, tk.END)
            self.backup_entry.insert(0, folder_selected)
            self.save_config()

    def is_backup_folder(self, folder):
        """检查给定文件夹是否为备份文件夹"""
        return os.path.exists(os.path.join(folder, "backup_info.txt"))

    def check_status(self):
        source_dir = self.source_entry.get()
        backup_dir = self.backup_entry.get()

        if not source_dir or not backup_dir:
            messagebox.showerror("错误", "请选择源目录和备份目录")
            return

        if source_dir == backup_dir:
            messagebox.showerror("错误", "源文件夹不能与备份文件夹相同")
            return

        if self.is_backup_folder(source_dir):
            messagebox.showerror("错误", "不能选择备份文件夹作为源文件夹")
            return

        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete(1.0, tk.END)
        self.info_text.config(state=tk.DISABLED)

        self.check_button.config(state=tk.DISABLED)
        self.start_button.config(state=tk.DISABLED)
        
        thread = threading.Thread(target=self.run_check, args=(source_dir, backup_dir))
        thread.start()

    def run_check(self, source_dir, backup_dir):
        try:
            self.message_queue.put("正在检查备份状态...")
            self.files_to_copy, self.files_to_delete = check_backup_status(source_dir, backup_dir, self.message_queue, self.backup_mode.get())
        except Exception as e:
            self.message_queue.put(f"检查过程中出现错误：{str(e)}")
            messagebox.showerror("错误", f"检查过程中出现错误：\n{str(e)}")
        finally:
            self.master.after(0, self.enable_buttons)

    def start_backup(self):
    
        source_dir = self.source_entry.get()
        backup_dir = self.backup_entry.get()

        if not source_dir or not backup_dir:
            messagebox.showerror("错误", "请选择源目录和备份目录")
            return

        if source_dir == backup_dir:
            messagebox.showerror("错误", "源文件夹不能与备份文件夹相同")
            return

        if self.is_backup_folder(source_dir):
            messagebox.showerror("错误", "不能选择备份文件夹作为源文件夹")
            return

        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete(1.0, tk.END)
        self.info_text.config(state=tk.DISABLED)

        self.check_button.config(state=tk.DISABLED)
        self.start_button.config(state=tk.DISABLED)
        
        thread = threading.Thread(target=self.run_backup, args=(source_dir, backup_dir))
        thread.start()

    def run_backup(self, source_dir, backup_dir):
        try:
            incremental_backup(source_dir, backup_dir, self.message_queue, self.backup_mode.get(), self.files_to_copy, self.files_to_delete)
        except Exception as e:
            self.message_queue.put(f"备份过程中出现错误：{str(e)}")
        finally:
            self.master.after(0, self.enable_buttons)
            self.files_to_copy = None
            self.files_to_delete = None

    def enable_buttons(self):
        self.check_button.config(state=tk.NORMAL)
        self.start_button.config(state=tk.NORMAL)

    def check_queue(self):
        try:
            while True:
                message = self.message_queue.get_nowait()
                self.info_text.config(state=tk.NORMAL)
                self.info_text.insert(tk.END, message + "\n")
                self.info_text.see(tk.END)
                self.info_text.config(state=tk.DISABLED)
        except queue.Empty:
            pass
        finally:
            self.master.after(100, self.check_queue)

    def show_about(self):
        about_text = """
        增量备份系统

        版本: 1.0.0
        发布日期: 2024年9月3日

        设计者: [施荣灿]

        使用说明:
        1. 选择源目录和备份目录
        2. 点击"检查状态"查看需要备份的文件
        3. 点击"开始备份"执行增量备份

        警告：备份目录中存在但源目录中不存在的文件将会被删除！
        警告：备份目录中存在但源目录中不存在的文件将会被删除！
        
        本程序可以帮助您轻松地进行文件增量备份,
        只备份发生变化的文件,节省时间和存储空间。
        
       

        版权所有 © 2024 [施荣灿]. 保留所有权利。
        """
        messagebox.showinfo("关于", about_text)

if __name__ == "__main__":
    root = tk.Tk()
    gui = BackupGUI(root)
    root.mainloop()