from os import getenv
import numpy as np
from . tool import xor_encrypt,butter_lowpass_filter,generate_crc
from dotenv import load_dotenv
load_dotenv(override=True)
cutoff_freq = int(getenv("cutoff_freq"))  # 低通濾波器的截止頻率
# 語音量化
def quantize_audio(signal):
    quantized_signal = np.round(signal * 32767).astype(np.int16)
    return quantized_signal

# FSK 調變
def fsk_modulate(bits, bit_rate=1000, f0=1000, f1=2000, Fs=8000):
    samples_per_bit = Fs // bit_rate
    t = np.arange(len(bits) * samples_per_bit) / Fs
    fsk_signal = np.zeros_like(t)

    for i, bit in enumerate(bits):
        freq = f1 if bit == 1 else f0
        fsk_signal[i * samples_per_bit:(i + 1) * samples_per_bit] = np.cos(
            2 * np.pi * freq * t[i * samples_per_bit:(i + 1) * samples_per_bit])

    return fsk_signal, t


# 交錯，加入填充
def interleave(bits, block_size=10):
    pad_size = (block_size - len(bits) % block_size) % block_size  # 計算需要填充的位數
    padded_bits = np.hstack([bits, np.zeros(pad_size, dtype=bits.dtype)])  # 填充位元
    interleaved_bits = padded_bits.reshape((-1, block_size)).T.flatten()  # 交錯
    return interleaved_bits, pad_size


# 模擬基地台上下行傳輸中加入干擾
def add_noise(signal, noise_level=0.1):  # 增加噪聲強度
    noise = np.random.normal(0, noise_level, len(signal))
    return signal + noise

# 模擬 A 手機至 B 手機的完整流程
def simulate_fsk_transmission(audio_signal, Fs=8000, noise=False, noise_level=0.1):
    # 進行低通濾波，減少高頻噪音
    audio_signal_filtered = butter_lowpass_filter(audio_signal, cutoff_freq, Fs)

    # 量化音訊信號
    quantized_audio = quantize_audio(audio_signal_filtered)
    encoded_bits = np.unpackbits(quantized_audio.view(np.uint8))

    # 加密
    encrypted_bits = xor_encrypt(encoded_bits)
    print("Data encrypted.")

    # 交錯，並處理填充
    interleaved_bits, pad_size = interleave(encrypted_bits)
    print("Data interleaved.")
    
    # 生成並印出 CRC 校驗碼
    encoded_bits_crc = generate_crc(interleaved_bits)
    print("Generated CRC and appended to data.")

    # FSK 調變
    fsk_signal, time = fsk_modulate(encoded_bits_crc)

    # 模擬基地台上下行傳輸過程
    fsk_signal_with_noise = fsk_signal
    if noise:
        fsk_signal_with_noise = add_noise(fsk_signal, noise_level)  # 加入噪聲
        print("Noise added to the signal.")
    
    return fsk_signal_with_noise, pad_size, encoded_bits_crc, time

    