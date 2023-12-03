import queue
import tkinter as tk
from tkinter import filedialog,PhotoImage
import re
import os
import requests
import json
from io import BytesIO
from PIL import ImageTk, Image
import base64
from urllib.parse import urlparse
from urllib.parse import unquote
import threading
from queue import Queue
from threading import Thread
from tkinter import Toplevel


root = tk.Tk()
root.title("图片链接替换工具-v3.3")
root.configure(bg="white")
picgo_server_url = "http://127.0.0.1:36677/upload"
result_filepath = None
back = "md"
path = None
has_run = 1

class MatchInfo:
    def __init__(self, filepath, picUrls):
        # md文件路径
        self.filepath = filepath
        # 文件中所有匹配到的图片url
        self.picUrls = picUrls

    def toString(self):
        s = "======================\n"
        s += self.filepath + ":\n"
        s += "\n".join(map(str, self.picUrls))
        return s

    def to_dict(self):
        return {"filepath": self.filepath, "picUrls": self.picUrls}

    @classmethod
    def from_dict(cls, data):
        return cls(data["filepath"], data["picUrls"])


# 函数：选择路径

def log_to_queue(message):
    log_text.insert(tk.END, message)
    log_text.see(tk.END)
    root.update_idletasks()


def select_path():
    global path
    path = filedialog.askdirectory()

    if not path:
        log_text.tag_configure("red", foreground="red")
        log_text.insert(tk.END, "未选择路径,请选择路径后继续\n", "red")  # 添加未选择路径的红色提示
        return  # 结束函数，不继续执行下面的逻辑

    path_entry.delete(0, tk.END)
    path_entry.insert(tk.END, path)
    log_text.insert(tk.END, f"路径选择为：{path}\n")


# 转义斜杠
def fix_file_path(filepath):
    # Replace backslashes with forward slashes
    return filepath.replace("\\", "/")


# 函数：提取链接
def extract_links():
    global result_filepath,back
    pathlu = path_entry.get()
    linklu = link_pattern_entry.get()
    back = allowed_extensions_entry.get()
    directory = pathlu

    md_regex = re.compile(rf".*\.{back}$")
    pic_regex = re.compile(linklu)
    if not linklu:
        log_text.tag_configure("red", foreground="red")
        log_text.insert(tk.END, "请输入扫描域名进行转换，或直接点击转换链接，切换为选择全部图片\n", "red")
        return
    # 获取用户输入的其他后缀
    allowed_extensions = allowed_extensions_entry.get().split()
    allowed_extensions_regex = r".*\.(" + "|".join(re.escape(ext) for ext in allowed_extensions) + r")$"

    file_links = {}  # 用于存储文件链接的字典

    for root, dirs, files in os.walk(directory):
        for filename in files:
            if re.match(allowed_extensions_regex, filename) or md_regex.match(filename):
                filepath = os.path.join(root, filename)
                filepath = fix_file_path(filepath)
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    picUrls = pic_regex.findall(content)
                    if picUrls:
                        if filepath not in file_links:
                            file_links[filepath] = set()
                        file_links[filepath].update(picUrls)

    # 转换链接为所需格式
    formatted_links = [{"file": file, "links": list(links)} for file, links in file_links.items()]

    # 提示获取链接情况
    if not formatted_links:
        log_text.tag_configure("red", foreground="red")
        log_text.insert(tk.END, "未获取到链接，请检查正则表达式或路径是否正确。\n", "red")
    else:
        # 提示获取链接成功
        log_text.insert(tk.END, "获取到链接。\n")

        # 用户选择保存位置，则保存到文件
        result_filepath = filedialog.asksaveasfilename(initialfile="output.json", defaultextension=".json",
                                                       filetypes=[("JSON 文件", "*.json")])
        if not result_filepath:
            log_text.tag_configure("red", foreground="red")
            log_text.insert(tk.END, "未选择路径,请选择路径后继续\n", "red")
        if result_filepath:
            with open(result_filepath, "w", encoding="utf-8") as output_file:
                json.dump(formatted_links, output_file, indent=4, ensure_ascii=False)

            # 提示处理完成
            log_text.insert(tk.END, f"链接获取完成并已保存到:{result_filepath}\n")
            log_text.see(tk.END)


