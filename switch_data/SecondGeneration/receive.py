from os import getenv
import numpy as np
from .tool import check_crc, xor_decrypt, butter_lowpass_filter
from dotenv import load_dotenv
load_dotenv(override=True)
cutoff_freq = int(getenv("cutoff_freq"))  # 低通濾波器的截止頻率
Fs = int(getenv("Fs"))  # 取樣頻率

# FSK 解調，向量化操作
def fsk_demodulate(fsk_signal, bit_rate=1000, f0=1000, f1=2000, Fs=8000):
    samples_per_bit = Fs // bit_rate
    t = np.arange(len(fsk_signal)) / Fs

    # 預先計算頻率基準信號
    ref_wave_0 = np.cos(2 * np.pi * f0 * t)
    ref_wave_1 = np.cos(2 * np.pi * f1 * t)

    # 使用 numpy 向量化運算來處理每個 bit
    num_bits = len(fsk_signal) // samples_per_bit
    demodulated_bits = np.zeros(num_bits, dtype=int)

    # 利用向量化進行比對計算
    for i in range(num_bits):
        start_idx = i * samples_per_bit
        end_idx = (i + 1) * samples_per_bit
        bit_segment = fsk_signal[start_idx:end_idx]

        # 計算兩個匹配的結果
        match_0 = np.sum(bit_segment * ref_wave_0[start_idx:end_idx])
        match_1 = np.sum(bit_segment * ref_wave_1[start_idx:end_idx])
        demodulated_bits[i] = 1 if match_1 > match_0 else 0

    return demodulated_bits

# 語音反量化
def dequantize_audio(quantized_signal):
    return quantized_signal.astype(np.float32) / 32767

# 解交錯並移除填充
def deinterleave(bits, pad_size, block_size=10):
    # 使用reshape來解交錯並去除填充
    deinterleaved_bits = bits.reshape((block_size, -1)).T.flatten()
    if pad_size > 0:
        deinterleaved_bits = deinterleaved_bits[:-pad_size]  # 移除填充的部分
    return deinterleaved_bits

# 解調變
def de_modual(fsk_signal_with_noise, pad_size, encoded_bits, time):
    try:
        # 解調 FSK 信號
        demodulated_bits = fsk_demodulate(fsk_signal_with_noise)

        # 驗證 CRC 校驗碼
        crc_check_passed = check_crc(demodulated_bits)
        print("CRC check passed:", crc_check_passed)

        if crc_check_passed:
            decoded_bits = demodulated_bits[:-16]  # 去除CRC位元

            # 解交錯並移除填充
            deinterleaved_bits = deinterleave(decoded_bits, pad_size)
            print("Data deinterleaved.")

            # 解密
            decrypted_bits = xor_decrypt(deinterleaved_bits)
            print("Data decrypted.")

            # 將解密的位元轉換回音訊數據
            decoded_audio = np.packbits(decrypted_bits[:len(encoded_bits)]).view(np.int16)

            # 反量化音訊
            restored_audio_signal = dequantize_audio(decoded_audio)
        
            # 檢查還原音訊振幅
            # print(f"Restored audio signal max: {np.max(restored_audio_signal)}")
            # print(f"Restored audio signal min: {np.min(restored_audio_signal)}")
            # 再次進行低通濾波，過濾掉高頻噪音
            restored_audio_signal_filtered = butter_lowpass_filter(restored_audio_signal, cutoff_freq, Fs)

            # 放大音訊信號
            restored_audio_signal_filtered *= 10
            print("#Data restored.")
            return restored_audio_signal_filtered, restored_audio_signal, time
        else:
            print("CRC check failed. Data might be corrupted. Outputting corrupted signal.")
            return None, None, None
    except Exception as e:
        print(f"Error during CRC check or data restoration: {e}")
        return None, None, None
