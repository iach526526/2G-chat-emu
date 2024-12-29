import socket
import pickle
import struct

def receive_data_over_socket(conn):
    """
    接收來自傳送端的數據
    :param conn: socket 連線對象
    :return: 解包後的 Python 資料
    """
    try:
        size_buffer = conn.recv(4)  # 接收數據大小（4字節）
        if len(size_buffer) < 4:
            raise ConnectionError("未接收到完整的數據大小資訊。")
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

def main():
    # 建立 socket 並連線到傳送端
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(('127.0.0.1', 65432))  # 連線到傳送端

    # 接收數據
    received_data = receive_data_over_socket(client_socket)
    if received_data is not None:
        print("接收到的數據內容：")
        for key, value in received_data.items():
            print(f"{key}:\n{value}\n")

    client_socket.close()

if __name__ == "__main__":
    main()
