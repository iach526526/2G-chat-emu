from os import getenv
import numpy as np
from scipy.signal import butter, lfilter
import binascii
from dotenv import load_dotenv
from .tool import butter_lowpass_filter
load_dotenv(override=True)

cutoff_freq = int(getenv("cutoff_freq"))  # 低通濾波器的截止頻率

# 模擬基地台上下行傳輸中加入干擾
def add_noise(signal, noise_level=0.1):  # 增加噪聲強度
    noise = np.random.normal(0, noise_level, len(signal))
    return signal + noise

# 模擬 A 手機至 B 手機的完整流程
def simulate_fsk_transmission(audio_signal, Fs=8000, noise=False, noise_level=0.1):
    # 進行低通濾波，減少高頻噪音
    audio_signal_filtered = butter_lowpass_filter(audio_signal,cutoff_freq,Fs)

    # 量化音訊信號
    quantized_audio = np.round(audio_signal_filtered * 32767).astype(np.int16)
    encoded_bits = np.unpackbits(quantized_audio.view(np.uint8))

    # 加密
    key = 123
    key_bits = np.unpackbits(np.array([key], dtype=np.uint8))
    key_bits_repeated = np.resize(key_bits, len(encoded_bits))
    encrypted_bits = np.bitwise_xor(encoded_bits, key_bits_repeated)


    # 交錯，並處理填充
    block_size = 10
    pad_size = (block_size - len(encrypted_bits) % block_size) % block_size  # 計算需要填充的位數
    padded_bits = np.hstack([encrypted_bits, np.zeros(pad_size, dtype=encrypted_bits.dtype)])  # 填充位元
    interleaved_bits = padded_bits.reshape((-1, block_size)).T.flatten()  # 交錯
    
    # 生成並印出 CRC 校驗碼
    data_bytes = np.packbits(interleaved_bits).tobytes()
    crc_value = binascii.crc_hqx(data_bytes, 0xFFFF)  # 使用CRC-16校驗
    crc_bits = np.unpackbits(np.array([crc_value >> 8, crc_value & 0xFF], dtype=np.uint8))
    # print(f"Generated CRC: 0x{crc_value:04x}")
    encoded_bits_crc=np.concatenate([interleaved_bits, crc_bits])
    # FSK 調變
    bit_rate=1000
    f0=1000
    f1=2000
    samples_per_bit = Fs // bit_rate
    num_samples = len(encoded_bits_crc) * samples_per_bit
    time = np.arange(num_samples) / Fs
    fsk_signal = np.zeros(num_samples)
    freqs = np.where(encoded_bits_crc == 1, f1, f0)
    fsk_signal = np.cos(2 * np.pi * freqs.repeat(samples_per_bit) * time)
    # 模擬基地台上下行傳輸過程
    fsk_signal_with_noise = fsk_signal
    if noise:
        fsk_signal_with_noise = add_noise(fsk_signal, noise_level)  # 加入噪聲
    print(" pad_size, encoded_bits_crc, time\n", pad_size, encoded_bits_crc, time)
    return fsk_signal_with_noise, pad_size, encoded_bits_crc, time