import argparse
import pickle
import queue
import re
import socket
import struct
import threading
import traceback
from os import getenv
import zlib
import tkinter as tk

import numpy as np
import sounddevice as sd
from dotenv import load_dotenv
from PIL import Image, ImageTk

import switch_data.SecondGeneration.receive as receive
import switch_data.SecondGeneration.send as send
from switch_data.socket.communicate import receive_data_over_socket, send_data_over_socket

BUFFER_SIZE = 8192  # 緩衝區大小，越小延遲越低，但可能導致卡頓
THRESHOLD_MAX = 2000  # 實際讀值要再除 1000
volume_threshold =THRESHOLD_MAX/2 # 初始音量閾值
load_dotenv(override=True)
cutoff_freq = int(getenv("cutoff_freq"))  # 低通濾波器的截止頻率
Fs = int(getenv("Fs"))  # 取樣頻率
exit_event = threading.Event()  # 用於通知結束的全域事件

audio_queue = queue.Queue(maxsize=20)
def modulation_thread(conn):
    while True:
        try:
            # 從隊列中獲取音訊數據
            audio_data = audio_queue.get()
            if audio_data is None:
                print("Audio data is None. Exiting modulation_thread().")
                break
            # 調變處理
            send.fsk_signal_with_noise, send.pad_size, send.encoded_bits_crc= send.simulate_fsk_transmission(audio_data)
            # 打包資料
            after_modulation_zip = {
                "audio": send.fsk_signal_with_noise,
                "pad_size": send.pad_size,
                "encoded_bits_crc": send.encoded_bits_crc,
            }
            send_data_over_socket(conn, after_modulation_zip)

        except Exception as e:
            print(f"Error in modulation_thread(): {e}")

# 主函數，負責錄音並將數據放入隊列
def microphone_send(conn):
    """即時錄音並將音訊數據送入調變執行緒"""
    print("Mic-on: Speak into the microphone. Press Ctrl+C to stop.")
    global volume_threshold
    # 創建調變處理執行緒
    process_single_mod = threading.Thread(target=modulation_thread, args=(conn,))
    process_single_mod.start()

    try:
        # 使用 InputStream 即時錄音
        with sd.InputStream(samplerate=Fs, channels=1, blocksize=BUFFER_SIZE) as input_stream:
            while not exit_event.is_set():
                try:
                    # 從麥克風獲取音訊數據
                    audio_data, overflow = input_stream.read(BUFFER_SIZE)
                    # audio data is numpy ndarray. len is UFFER_SIZE(1024)
                    if overflow:
                        print("Buffer overflow detected!")  # 緩衝區溢出
                    # 檢查是否收到人聲，如果音量太小則跳過
                    if np.sqrt(np.mean(audio_data**2, axis=0)) < volume_threshold:
                        print(f"Audio is silent, skipping transmission.now mean is {np.mean(np.abs(audio_data))}")
                        continue  # 跳過發送過程，回到隊列等待新的音訊數據
                    # 將音訊數據放入 queue
                    audio_queue.put(audio_data)

                except Exception as e:
                    print(f"Error in microphone_send() loop: {e}")
                    break
            print("錄音退出")
    except KeyboardInterrupt:
        process_single_mod.join()
        print("錄音停止")
            
def microphone_receive(conn):
    """接收音訊並播放"""
    print("start reveive")
    with sd.OutputStream(samplerate=Fs, channels=1, blocksize=BUFFER_SIZE) as output_stream:
        while not exit_event.is_set():
            try:
                received_data = receive_data_over_socket(conn)
                # print("收到了：",received_data)
                if received_data is None:
                    print("通道已關閉，結束接收音訊。")
                    exit_event.is_set()
                    break
                # 解調變處理
                rc_audio = received_data["audio"]
                pad_size = received_data["pad_size"]
                encoded_bits_crc = received_data["encoded_bits_crc"]
                receive.restored_audio_signal_filtered = receive.de_modula(rc_audio, pad_size, encoded_bits_crc)
                restored_audio = np.array(receive.restored_audio_signal_filtered,dtype="float32")
                output_stream.write(restored_audio)
                print("Audio data played.")
            except Exception as e:
                print(f"Error in microphone_receive(): {e}")
                traceback.print_exc()
                break
            

def start_server(port,status):
    """啟動伺服器模式"""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', port))
    server_socket.listen(1)
    print(f"Listening for connections on port {port}...")
    server_socket.settimeout(1)  # 設定超時時間為 5 秒
    conn = None
    addr = None
    status.put(f"waiting for connection on port {port}...")
    while not exit_event.is_set():
        try:
            conn, addr = server_socket.accept()
            print(f"Connected by {addr}")
            status.put(f"Connected to {addr}")
            return conn
        except socket.timeout:
            continue  # 超時後重新檢查 exit_event
    print(f"Connected by {addr}")
    status.put("Server stopped.")
    return conn

def connect_to_peer(host, port,status):
    """連線到另一個 P2P 節點"""
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    status.put(f"trying to connect {host}:{port}...")
    client_socket.connect((host, port))
    print(f"Connected to {host}:{port}")
    status.put(f"Connected to {host}:{port}")
    return client_socket
