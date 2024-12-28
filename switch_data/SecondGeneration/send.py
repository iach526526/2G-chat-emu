from os import getenv
import numpy as np
from scipy.signal import butter, lfilter
import binascii
from dotenv import load_dotenv
load_dotenv(override=True)
cutoff_freq = int(getenv("cutoff_freq"))  # 低通濾波器的截止頻率

# 模擬基地台上下行傳輸中加入干擾
def add_noise(signal, noise_level=0.1):  # 增加噪聲強度
    noise = np.random.normal(0, noise_level, len(signal))
    return signal + noise

# 模擬 A 手機至 B 手機的完整流程
def simulate_fsk_transmission(audio_signal, Fs=8000, noise=False, noise_level=0.1):
    # 進行低通濾波，減少高頻噪音
    nyq = 0.5 * Fs  # 奈奎斯特頻率
    order = 5  # 濾波器階數
    cutoff = cutoff_freq  # 截止頻率
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    y = lfilter(b, a, audio_signal)
    
    audio_signal_filtered = y

    # 量化音訊信號
    quantized_audio = np.round(audio_signal_filtered * 32767).astype(np.int16)
    encoded_bits = np.unpackbits(quantized_audio.view(np.uint8))

    # 加密
    key=123
    key_bits = np.unpackbits(np.array([key], dtype=np.uint8))
    encrypted_bits = np.bitwise_xor(encoded_bits, np.tile(key_bits, len(encoded_bits) // len(key_bits) + 1)[:len(encoded_bits)])
    # print("Data encrypted.")

    # 交錯，並處理填充
    block_size=10
    pad_size = (block_size - len(encrypted_bits) % block_size) % block_size  # 計算需要填充的位數
    padded_bits = np.hstack([encrypted_bits, np.zeros(pad_size, dtype=encrypted_bits.dtype)])  # 填充位元
    interleaved_bits = padded_bits.reshape((-1, block_size)).T.flatten()  # 交錯
    # print("Data interleaved.")
    
    # 生成並印出 CRC 校驗碼
    data_bytes = np.packbits(interleaved_bits).tobytes()
    crc_value = binascii.crc_hqx(data_bytes, 0xFFFF)  # 使用CRC-16校驗
    crc_bits = np.unpackbits(np.array([crc_value >> 8, crc_value & 0xFF], dtype=np.uint8))
    # print(f"Generated CRC: 0x{crc_value:04x}")
    encoded_bits_crc=np.concatenate([interleaved_bits, crc_bits])
    # print("Generated CRC and appended to data.")

    # FSK 調變
    bit_rate=1000
    f0=1000
    f1=2000
    Fs=8000
    samples_per_bit = Fs // bit_rate
    time = np.arange(len(encoded_bits_crc) * samples_per_bit) / Fs
    fsk_signal = np.zeros_like(time)

    for i, bit in enumerate(encoded_bits_crc):
        freq = f1 if bit == 1 else f0
        fsk_signal[i * samples_per_bit:(i + 1) * samples_per_bit] = np.cos(
            2 * np.pi * freq * time[i * samples_per_bit:(i + 1) * samples_per_bit])

    # 模擬基地台上下行傳輸過程
    fsk_signal_with_noise = fsk_signal
    if noise:
        fsk_signal_with_noise = add_noise(fsk_signal, noise_level)  # 加入噪聲
        # print("Noise added to the signal.")
    
    return fsk_signal_with_noise, pad_size, encoded_bits_crc, time