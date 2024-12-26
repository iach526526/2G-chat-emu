import socket
import numpy as np

# Create a numpy array
array_to_send = np.random.rand(4, 4)  # A 4x4 array of random numbers

# Serialize the array
data = array_to_send.tobytes()

# Send metadata: shape and dtype
metadata = f"{array_to_send.shape};{array_to_send.dtype}".encode()

# Create a socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(("127.0.0.1", 12345))  # Connect to the server

# Send the metadata length, metadata, and data
sock.sendall(len(metadata).to_bytes(4, 'big'))  # First send metadata length
sock.sendall(metadata)                          # Then send metadata
sock.sendall(data)                              # Finally send the data

sock.close()
