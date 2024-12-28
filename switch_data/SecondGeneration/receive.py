from os import getenv
import numpy as np
import binascii
from .tool import xor_decrypt, butter_lowpass_filter
from dotenv import load_dotenv
load_dotenv(override=True)
cutoff_freq = int(getenv("cutoff_freq"))  # 低通濾波器的截止頻率
Fs = int(getenv("Fs"))  # 取樣頻率

def generate_crc(data_bits):
    data_bytes = np.packbits(data_bits).tobytes()
    crc_value = binascii.crc_hqx(data_bytes, 0xFFFF)  # 使用CRC-16校驗
    crc_bits = np.unpackbits(np.array([crc_value >> 8, crc_value & 0xFF], dtype=np.uint8))
    print(f"Generated CRC: 0x{crc_value:04x}")
    return np.concatenate([data_bits, crc_bits])
# 解調變
def de_modual(fsk_signal, pad_size, encoded_bits, time):
    try:
        # 解調 FSK 信號
        bit_rate = 1000
        f0 = 1000
        f1 = 2000
        samples_per_bit = Fs // bit_rate
        t = np.arange(len(fsk_signal)) / Fs

        # 預先計算頻率基準信號
        ref_wave_0 = np.cos(2 * np.pi * f0 * t)
        ref_wave_1 = np.cos(2 * np.pi * f1 * t)

        # 使用 numpy 向量化運算來處理每個 bit
        num_bits = len(fsk_signal) // samples_per_bit
        demodulated_bits = np.zeros(num_bits, dtype=int)

        # 先計算每一段的起始和結束索引
        indices = np.arange(num_bits)[:, None] * samples_per_bit
        start_indices = indices
        end_indices = indices + samples_per_bit

        # 生成 2D 切片矩陣以提取對應的信號段
        bit_segments = np.array([fsk_signal[start:end] for start, end in zip(start_indices, end_indices)])

        # 計算結果矩陣
        matches_0 = np.sum(bit_segments * ref_wave_0[start_indices:end_indices], axis=1)
        matches_1 = np.sum(bit_segments * ref_wave_1[start_indices:end_indices], axis=1)

        # 判斷 demodulated_bits
        demodulated_bits = (matches_1 > matches_0).astype(int)

        # 驗證 CRC 校驗碼
        data_bits = demodulated_bits[:-16]  # 提取原始數據
        crc_received = demodulated_bits[-16:]  # 提取CRC校驗碼
        expected_crc = generate_crc(data_bits)[-16:]  # 重新生成校驗碼
        crc_check_passed = np.array_equal(crc_received, expected_crc)
        print("CRC check passed:", crc_check_passed)

        if crc_check_passed:
            decoded_bits = demodulated_bits[:-16]  # 去除CRC位元
            # 解交錯並移除填充
            block_size = 10
            # 使用reshape來解交錯並去除填充
            deinterleaved_bits = decoded_bits.reshape((block_size, -1)).T.flatten()
            if pad_size > 0:
                deinterleaved_bits = deinterleaved_bits[:-pad_size]  # 移除填充的部分
            print("Data deinterleaved.")

            # 解密
            decrypted_bits = xor_decrypt(deinterleaved_bits)
            print("Data decrypted.")
            # 將解密的位元轉換回音訊數據
            decoded_audio = np.packbits(decrypted_bits[:len(encoded_bits)]).view(np.int16)

            # 反量化音訊
            restored_audio_signal = decoded_audio.astype(np.float32) / 32767
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
