import pickle
import struct
import traceback
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
        traceback.print_exc()
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
        traceback.print_exc()
        print(f"接收數據時發生錯誤: {e}")
        return None