def push_change():
    global picgo_server_url  # 使 picgo_server_url 变量全局可用
    global result_filepath
    if not window_d:
        create_window_d()
        window_d.withdraw()
    def upload_by_picgo(match_info):
        name = match_info['file']
        data = {
            "list": match_info['links']
        }
        log_to_queue(f"开始上传文件: {name}\n")  # 修正此行
        res = requests.post(picgo_server_url, json=data)
        res_obj = res.json()
        if res.status_code != 200 or not res_obj.get("success"):
            log_text.tag_configure("red", foreground="red")
            log_text.insert(tk.END, f"上传失败: {name}\n! 请检查网络和配置项\n", "red")
            return False
        log_to_queue(f"上传成功: {name}\n")
        return res_obj["result"]

    def process_matches():
        try:
            if not result_filepath:
                log_text.tag_configure("red", foreground="red")
                log_text.insert(tk.END, "路径文件为空，请先进行链接提取\n", "red")
                return
            # Deserialize
            with open(result_filepath, "r", encoding="utf-8") as output_file:
                load_data = json.load(output_file)
                matches = load_data  # Matches are a list of dictionaries

            log_to_queue("开始执行，请勿重复点击，可能需要较长时间，请等待!!!\n")
            # Upload images for each match and replace original URLs
            for match in matches:
                # Upload all images in the file
                pics_new = upload_by_picgo(match)
                if not pics_new:
                    continue

                # Replace URLs in the file
                filepath = match['file']

                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    for search_text, replace_text in zip(match['links'], pics_new):
                        content = content.replace(search_text, replace_text)
                    with open(filepath, "w", encoding="utf-8") as ff:
                        ff.write(content)
                        log_to_queue(f"已替换：{match['file']}\n")
            log_to_queue("全部执行完成!!\n")
        except Exception as e:
            log_to_queue(f"批量替换失败: {str(e)}\n")

    # Create a thread for processing matches
    process_thread = Thread(target=process_matches)
    process_thread.start()



def update_link_entry():
    # 获取用户输入的链接
    global result_filepath, back, path, has_run
    if not path:
        log_text.tag_configure("red", foreground="red")
        log_text.insert(tk.END, "未选择路径,请选择路径后继续\n", "red")  # 添加未选择路径的红色提示
        return
    # 获取用户输入的链接
    link_text = link_pattern_entry.get()

    # 默认正则表达式
    default_regex = r"https?://[^\s\r\n(){}\[\]]+/[^\s\r\n(){}\[\]]+(?:jpg|png|gif|jpeg|pdf|webp|bmp|tiff|svg|heif|ico|apng|exif|raw|psd|eps|wmf|emf|pcx|dng|webm|jp2)"

    # 检查用户输入是否为空
    if not link_text:
        formatted_link = default_regex
    elif link_text == default_regex:
        # 如果用户输入与默认正则表达式匹配，不进行转换
        formatted_link = link_text
    else:
        # 如果用户输入没有"http://"或"https://"前缀，自动添加
        if not link_text.startswith("http://") and not link_text.startswith("https://"):
            link_text = "http://" + link_text

        # 提取域名部分
        domain_match = re.search(r'https?://([^/]+)', link_text)
        if domain_match:
            domain = domain_match.group(1)
            formatted_link = re.escape(domain)  # 转义域名以用于正则表达式
            formatted_link = rf"https?://{formatted_link}/[^\s\r\n(){{}}\[\]]+(?:jpg|png|gif|jpeg|pdf|webp|bmp|tiff|svg|heif|ico|apng|exif|raw|psd|eps|wmf|emf|pcx|dng|webm|jp2)"
    # 插入格式化后的链接到 GUI 元素
    link_pattern_entry.delete(0, tk.END)
    link_pattern_entry.insert(tk.END, formatted_link)
    if has_run == 1:
        log_text.insert(tk.END, "链接已转换为：" + formatted_link + "\n")
        has_run += 1
    else:
        log_text.tag_configure("red", foreground="red")
        log_text.insert(tk.END, "请勿重复转换相同的链接。\n", "red")
    return



