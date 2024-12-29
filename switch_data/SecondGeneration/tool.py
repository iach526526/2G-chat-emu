from scipy.signal import butter, lfilter
import numpy as np
# 低通濾波器設計
def butter_lowpass_filter(data, cutoff, Fs, order=5):
    nyq = 0.5 * Fs  # 奈奎斯特頻率
    normal_cutoff = cutoff / nyq # 截止頻率
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return lfilter(b, a, data)
# XOR加密
def xor_encrypt(bits, key=123):
    key_bits = np.unpackbits(np.array([key], dtype=np.uint8))
    key_bits_repeated = np.resize(key_bits, len(bits))
    encrypted_bits = np.bitwise_xor(bits, key_bits_repeated)
    return encrypted_bits


# XOR解密
def xor_decrypt(bits, key=123):
    return xor_encrypt(bits, key)  # XOR加密與解密是相同的操作