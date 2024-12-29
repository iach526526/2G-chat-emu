import socket
import pickle
import struct
import numpy as np

def send_data_over_socket(conn, data):
    """
    傳送數據到接收端
    :param conn: socket 連線對象
    :param data: 要傳送的 Python 資料
    """
    try:
        serialized_data = pickle.dumps(data)  # 序列化數據
        data_size = len(serialized_data)  # 計算數據大小
        conn.sendall(struct.pack(">I", data_size))  # 傳送數據大小（4字節）
        conn.sendall(serialized_data)  # 傳送序列化的數據
        print(f"已成功傳送 {data_size} bytes 的數據。")
    except Exception as e:
        print(f"傳送數據時發生錯誤: {e}")

def main():
    # 建立 socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('127.0.0.1', 65432))  # 綁定 IP 和 Port
    server_socket.listen(1)
    print("等待連線...")

    conn, addr = server_socket.accept()
    print(f"已連線: {addr}")

    # 準備隨機矩陣數據
    data_to_send = {
        "matrix1": np.random.rand(3, 3),  # 3x3 隨機矩陣
        "matrix2": np.random.rand(4, 2),  # 4x2 隨機矩陣
        "matrix3": np.random.rand(2, 5)   # 2x5 隨機矩陣
    }
    print("準備傳送的數據內容：")
    for key, value in data_to_send.items():
        print(f"{key}:\n{value}\n")

    # 傳送數據
    send_data_over_socket(conn, data_to_send)

    conn.close()
    server_socket.close()

if __name__ == "__main__":
    main()