def perform_link_replacement():
    global back
    # 获取用户输入的替换链接域名和路径
    replacement_domain = replacement_link_entry.get()
    path = path_entry.get()
    link_text = link_pattern_entry.get()
    back = allowed_extensions_entry.get()
    if not path:
        log_to_queue("请选择文件路径\n")
        return
    # 检查是否有输入
    if not replacement_domain:
        log_text.tag_configure("red", foreground="red")
        log_text.insert(tk.END, "请输入需要扫描md文件中的域名\n", "red")
        return



    # 遍历目录，替换链接
    for root, dirs, files in os.walk(path):
        for filename in files:
            if filename.endswith(rf".{back}"):
                filepath = os.path.join(root, filename)
                filepath = fix_file_path(filepath)
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    # 使用正则表达式替换链接中的域名部分
                    content = re.sub(rf"{link_text}", f"{replacement_domain}", content)
                with open(filepath, "w", encoding="utf-8") as ff:
                    ff.write(content)
                    log_to_queue(f"已替换文件：{filepath}\n")

    log_to_queue("指定链接已替换完成\n")

def extract_update_link():
    global result_filepath, back,path,has_run
    if not path:
        log_text.tag_configure("red", foreground="red")
        log_text.insert(tk.END, "未选择路径,请选择路径后继续\n", "red")  # 添加未选择路径的红色提示
        return
    # 获取用户输入的链接
    link_text = link_pattern_entry.get()

    # 默认正则表达式
    default_regex = r"https?://[^\s\r\n(){}\[\]]+/[^\s\r\n(){}\[\]]+(?:jpg|png|gif|jpeg|pdf|webp|bmp|tiff|svg|heif|ico|apng|exif|raw|psd|eps|wmf|emf|pcx|dng|webm|jp2)"

    if not path:
        log_text.tag_configure("red", foreground="red")
        log_text.insert(tk.END, "未选择路径,请选择路径后继续\n", "red")
        if link_text == default_regex:
            log_text.tag_configure("red", foreground="red")
            log_text.insert(tk.END, "请勿重复转换相同的链接。\n", "red")
            return

    # 检查用户输入是否为空
    if not link_text:
        formatted_link = default_regex
    elif link_text == default_regex:
        # 如果用户输入与默认正则表达式匹配，不进行转换
        formatted_link = link_text
    else:
        # 如果用户输入没有"http://"或"https://"前缀，自动添加
        if not link_text.startswith("http://") and not link_text.startswith("https://"):
            link_text = "http://" + link_text

        # 提取域名部分
        domain_match = re.search(r'https?://([^/]+)', link_text)
        if domain_match:
            domain = domain_match.group(1)
            formatted_link = re.escape(domain)  # 转义域名以用于正则表达式
            formatted_link = rf"https?://{formatted_link}/[^\s\r\n(){{}}\[\]]+(?:jpg|png|gif|jpeg|pdf|webp|bmp|tiff|svg|heif|ico|apng|exif|raw|psd|eps|wmf|emf|pcx|dng|webm|jp2)"

    # 插入格式化后的链接到 GUI 元素
    link_pattern_entry.delete(0, tk.END)
    link_pattern_entry.insert(tk.END, formatted_link)
    if has_run == 1:
        log_text.insert(tk.END, "链接已转换为：" + formatted_link + "\n")
        has_run+=1
        extract_linksb()
    else:
        extract_linksb()

