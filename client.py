import socket
import pickle
import argparse
import threading
import sounddevice as sd
import numpy as np
import struct
import traceback
import queue
import re
import switch_data.SecondGeneration.receive as receive
import switch_data.SecondGeneration.send as send
BUFFER_SIZE = 1024  # 緩衝區大小，越小延遲越低，但可能導致卡頓
Fs = 8000  # 取樣頻率
def send_data_over_socket(conn, data):
    """
    傳送數據到接收端
    :param conn: socket 連線對象
    :param data: 要傳送的 Python 資料
    """
    try:
        serialized_data = pickle.dumps(data)  # 序列化數據
        data_size = len(serialized_data)  # 計算數據大小
        conn.sendall(struct.pack(">I", data_size))  # 傳送數據大小（4 bytes）
        conn.sendall(serialized_data)  # 傳送序列化的數據
        print(f"已成功傳送 {data_size} bytes 的數據。")
    except Exception as e:
        print(f"傳送數據時發生錯誤: {e}")
def receive_data_over_socket(conn):
    """
    接收來自傳送端的數據
    :param conn: socket 連線對象
    :return: 解包後的 Python 資料
    """
    try:
        size_buffer = conn.recv(4)  # 接收數據大小（4 byte）
        if len(size_buffer) < 4:
            print("未接收到完整的數據大小資訊。")
            return None
        data_size = struct.unpack(">I", size_buffer)[0]  # 解析數據大小
        print(f"準備接收 {data_size} bytes 的數據...")

        buffer = bytearray(data_size)
        buffer_view = memoryview(buffer)

        received_size = 0
        while received_size < data_size:
            chunk_size = conn.recv_into(buffer_view[received_size:], data_size - received_size)
            if chunk_size == 0:
                raise ConnectionError("傳送端關閉連線。")
            received_size += chunk_size

        received_data = pickle.loads(buffer)  # 解包數據
        print("數據接收成功並解包完成。")
        return received_data
    except Exception as e:
        print(f"接收數據時發生錯誤: {e}")
        return None
audio_queue = queue.Queue()
def modulation_thread(conn):
    while True:
        try:
            # 從隊列中獲取音訊數據
            audio_data = audio_queue.get()
            if audio_data is None:
                print("Audio data is None. Exiting modulation_thread().")
                break
            # 檢查是否收到人聲，如果音量太小則跳過
            if np.mean(np.abs(audio_data)) < 0.5:
                print(f"Audio is silent, skipping transmission.now mean is {np.mean(np.abs(audio_data))}")
                continue  # 跳過發送過程，回到隊列等待新的音訊數據
            # 調變處理
            send.fsk_signal_with_noise, send.pad_size, send.encoded_bits_crc, send.time = send.simulate_fsk_transmission(audio_data)
            # print("調變後", send.pad_size, send.encoded_bits_crc, send.time)
            # receive.de_modual(send.fsk_signal_with_noise, send.pad_size, send.encoded_bits_crc, send.time)
            # 打包資料
            after_modulation_zip = {
                "audio": send.fsk_signal_with_noise,
                "pad_size": send.pad_size,
                "encoded_bits_crc": send.encoded_bits_crc,
                "time": send.time
            }
            send_data_over_socket(conn, after_modulation_zip)
            
            # print("解調後長度",len(receive.restored_audio_signal_filtered), len(receive.restored_audio_signal), len(receive.time))
            # 序列化並發送數據
            # send_data = pickle.dumps(receive.restored_audio_signal_filtered)
            # send_data = pickle.dumps(audio_data)
            # conn.send(send_data)
            # print("序列化後長度",len(send_data))
            # print(f"已發送語音包，大小: {len(send_data)} bytes")

        except Exception as e:
            print(f"Error in modulation_thread(): {e}")

# 主函數，負責錄音並將數據放入隊列
def microphone_send(conn):
    """即時錄音並將音訊數據送入調變執行緒"""
    print("Mic-on: Speak into the microphone. Press Ctrl+C to stop.")
    
    # 創建調變處理執行緒
    mod_thread = threading.Thread(target=modulation_thread, args=(conn,))
    mod_thread.start()

    try:
        # 使用 InputStream 即時錄音
        with sd.InputStream(samplerate=Fs, channels=1, blocksize=BUFFER_SIZE) as input_stream:
            while True:
                try:
                    # 從麥克風獲取音訊數據
                    audio_data, overflow = input_stream.read(BUFFER_SIZE)
                    # audio data is numpy ndarray. len is UFFER_SIZE(1024)
                    if overflow:
                        print("Buffer overflow detected!")  # 緩衝區溢出
                    
                    # 將音訊數據放入 queue
                    audio_queue.put(audio_data)

                except Exception as e:
                    print(f"Error in microphone_send() loop: {e}")
                    break
    except KeyboardInterrupt:
        mod_thread.join()
        print("錄音停止")
            
def microphone_receive(conn):
    """接收音訊並播放"""
    print("start reveive")
    with sd.OutputStream(samplerate=Fs, channels=1, blocksize=BUFFER_SIZE) as output_stream:
        while True:
            try:
                received_data = receive_data_over_socket(conn)
                print("收到了：",received_data)
                if received_data is None:
                    print("通道已關閉，結束接收音訊。")
                    break
                # 解調變處理
                rc_audio = np.asarray(received_data["audio"])
                pad_size = int(received_data["pad_size"])
                encoded_bits_crc = np.asarray(received_data["encoded_bits_crc"])
                time = np.asarray(received_data["time"])
                receive.restored_audio_signal_filtered, receive.restored_audio_signal, receive.time = receive.de_modual(
                    rc_audio, pad_size, encoded_bits_crc, time)
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
    conn, addr = server_socket.accept()
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
if __name__ == "__main__":
    # server 也可以傳送訊息給 client，這裡只是用來配對的，發起電話的人是 client 端
    mode, port, host = read_argv()
    if mode == 'server':
        conn = start_server(port)
    elif mode == 'client':
        conn = connect_to_peer(host, port)
    else:
        print("Invalid mode selected.")
        exit(1)

    # 啟動接收與傳送執行緒
    # threading.Thread(target=handle_receive_msg, args=(conn,), daemon=True).start()
    # threading.Thread(target=handle_send_msg, args=(conn,), daemon=True).start()
    if (mode == 'client'):
        threading.Thread(target=microphone_send, args=(conn,),daemon=True).start()
    threading.Thread(target=microphone_receive, args=(conn,), daemon=True).start()

    # 保持主執行緒運行
    while True:
        pass
