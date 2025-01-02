import socket
import pickle
import argparse
import threading
import tkinter as tk
import sounddevice as sd
import numpy as np
import struct
import traceback
import queue
import re
import switch_data.SecondGeneration.receive as receive
import switch_data.SecondGeneration.send as send
import zlib
BUFFER_SIZE = 8192  # 緩衝區大小，越小延遲越低，但可能導致卡頓
volume_threshold = 0.1  # 初始音量閾值
Fs = 8000  # 取樣頻率
exit_event = threading.Event()  # 用於通知結束的全域事件
def send_data_over_socket(conn, data):
    """
    傳送數據到接收端（使用 Pickle 和壓縮）
    :param conn: socket 連線對象
    :param data: 要傳送的 Python 資料
    """
    try:
        # 序列化數據並壓縮
        serialized_data = pickle.dumps(data)
        print(f"已序列化數據，原始大小: {len(serialized_data)} bytes")
        compressed_data = zlib.compress(serialized_data)
        data_size = len(compressed_data)
        
        # 傳送數據大小（4 bytes）和壓縮後的數據
        conn.sendall(struct.pack(">I", data_size) + compressed_data)
        
        print(f"已成功傳送 {data_size} bytes 的壓縮數據。")
    except (ConnectionError, OSError) as e:
        print(f"傳送數據時發生連線錯誤: {e}")
    except Exception as e:
        print(f"傳送數據時發生錯誤: {e}")
def receive_data_over_socket(conn):
    """
    接收來自傳送端的數據（使用 Pickle 和解壓縮）
    :param conn: socket 連線對象
    :return: 解包後的 Python 資料
    """
    try:
        # 接收數據大小（4 bytes）
        size_buffer = conn.recv(4)
        if len(size_buffer) != 4:
            raise ConnectionError("未接收到完整的數據大小資訊。")
        
        # 解析數據大小
        data_size = struct.unpack(">I", size_buffer)[0]
        print(f"準備接收 {data_size} bytes 的壓縮數據...")
        
        # 接收完整的壓縮資料
        buffer = bytearray(data_size)
        buffer_view = memoryview(buffer)
        received_size = 0
        
        while received_size < data_size:
            chunk_size = conn.recv_into(buffer_view[received_size:], data_size - received_size)
            if chunk_size == 0:
                raise ConnectionError("傳送端關閉連線。")
            received_size += chunk_size
        
        # 解壓縮數據並反序列化
        decompressed_data = zlib.decompress(buffer)
        received_data = pickle.loads(decompressed_data)
        
        print("數據接收成功並解包完成。")
        return received_data
    except (ConnectionError, OSError) as e:
        print(f"接收數據時發生連線錯誤: {e}")
        return None
    except zlib.error as e:
        print(f"解壓縮失敗: {e}")
        return None
    except Exception as e:
        print(f"接收數據時發生錯誤: {e}")
        return None
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
            

def start_server(port):
    """啟動伺服器模式"""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', port))
    server_socket.listen(1)
    print(f"Listening for connections on port {port}...")
    server_socket.settimeout(1)  # 設定超時時間為 5 秒
    conn = None
    addr = None
    while not exit_event.is_set():
        try:
            conn, addr = server_socket.accept()
            print(f"Connected by {addr}")
            return conn
        except socket.timeout:
            continue  # 超時後重新檢查 exit_event
    print(f"Connected by {addr}")
    return conn

def connect_to_peer(host, port):
    """連線到另一個 P2P 節點"""
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((host, port))
    print(f"Connected to {host}:{port}")
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
    volume_threshold = float(value)/10000
    lable.config(text=f"Threshold: {volume_threshold}")
    
def disable_voice(bar, lable):
    global audio_queue
    while not audio_queue.empty():
        audio_queue.get()
    bar.set(9000)  # 將滑桿值設為 0.9
    update_threshold(9000,lable)  # 更新顯示的閾值
    audio_queue.queue.clear()  # 清空柱列
def create_gui(role):
    
    def on_close():
        root.destroy()
        print("GUI closed. Exiting...")
        exit_event.set()  # 通知其他執行緒退出
    global volume_threshold
    root = tk.Tk()
    root.title(f"2G chat({role})")
    root.geometry("420x650")
    root.minsize(210, 325)
    # 靈敏度閾值標籤
    now_value = tk.Label(root, text=f"Threshold:{volume_threshold}")
    # 滑動條
    bar = tk.Scale(root, 
                   from_=0, 
                   to=9000, 
                   orient="horizontal", 
                   command=lambda value: update_threshold(value, now_value),
                   showvalue=False)
    bar.set(volume_threshold)# 設定拉桿初始值
    # 按鈕
    termination_btn = tk.Button(root, text="Exit",
                                command=on_close,
                                activeforeground='#0f0',
                                background='#f00')
    close_mic = tk.Button(root, text="🔇",
                          
                            command=lambda: disable_voice(bar, now_value),
                            activeforeground='#fff')
    # 顯示
    now_value.pack(pady=10)
    bar.pack(pady=10)
    termination_btn.pack(pady=10)
    close_mic.pack(pady=10)
    root.protocol("WM_DELETE_WINDOW", on_close)
    return root
def start_grahpic(mode):
    gui = create_gui(f"{mode}")
    gui.mainloop()
if __name__ == "__main__":
    # server 也可以傳送訊息給 client，這裡只是用來配對的，發起電話的人是 client 端
    mode, port, host = read_argv()
    conn = None
    if mode == 'server':
        threading.Thread(target=start_grahpic, args=(mode,), daemon=True).start()
        conn = start_server(port)
    elif mode == 'client':
        threading.Thread(target=start_grahpic, args=(mode,), daemon=True).start()
        conn = connect_to_peer(host, port)
    # 若參數錯誤， read_argv() 會退出程式
    threading.Thread(target=microphone_send, args=(conn,),daemon=True).start()
    threading.Thread(target=microphone_receive, args=(conn,), daemon=True).start()
    exit_event.wait()