def extract_linksb():
    global result_filepath,back
    pathlu = path_entry.get()
    linklu = link_pattern_entry.get()
    back = allowed_extensions_entry.get()
    directory = pathlu

    md_regex = re.compile(rf".*\.{back}$")
    pic_regex = re.compile(linklu)
    if not linklu:
        log_text.tag_configure("red", foreground="red")
        log_text.insert(tk.END, "请输入扫描域名进行转换，或直接点击转换链接，切换为选择全部图片\n", "red")
        return
    # 获取用户输入的其他后缀
    allowed_extensions = allowed_extensions_entry.get().split()
    allowed_extensions_regex = r".*\.(" + "|".join(re.escape(ext) for ext in allowed_extensions) + r")$"

    file_links = {}  # 用于存储文件链接的字典

    for root, dirs, files in os.walk(directory):
        for filename in files:
            if re.match(allowed_extensions_regex, filename) or md_regex.match(filename):
                filepath = os.path.join(root, filename)
                filepath = fix_file_path(filepath)
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    picUrls = pic_regex.findall(content)
                    if picUrls:
                        if filepath not in file_links:
                            file_links[filepath] = set()
                        file_links[filepath].update(picUrls)

    # 转换链接为所需格式
    formatted_links = [{"file": file, "links": list(links)} for file, links in file_links.items()]
    # 提示获取链接情况
    if not formatted_links:
        log_text.tag_configure("red", foreground="red")
        log_text.insert(tk.END, "未获取到链接，请检查正则表达式或路径是否正确。\n", "red")
    else:
        # 提示获取链接成功
        log_text.insert(tk.END, "获取到链接。\n")

        # 用户选择保存位置，则保存到文件
        result_filepath = filedialog.asksaveasfilename(initialfile="output.json", defaultextension=".json",
                                                       filetypes=[("JSON 文件", "*.json")])
        if not result_filepath:
            log_text.tag_configure("red", foreground="red")
            log_text.insert(tk.END, "未选择路径,请选择路径后继续\n", "red")
            return
        if result_filepath:
            with open(result_filepath, "w", encoding="utf-8") as output_file:
                json.dump(formatted_links, output_file, indent=4, ensure_ascii=False)

            # 提示处理完成
            log_text.insert(tk.END, f"链接获取完成并已保存到:{result_filepath}\n")
            log_text.see(tk.END)


def perform_link_download():
    if not window_d:
        create_window_d()
        window_d.withdraw()
    def download_link_content(link, save_directory):
        try:
            response = requests.get(link, stream=True)
            if response.status_code == 200:
                parsed_url = urlparse(link)
                path = unquote(parsed_url.path)
                save_path = os.path.join(save_directory, path.lstrip("/"))
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, 'wb') as file:
                    for chunk in response.iter_content(1024):
                        file.write(chunk)
                log_to_queue(f"已下载：{path}\n")
            else:
                log_to_queue(f"下载失败：{link}\n")
        except Exception as e:
            log_to_queue(f"下载时错误：{str(e)}\n")
    def download_thread():
        # 下载链接内容到指定文件夹
        if not result_filepath:
            log_text.tag_configure("red", foreground="red")
            log_text.insert(tk.END, "路径文件为空，请先进行转换提取，选择所需保存图片\n", "red")
            return
        log_text.insert(tk.END, "下载文件可能较多，请勿重复点击，耐心等待...\n")
        download_directory = filedialog.askdirectory()

        if not download_directory:
            if not result_filepath:
                log_text.tag_configure("red", foreground="red")
                log_text.insert(tk.END, "未选择下载路径，请选择路径后继续。\n", "red")
            return

        # Deserialize from the specified file
        with open(result_filepath, "r", encoding="utf-8") as output_file:
            load_data = json.load(output_file)

        # Check if the loaded data is in the expected format
        if not isinstance(load_data, list):
            log_to_queue("文件内容不符合预期的格式。\n")
            return

        # Iterate through the loaded data and call download_link_content
        for item in load_data:
            if "file" in item and "links" in item:
                file = item["file"]
                links = item["links"]
                for link in links:
                    download_link_content(link, download_directory)

        log_queue.put("链接提取和下载完成。\n")



    # 创建一个队列用于在后台线程中记录日志
    log_queue = Queue()

    # 后台线程执行下载
    download_thread = threading.Thread(target=download_thread)
    download_thread.start()

    # 使用定时器在后台线程中获取队列消息并输出到日志框
    def update_log():
        try:
            message = log_queue.get(0)
            log_text.insert(tk.END, message)
            log_queue.task_done()
        except queue.Empty:
            pass

        log_text.after(100, update_log)

    update_log()


# 创建主应用窗口

window_b = None
window_c = None
window_d = None

def show_a_window():
    root.deiconify()
    if window_b:
        window_b.withdraw()
    if window_c:
        window_c.withdraw()

def show_d_window():
    window_d.deiconify()  # 显示窗口 D

# 显示 C 界面的函数
def show_c_window():
    global window_c
    if not window_c:
        create_window_c()
    root.withdraw()  # 隐藏根窗口
    if window_c:
        window_c.deiconify()  # 显示窗口C


# 从 A 界面显示 B 界面的函数
def show_b_window_from_a():
    global window_b
    root.withdraw()
    if not window_b:
        create_window_b()
    else:
        window_b.deiconify()


