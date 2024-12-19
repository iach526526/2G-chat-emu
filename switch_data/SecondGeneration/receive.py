from os import getenv
import numpy as np
from . tool import check_crc, xor_decrypt,butter_lowpass_filter
from dotenv import load_dotenv
load_dotenv(override=True)
cutoff_freq = int(getenv("cutoff_freq"))  # 低通濾波器的截止頻率
Fs = int(getenv("Fs"))  # 取樣頻率

# FSK 解調
def fsk_demodulate(fsk_signal, bit_rate=1000, f0=1000, f1=2000, Fs=8000):
    samples_per_bit = Fs // bit_rate
    t = np.arange(len(fsk_signal)) / Fs

    ref_wave_0 = np.cos(2 * np.pi * f0 * t)
    ref_wave_1 = np.cos(2 * np.pi * f1 * t)

    demodulated_bits = np.zeros(len(fsk_signal) // samples_per_bit, dtype=int)

    for i in range(len(demodulated_bits)):
        bit_segment = fsk_signal[i * samples_per_bit:(i + 1) * samples_per_bit]
        match_0 = np.sum(bit_segment * ref_wave_0[i * samples_per_bit:(i + 1) * samples_per_bit])
        match_1 = np.sum(bit_segment * ref_wave_1[i * samples_per_bit:(i + 1) * samples_per_bit])
        demodulated_bits[i] = 1 if match_1 > match_0 else 0

    return demodulated_bits

# 語音反量化
def dequantize_audio(quantized_signal):
    dequantized_signal = quantized_signal.astype(np.float32) / 32767
    return dequantized_signal

# 解交錯並移除填充
def deinterleave(bits, pad_size, block_size=10):
    deinterleaved_bits = bits.reshape((block_size, -1)).T.flatten()  # 解交錯
    if pad_size > 0:
        deinterleaved_bits = deinterleaved_bits[:-pad_size]  # 移除填充的部分
    return deinterleaved_bits
# 解調變
def de_modual(fsk_signal_with_noise, pad_size, encoded_bits, time):
    # 接收端解調
    demodulated_bits = fsk_demodulate(fsk_signal_with_noise)

    # 驗證 CRC 校驗碼並印出結果
    try:
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

            decoded_audio = np.packbits(decrypted_bits[:len(encoded_bits)]).view(np.int16)  # 確保數據長度一致
            restored_audio_signal = dequantize_audio(decoded_audio)

            # 檢查還原音訊振幅
            print(f"Restored audio signal max: {np.max(restored_audio_signal)}")
            print(f"Restored audio signal min: {np.min(restored_audio_signal)}")

            # 再次進行低通濾波，過濾掉高頻噪音
            restored_audio_signal_filtered = butter_lowpass_filter(restored_audio_signal, cutoff_freq, Fs)

            # 放大信號，確保還原的音訊足夠大
            restored_audio_signal_filtered = restored_audio_signal_filtered * 10
            print("#Data restored.")
            return restored_audio_signal_filtered, restored_audio_signal, time
        else:
            print("CRC check failed. Data might be corrupted. Outputting corrupted signal.")
    except Exception as e:
        print(f"Error during CRC check or data restoration: {e}")