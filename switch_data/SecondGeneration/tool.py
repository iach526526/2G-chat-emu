from scipy.signal import butter, lfilter
import binascii
import numpy as np
# 低通濾波器設計
def butter_lowpass_filter(data, cutoff, Fs, order=5):
    nyq = 0.5 * Fs  # 奈奎斯特頻率
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    y = lfilter(b, a, data)
    return y
# CRC16 校驗碼生成
def generate_crc(data_bits):
    data_bytes = np.packbits(data_bits).tobytes()
    crc_value = binascii.crc_hqx(data_bytes, 0xFFFF)  # 使用CRC-16校驗
    crc_bits = np.unpackbits(np.array([crc_value >> 8, crc_value & 0xFF], dtype=np.uint8))
    print(f"Generated CRC: 0x{crc_value:04x}")
    return np.concatenate([data_bits, crc_bits])

# CRC16 校驗驗證
def check_crc(data_bits_with_crc):
    data_bits = data_bits_with_crc[:-16]  # 提取原始數據
    crc_received = data_bits_with_crc[-16:]  # 提取CRC校驗碼
    expected_crc = generate_crc(data_bits)[-16:]  # 重新生成校驗碼
    return np.array_equal(crc_received, expected_crc)

# XOR加密
def xor_encrypt(bits, key=123):
    key_bits = np.unpackbits(np.array([key], dtype=np.uint8))
    encrypted_bits = np.bitwise_xor(bits, np.tile(key_bits, len(bits) // len(key_bits) + 1)[:len(bits)])
    return encrypted_bits


# XOR解密
def xor_decrypt(bits, key=123):
    return xor_encrypt(bits, key)  # XOR加密與解密是相同的操作