# 从 A 界面显示 C 界面的函数
def show_c_window_from_a():
    global window_c
    root.withdraw()
    if not window_c:
        create_window_c()
    else:
        window_c.deiconify()


# 处理 C 界面关闭事件的函数
def on_b_window_close():
    global window_b,picgo_server_url,result_filepath,back,path,has_run
    if window_b:
        window_b.destroy()
        window_b = None  # 重置窗口 B
        picgo_server_url = "http://127.0.0.1:36677/upload"
        result_filepath = None
        back = "md"
        path = None
        has_run = 1
    show_a_window()
def on_c_window_close():
    global window_c,picgo_server_url,result_filepath,back,path,has_run
    if window_c:
        window_c.destroy()
        picgo_server_url = "http://127.0.0.1:36677/upload"
        result_filepath = None
        back = "md"
        path = None
        has_run = 1
        window_c = None
    show_a_window()

def on_d_window_close():
    root.destroy()
# 处理主窗口关闭事件的函数
def on_a_window_close():
    if not window_d:
        root.destroy()
    else:
        root.withdraw()
        show_d_window()



# 设置程序图标
encoded_image = " "
decoded_image = base64.b64decode(encoded_image)
icon_photo = ImageTk.PhotoImage(data=decoded_image)
root.iconphoto(True, icon_photo)

root.protocol("WM_DELETE_WINDOW", on_a_window_close)
root.geometry("480x340")
root.wm_maxsize(400, 340)

# 计算居中显示的窗口大小
window_width = 480
window_height = 380
windowa_width_max = 400
windowa_height_max = 380
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
x_position = (screen_width - window_width) // 2
y_position = (screen_height - window_height) // 2

# 使用几何字符串设置窗口
geometry_string = f"{window_width}x{window_height}+{x_position}+{y_position}"
root.geometry(geometry_string)
root.wm_maxsize(windowa_width_max, windowa_height_max)

# 添加介绍文字
intro_label = tk.Label(root, text="-----------------------------------------------------", pady=10,
                       font=("Helvetica", 16, "bold"))
intro_label.pack()
intro_label = tk.Label(root, text="图片链接替换提取工具", pady=0, font=("Helvetica", 16, "bold"))
intro_label.pack()
intro_label = tk.Label(root, text="-----------------------------------------------------", pady=2,
                       font=("Helvetica", 16, "bold"))
intro_label.pack()

intro_label = tk.Label(root, text="！！！！！！使用前，请先备份！！！！！！", pady=0, font=("Helvetica", 12, "bold"), fg="red")
intro_label.pack()

intro_label = tk.Label(root,
                       text="程序  by  静雨▪安蝉(blog.kwxos.top)+ChatGpt完成\n对Github-wincent98/Picaway佬的代码改进封装和增加前端\n-----------＞如有任何问题，博客留言＜-----------",
                       pady=3, font=("微软雅黑", 10, "bold"))
intro_label.pack()

intro_frame = tk.Frame(root)
intro_frame.pack()

intro_label_left = tk.Label(intro_frame,
                            text="本程序分为两个板块：\n自动更换：\n①提取图片链接到指定文件\n②更换图片图床和替换图片链接\n③图片链接转换正则\n④需借助PicGo更换图床",
                            font=("微软雅黑", 10, "bold"), justify=tk.LEFT)
intro_label_left.grid(row=0, column=0, sticky=tk.W, padx=1)

intro_label_right = tk.Label(intro_frame,
                             text="\n手动更换：\n更换图片域名为指定域名①\n根据域名图片路径下载到本地②\n灵活转移图片替换链接③\n手动更换不依赖PicGo④",
                             font=("微软雅黑", 10, "bold"), justify=tk.RIGHT)
intro_label_right.grid(row=0, column=1, sticky=tk.E, padx=5)

# 创建一个框架用于放置按钮，并使其水平居中
button_frame = tk.Frame(root)
button_frame.pack()

button_to_c_from_a = tk.Button(button_frame, text="自动更换", command=show_c_window)
button_to_c_from_a.grid(row=0, column=0, padx=60, pady=15)

button_to_b_from_a = tk.Button(button_frame, text="手动更换", command=show_b_window_from_a)
button_to_b_from_a.grid(row=0, column=1, padx=60, pady=15)


