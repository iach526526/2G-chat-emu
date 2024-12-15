import sounddevice as sd

# 全局參數
Fs = 8000  # 取樣頻率
BUFFER_SIZE = 1024  # 緩衝區大小，越小延遲越低，但可能導致卡頓

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
                output_stream.write(audio_data)
        except KeyboardInterrupt:
            print("\nMic-off: Stopping microphone.")

# 主程式入口
if __name__ == "__main__":
    try:
        microphone_loop()
    except Exception as e:
        print(f"Error: {e}")
