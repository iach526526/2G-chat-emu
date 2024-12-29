import sounddevice as sd
import numpy as np
# import matplotlib.pyplot as plt
import switch_data.SecondGeneration.receive as receive
import switch_data.SecondGeneration.send as send
import threading

# 全局參數
Fs = 8000  # 取樣頻率
BUFFER_SIZE = 512  # 緩衝區大小，越小延遲越低，但可能導致卡頓

def microphone_loop():
    """實現即時錄音並播放的麥克風功能"""
    print("Mic-on: Speak into the microphone. Press Ctrl+C to stop.")

    # 使用 InputStream 和 OutputStream 即時處理音訊
    with sd.InputStream(samplerate=Fs, channels=1, blocksize=BUFFER_SIZE) as input_stream, \
         sd.OutputStream(samplerate=Fs, channels=1, blocksize=BUFFER_SIZE) as output_stream:

        try:
            while True:
                # 從麥克風獲取音訊數據
                audio_data, overflow = input_stream.read(BUFFER_SIZE)
                if overflow:
                    print("Buffer overflow detected!")  # 提醒使用者有緩衝區溢出的情況
                # 將音訊數據直接播放
                send.fsk_signal_with_noise, send.pad_size, send.encoded_bits_crc= send.simulate_fsk_transmission(audio_data)
                receive.restored_audio_signal_filtered= receive.de_modual(send.fsk_signal_with_noise, send.pad_size, send.encoded_bits_crc)
                receive.restored_audio_signal_filtered = np.array(receive.restored_audio_signal_filtered, dtype='float32')
                # output_stream.write(receive.restored_audio_signal_filtered)
                output_stream.write(receive.restored_audio_signal_filtered)
        except KeyboardInterrupt:
            print("\nMic-off: Stopping microphone.")

# 主程式入口
if __name__ == "__main__":
    try:
        microphone_loop()
        threading.Thread(target=microphone_loop,daemon=True).start()
        
    except Exception as e:
        print(f"Error: {e}")