def create_window_c():
    global window_c, path_entry, log_text, link_pattern_entry, link_pattern_entry, allowed_extensions_entry
    window_c = tk.Toplevel(root)
    window_c.title("自动更换工具")
    window_c.protocol("WM_DELETE_WINDOW", on_c_window_close)

    # 设置窗口
    window_width = 520  # 增加窗口宽度
    window_height = 508 # Increased window height to accommodate the log display
    window_width_max = 520
    window_height_max = 520
    screen_width = window_c.winfo_screenwidth()
    screen_height = window_c.winfo_screenheight()
    x_position = (screen_width - window_width) // 2
    y_position = (screen_height - window_height) // 2

    window_c.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")

    window_c.wm_maxsize(window_width_max, window_height_max)
    # 创建和放置部件

    frame_top = tk.Frame(window_c)
    frame_top.pack(pady=1)

    frame_bottom = tk.Frame(window_c)
    frame_bottom.pack(pady=1)

    frame_middle = tk.Frame(window_c)
    frame_middle.pack(pady=1)

    path_entry_label = tk.Label(frame_top, text="文件路径:")
    path_entry_label.grid(row=0, column=0, padx=5, pady=5, sticky=tk.E)  # 减小间隔
    path_entry = tk.Entry(frame_top, width=40)
    path_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

    link_pattern_label = tk.Label(frame_bottom, text="域名链接:")
    link_pattern_label.grid(row=1, column=0, padx=5, pady=5, sticky=tk.E)  # 减小间隔
    link_pattern_entry = tk.Entry(frame_bottom, width=40)
    link_pattern_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)

    allowed_extensions_label = tk.Label(frame_middle, text="文件后缀:")
    allowed_extensions_label.grid(row=2, column=1, padx=5, pady=5, sticky=tk.E)  # 减小间隔
    allowed_extensions_entry = tk.Entry(frame_middle, width=4)
    allowed_extensions_entry.insert(tk.END, back)
    allowed_extensions_entry.grid(row=2, column=2, padx=5, pady=5, sticky=tk.W)

    # 设置服务URL标签和输入框
    picgo_server_url_label = tk.Label(frame_middle, text="服务URL:")
    picgo_server_url_label.grid(row=2, column=3, padx=5, pady=5, sticky=tk.E)  # 减小间隔
    picgo_server_url_entry = tk.Entry(frame_middle, width=25)
    picgo_server_url_entry.insert(tk.END, picgo_server_url)  # 设置默认值
    picgo_server_url_entry.grid(row=2, column=4, padx=5, pady=5, sticky=tk.W)

    # 创建一个框架用于放置按钮，并使其水平居中
    button_frame = tk.Frame(window_c)
    button_frame.pack()

    select_path_button = tk.Button(button_frame, text="①选择路径", command=select_path)
    select_path_button.grid(row=0, column=0, padx=10, pady=5)

    update_link_button = tk.Button(button_frame, text="②转换链接", command=update_link_entry)
    update_link_button.grid(row=0, column=1, padx=10, pady=5)

    extract_button = tk.Button(button_frame, text="③提取链接", command=extract_links)
    extract_button.grid(row=0, column=2, padx=10, pady=5)

    change_button = tk.Button(button_frame, text="④上传替换", command=push_change)
    change_button.grid(row=0, column=3, padx=10, pady=5)

    log_text = tk.Text(window_c, width=70, height=10, wrap=tk.WORD)
    log_text.pack(pady=10)

    fixed_text_label = tk.Label(window_c, text="注：此程序用于替换文件中的图片链接，与PicGo配合使用")
    fixed_text_label.pack(pady=(1, 0), padx=10)

    fixed_text_label = tk.Label(window_c, text="教程：", anchor="w")
    fixed_text_label.pack(pady=(1, 0), padx=10, anchor="w")

    fixed_text_label = tk.Label(window_c,
                                text="1.点击选择文件路径  2.输入md文件中需要被替换链接的域名(不加路径)，也可输入正则链接",
                                anchor="w")
    fixed_text_label.pack(pady=(1, 0), padx=10, anchor="w")

    fixed_text_label = tk.Label(window_c,
                                text="3.点击转换链接(也可自行输入正则，不转换),当域名链接值为空时，默认匹配所有图片",
                                anchor="w")
    fixed_text_label.pack(pady=(1, 0), padx=10, anchor="w")

    fixed_text_label = tk.Label(window_c,
                                text="4.输入文件后缀，如md,json,css,不需要添加符号  5.可更改picgo的服务URL，一般默认即可",
                                anchor="w")
    fixed_text_label.pack(pady=(1, 0), padx=10, anchor="w")

    fixed_text_label = tk.Label(window_c, text="6.点击执行替换，即可自动上传图床并替换md文件中的链接，终，等待完成就行",
                                anchor="w")
    fixed_text_label.pack(pady=(1, 0), padx=10, anchor="w")

    fixed_text_label = tk.Label(window_c,
                                text="----------------------------------------------------------------------------------------------------\n程序  by  静雨▪安蝉(blog.kwxos.top)+ChatGpt完成\n对Github-wincent98/Picaway佬的代码改进封装和增加前端")
    fixed_text_label.pack(pady=(2, 0))


