import socket
import numpy as np

# Create a socket
server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_sock.bind(("127.0.0.1", 12345))
server_sock.listen(1)  # Listen for connections

conn, addr = server_sock.accept()
print(f"Connected by {addr}")

# Receive metadata length
metadata_length = int.from_bytes(conn.recv(4), 'big')  # First 4 bytes are metadata length

# Receive metadata
metadata = conn.recv(metadata_length).decode()
shape, dtype = metadata.split(";")
shape = tuple(map(int, shape.strip("()").split(",")))  # Convert shape to tuple
dtype = np.dtype(dtype)

# Receive the data
data = b""
while len(data) < np.prod(shape) * dtype.itemsize:
    packet = conn.recv(4096)  # Receive in chunks
    if not packet:
        break
    data += packet

# Reconstruct the numpy array
received_array = np.frombuffer(data, dtype=dtype).reshape(shape)
print(received_array)

conn.close()
server_sock.close()
