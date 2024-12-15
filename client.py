import socket
import threading

def handle_receive(conn):
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

def handle_send(conn):
    """傳送訊息的執行緒"""
    while True:
        try:
            message = input("Enter message: ")
            conn.send(message.encode('utf-8'))
        except Exception as e:
            print(f"Error sending data: {e}")
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
    threading.Thread(target=handle_receive, args=(conn,), daemon=True).start()
    threading.Thread(target=handle_send, args=(conn,), daemon=True).start()

    # 保持主執行緒運行
    while True:
        pass
