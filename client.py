import socket
import pickle
import argparse
import threading
import sounddevice as sd
import numpy as np
import queue
import re
import switch_data.SecondGeneration.receive as receive
import switch_data.SecondGeneration.send as send
BUFFER_SIZE = 1024  # 緩衝區大小，越小延遲越低，但可能導致卡頓
Fs = 8000  # 取樣頻率
def handle_receive_msg(conn):
    """接收訊息的執行緒"""
    while True:
        try:
            data = conn.recv(1024).decode('utf-8')
            if not data:
                break
            print(f"Received: {data}")
        except Exception as e:
            print(f"Error receiving data: {e}")
            break

def handle_send_msg(conn):
    """傳送訊息的執行緒"""
    while True:
        try:
            message = input("Enter message: ")
            conn.send(message.encode('utf-8'))
        except Exception as e:
            print(f"Error sending data: {e}")
            break
audio_queue = queue.Queue()
def modulation_thread(conn):
    while True:
        try:
            # 從隊列中獲取音訊數據
            audio_data = audio_queue.get()
            if audio_data is None:
                print("Audio data is None. Exiting modulation_thread().")
                break

            # 調變處理
            send.fsk_signal_with_noise, send.pad_size, send.encoded_bits_crc, send.time = send.simulate_fsk_transmission(audio_data)
            print("調變後", send.pad_size, send.encoded_bits_crc, send.time)

            # 解調變處理
            receive.restored_audio_signal_filtered, receive.restored_audio_signal, receive.time = receive.de_modual(
                send.fsk_signal_with_noise, send.pad_size, send.encoded_bits_crc, send.time
            )

            # 序列化並發送數據
            # send_data = pickle.dumps(receive.restored_audio_signal_filtered)
            send_data = pickle.dumps(audio_data)
            conn.send(send_data)
            print(f"已發送語音包，大小: {len(send_data)} bytes")

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
                    if overflow:
                        print("Buffer overflow detected!")  # 緩衝區溢出
                    print("原始聲音長度：", len(audio_data), type(audio_data))
                    
                    # 將音訊數據放入隊列
                    audio_queue.put(audio_data)

                except Exception as e:
                    print(f"Error in microphone_send() loop: {e}")
                    break
    except KeyboardInterrupt:
        print("錄音停止")

    finally:
        # 停止子執行緒
        audio_queue.put(None)  # 傳遞特殊訊號，讓子執行緒退出
        mod_thread.join()
        print("Mic-off: Program terminated.")
            
def microphone_receive(conn):
    """接收音訊並播放"""
    print("start reveive")
    try:
        # 沒有調變4250，調變後　8344
        SIZE_OF_VOICE_PKG=4250
        buffer = bytearray(SIZE_OF_VOICE_PKG)
        bufferI = 0
        with sd.OutputStream(samplerate=Fs, channels=1, blocksize=BUFFER_SIZE) as output_stream:
            while True:
                # 接收數據
                receive_byte_count=conn.recv_into(memoryview(buffer)[bufferI:],SIZE_OF_VOICE_PKG-bufferI)  # 根據情況調整緩衝區大小
                bufferI += receive_byte_count
                if bufferI >= SIZE_OF_VOICE_PKG:
                    bufferI = 0
                else:
                    continue
                if receive_byte_count==0:
                    print("Connection closed by sender.")
                    break
                
                try:
                    # 嘗試反序列化完整的數據
                    audio_data = pickle.loads(memoryview(buffer)[:SIZE_OF_VOICE_PKG])
                    print(f"now buffer len is {len(buffer)}")
                    
                    # 確保數據為 float32 格式的 numpy array
                    audio_array = np.array(audio_data, dtype='float32')
                    # receive.restored_audio_signal_filtered, receive.restored_audio_signal, receive.time = receive.de_modual(send.fsk_signal_with_noise, send.pad_size, send.encoded_bits_crc, send.time)
                    # 播放音訊
                    output_stream.write(audio_array)
                    print("Audio data played.")
                except pickle.UnpicklingError:
                    # 如果數據不完整，繼續接收更多數據
                    print("Data incomplete. Receiving more...") 
                    continue
    except Exception as e:
        print(f"Error receiving data: {e}")

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