# 创建手动更换工具
def create_window_b():
    global window_b, path_entry, log_text, link_pattern_entry, link_pattern_entry, allowed_extensions_entry, replacement_link_entry
    window_b = tk.Toplevel(root)
    window_b.title("手动更换工具")
    window_b.protocol("WM_DELETE_WINDOW", on_b_window_close)

    # 计算居中显示的窗口宽度
    window_width = 485
    window_height = 537
    windowb_width_max = 485
    windowb_height_max = 537
    screen_width = window_b.winfo_screenwidth()
    screen_height = window_b.winfo_screenheight()
    x_position = (screen_width - window_width) // 2
    y_position = (screen_height - window_height) // 2

    window_b.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")

    window_b.wm_maxsize(windowb_width_max, windowb_height_max)

    frame_top = tk.Frame(window_b)  # 创建一个框架用于放置上侧部件
    frame_top.pack(pady=1)  # 减小间隔

    frame_middle = tk.Frame(window_b)  # 创建一个框架用于放置中部部件
    frame_middle.pack(pady=1)  # 减小间隔

    frame_bottom = tk.Frame(window_b)  # 创建一个框架用于放置下侧部件
    frame_bottom.pack(pady=1)  # 减小间隔

    # 添加输入框，用于跳转到自动更换工具
    path_entry_label = tk.Label(frame_top, text="文件路径:")
    path_entry_label.grid(row=0, column=0, padx=5, pady=5, sticky=tk.E)
    path_entry = tk.Entry(frame_top, width=40)
    path_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

    allowed_extensions_label = tk.Label(frame_top, text="文件后缀:")
    allowed_extensions_label.grid(row=0, column=1, padx=280, pady=5, sticky=tk.W)

    allowed_extensions_entry = tk.Entry(frame_top, width=4)
    allowed_extensions_entry.insert(tk.END, "md")
    allowed_extensions_entry.grid(row=0, column=1, padx=341, pady=5, sticky=tk.W)

    link_pattern_label = tk.Label(frame_top, text="扫描链接:")
    link_pattern_label.grid(row=1, column=0, padx=5, pady=5, sticky=tk.E)
    link_pattern_entry = tk.Entry(frame_top, width=52)
    link_pattern_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)

    replacement_link_label = tk.Label(frame_top, text="替换链接:")
    replacement_link_label.grid(row=2, column=0, padx=5, pady=5, sticky=tk.E)
    replacement_link_entry = tk.Entry(frame_top, width=52)
    replacement_link_entry.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)

    # 添加按钮，用于直接替换和保存本地
    select_path_button = tk.Button(frame_middle, text="①选择路径", command=select_path)
    select_path_button.grid(row=0, column=0, padx=10, pady=10)

    replace_button = tk.Button(frame_middle, text="②直接替换", command=perform_link_replacement)
    replace_button.grid(row=0, column=1, padx=10, pady=10)

    download_link_button = tk.Button(frame_middle, text="④转换提取", command=extract_update_link)
    download_link_button.grid(row=0, column=2, padx=10, pady=10)

    download_link_button = tk.Button(frame_middle, text="③保存本地", command=perform_link_download)
    download_link_button.grid(row=0, column=3, padx=10, pady=10)

    log_text = tk.Text(frame_bottom, width=65, height=10, wrap=tk.WORD)
    log_text.grid(row=0, column=0, padx=10, pady=10)

    fixed_text_label = tk.Label(window_b, text="注：此程序用于替换文件中的图片链接，更换图床请手动上传")
    fixed_text_label.pack(pady=(1, 0), padx=10)

    fixed_text_label = tk.Label(window_b, text="教程：", anchor="w")
    fixed_text_label.pack(pady=(1, 0), padx=10, anchor="w")

    fixed_text_label = tk.Label(window_b,
                                text="1.点击选择需扫描文件的路径，输入文件后缀，默认md，可选择json,css,...",
                                anchor="w")
    fixed_text_label.pack(pady=(1, 0), padx=10, anchor="w")

    fixed_text_label = tk.Label(window_b,
                                text="2.输入文件中需要被扫描链接的域名",
                                anchor="w")
    fixed_text_label.pack(pady=(1, 0), padx=10, anchor="w")

    fixed_text_label = tk.Label(window_b,
                                text="3.在替换链接处输入你想将原域名替换的域名，点击直接替换,即可替换",
                                anchor="w")
    fixed_text_label.pack(pady=(1, 0), padx=10, anchor="w")

    fixed_text_label = tk.Label(window_b, text="4.点击转换提取,即可提取链接保存到指定路径，可将不需要下载的链接删除,",
                                anchor="w")
    fixed_text_label.pack(pady=(1, 0), padx=10, anchor="w")

    fixed_text_label = tk.Label(window_b, text="5.点击保存本地,即可根据链接路径,下载文件中选择的图片并按照链接路径保存到本地,",
                                anchor="w")
    fixed_text_label.pack(pady=(1, 0), padx=10, anchor="w")

    fixed_text_label = tk.Label(window_b,
                                text="----------------------------------------------------------------------------------------------------\n程序  by  静雨▪安蝉(blog.kwxos.top)+ChatGpt完成\n对Github-wincent98/Picaway佬的代码改进封装和增加前端")
    fixed_text_label.pack(pady=(2, 0))

