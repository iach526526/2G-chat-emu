import socket
import pickle
import threading
import sounddevice as sd
import numpy as np
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
def microphone_send(conn):
    """實現即時錄音並播放的麥克風功能"""
    print("Mic-on: Speak into the microphone. Press Ctrl+C to stop.")
    # 使用 InputStream 和 OutputStream 即時處理音訊
    while True:
        try:
            with sd.InputStream(samplerate=Fs, channels=1, blocksize=BUFFER_SIZE) as input_stream, \
                sd.OutputStream(samplerate=Fs, channels=1, blocksize=BUFFER_SIZE) as output_stream:
                # 從麥克風獲取音訊數據
                audio_data, overflow = input_stream.read(BUFFER_SIZE)
                if overflow:
                    print("Buffer overflow detected!")  # 提醒使用者有緩衝區溢出的情況
                # 將音訊數據調變成 2G 訊號
                send.fsk_signal_with_noise, send.pad_size, send.encoded_bits_crc, send.time = send.simulate_fsk_transmission(audio_data)
                receive.restored_audio_signal_filtered, receive.restored_audio_signal, receive.time = receive.de_modual(send.fsk_signal_with_noise, send.pad_size, send.encoded_bits_crc, send.time)
                send_data = pickle.dumps(receive.restored_audio_signal_filtered)  # 序列化音訊數據
                conn.send(send_data)
        except Exception as e:
            print(f"Error in microphone_send(): {e}")
            exit(1)
            
def microphone_receive(conn):
    """接收音訊並播放"""
    try:
        buffer = b''  # 用於累積接收到的數據
        with sd.OutputStream(samplerate=Fs, channels=1, blocksize=BUFFER_SIZE) as output_stream:
            while True:
                # 接收數據
                data = conn.recv(BUFFER_SIZE)  # 根據情況調整緩衝區大小
                if not data:
                    print("Connection closed by sender.")
                    break
                
                # 累積接收到的數據
                buffer += data
                
                try:
                    # 嘗試反序列化完整的數據
                    audio_data = pickle.loads(buffer)
                    buffer = b''  # 清空緩衝區以接收新的數據
                    
                    # 確保數據為 float32 格式的 numpy array
                    audio_array = np.array(audio_data, dtype='float32')
                    
                    # 播放音訊
                    output_stream.write(audio_array)
                    print("Audio data played.")
                except pickle.UnpicklingError:
                    # 如果數據不完整，繼續接收更多數據
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

if __name__ == "__main__":
    mode = input("Start as server or client? (server:0/client:1): ").strip().lower()
    # server 也可以傳送訊息給 client，這裡只是用來配對的，發起電話的人是 client 端
    if mode == '0':
        port = int(input("Enter port to listen on: "))
        conn = start_server(port)
    elif mode == '1':
        host = input("Enter server IP: ").strip()
        port = int(input("Enter server port: "))
        conn = connect_to_peer(host, port)
    else:
        print("Invalid mode selected.")
        exit(1)

    # 啟動接收與傳送執行緒
    # threading.Thread(target=handle_receive_msg, args=(conn,), daemon=True).start()
    # threading.Thread(target=handle_send_msg, args=(conn,), daemon=True).start()
    threading.Thread(target=microphone_send, args=(conn,),daemon=True).start()
    threading.Thread(target=microphone_receive, args=(conn,), daemon=True).start()

    # 保持主執行緒運行
    while True:
        pass