def read_argv():
    # return mode, port, host. if user didn't input port or host, use default value.
    parser = argparse.ArgumentParser(description="Start as server or client.")
    parser.add_argument("mode", choices=["server", "client"], help="Start as 'server' or 'client'")
    parser.add_argument("--port", required=False, help="Port number default is 3000",type=int)
    parser.add_argument("--host", required=False, help="Server IP address. default is '127.0.0.1'. Example:'192.168.0.1' (required for client mode)")
    args = parser.parse_args()
    if not args.port:
        use_port = 3000 # default port
    else:
        use_port = args.port
    if not args.host:
        use_host = "127.0.0.1" # default host
    else:
        #check if IP vaild or not
        use_host = args.host
        ip_pattern = re.compile(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")
        if not ip_pattern.match(use_host):
            print("Invalid IP address format.")
            exit(1)
    return args.mode, use_port, use_host
def update_threshold(value,lable):
    global volume_threshold
    volume_threshold = float(value)/1000
    lable.config(text=f"Threshold: {volume_threshold}")
    
def toggle_voice(btn_self,bar, lable):
    global audio_queue
    current_text = btn_self.cget("text")  # 獲取按鈕當前文字
    while not audio_queue.empty():
        audio_queue.get()
    if current_text == "🔊":# 把麥關掉
        bar.set(THRESHOLD_MAX)
        update_threshold(THRESHOLD_MAX,lable)  # 更新顯示的閾值
    else:
        bar.set(THRESHOLD_MAX/2)
        update_threshold(THRESHOLD_MAX/2,lable)  # 更新顯示的閾值
    new_text = "🔇" if current_text == "🔊" else "🔊"
    btn_self.config(text=new_text)
        
    audio_queue.queue.clear()  # 清空柱列
def create_gui(role,status):
    def on_close():
        print("GUI closed. Exiting...")
        root.destroy()
        exit_event.set()  # 通知其他執行緒退出
    def update_status():
        try:
            while not status.empty():
                message = status.get_nowait()
                status_var.set(message)
        except queue.Empty:
            pass
        if not exit_event.is_set():
            root.after(100, update_status)
    global volume_threshold
    global tk_img
    root = tk.Tk()
    root.title(f"2G chat({role})")
    root.geometry("420x650")
    root.minsize(210, 325)
    root.maxsize(420, 650)
    if role == "server":
        img_obj= Image.open('./img/zelda-Road94.jpg')
        tk_img = ImageTk.PhotoImage(img_obj)
        pos='center'
    else:
        img_obj= Image.open('./img/link-Road94.jpg')
        tk_img = ImageTk.PhotoImage(img_obj)
        pos='center'
    gavartar = tk.Label(root, image=tk_img, width=650, height=300, anchor=pos)
    status_var = tk.StringVar(value=status)
    status_label = tk.Label(root, textvariable=status_var, font=("Arial", 15))
    # 靈敏度閾值標籤
    now_value = tk.Label(root, text=f"Threshold:{volume_threshold}")
    # 滑動條
    bar = tk.Scale(root,
                   from_=0,
                   to=THRESHOLD_MAX,
                   orient="horizontal",
                   command=lambda value: update_threshold(value, now_value),
                   showvalue=False)
    bar.set(volume_threshold)# 設定拉桿初始值
    # 按鈕
    termination_btn = tk.Button(root, text="📞",
                                command=on_close,
                                font=("Arial", 24),  # 字體名稱和大小
                                activeforeground='#0f0',
                                background='#A00')
    close_mic = tk.Button(root, text="🔊",
                          
                            command=lambda: toggle_voice(close_mic,bar, now_value),
                            activeforeground='#fff')
    # 顯示
    gavartar.pack()
    status_label.pack(pady=20)
    now_value.pack(pady=10)
    bar.pack(pady=10)
    close_mic.pack(pady=10)
    termination_btn.pack(pady=10)
    root.after(100, update_status) # 每 100 毫秒更新一次狀態
    root.protocol("WM_DELETE_WINDOW", on_close)
    return root
def start_grahpic(mode,string):
    gui = create_gui(mode,string)
    gui.mainloop()
if __name__ == "__main__":
    # server 也可以傳送訊息給 client，這裡只是用來配對的，發起電話的人是 client 端
    mode, port, host = read_argv()
    conn = None
    status_string = queue.Queue(maxsize=1) 
    if mode == 'server':
        threading.Thread(target=start_grahpic, args=(mode,status_string), daemon=True).start()
        conn = start_server(port, status_string)
    elif mode == 'client':
        threading.Thread(target=start_grahpic, args=(mode,status_string), daemon=True).start()
        conn = connect_to_peer(host, port,status_string)
    # 若參數錯誤， read_argv() 會退出程式
    threading.Thread(target=microphone_send, args=(conn,),daemon=True).start()
    threading.Thread(target=microphone_receive, args=(conn,), daemon=True).start()
    exit_event.wait()