def create_window_d():
    global window_d
    window_d = Toplevel(root)
    window_d.title("链接替换工具")
    window_d.protocol("WM_DELETE_WINDOW", on_d_window_close)

    def load_and_display_image(image_url, label):
        response = requests.get(image_url)
        image = Image.open(BytesIO(response.content))
        image = image.resize((150, 150), Image.LANCZOS)
        photo = ImageTk.PhotoImage(image)

        label.configure(image=photo)
        label.image = photo

    # 创建一个主的框架，用于放置图片和文本
    main_frame = tk.Frame(window_d)
    main_frame.grid(row=0, column=0, padx=10, pady=10)

    # 添加第一张空白的图片标签
    image1_label = tk.Label(main_frame)
    image1_label.grid(row=0, column=0, padx=10)

    # 添加第二张空白的图片标签
    image2_label = tk.Label(main_frame)
    image2_label.grid(row=0, column=1, padx=10)

    # 添加文本，居中对齐
    text = "如果觉得工具不错的话，可以打赏一下吗？\n٩(๑>◡<๑)۶      谢谢啦！    ✧*｡٩(ˊᗜˋ*)و✧*｡"
    text_label = tk.Label(main_frame, text=text, wraplength=300)
    text_label.grid(row=1, column=0, columnspan=2, padx=10, pady=10)

    window_d.update()  # 显示窗口

    # 使用多线程加载图片
    image1_url = " "
    image2_url = " "
    thread1 = threading.Thread(target=load_and_display_image, args=(image1_url, image1_label))
    thread2 = threading.Thread(target=load_and_display_image, args=(image2_url, image2_label))

    thread1.start()
    thread2.start()
    # 获取屏幕宽度和高度
    window_width = 370
    window_height = 220
    windowa_width_max = 370
    windowa_height_max = 220
    screen_width = window_d.winfo_screenwidth()
    screen_height = window_d.winfo_screenheight()
    x_position = (screen_width - window_width) // 2
    y_position = (screen_height - window_height) // 2

    # 使用几何字符串设置窗口
    geometry_string = f"{window_width}x{window_height}+{x_position}+{y_position}"
    window_d.geometry(geometry_string)
    window_d.wm_maxsize(windowa_width_max, windowa_height_max)

show_a_window()

# 运行主程序
root.mainloop()
