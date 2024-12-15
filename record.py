import os
import sounddevice as sd
import soundfile as sf
import numpy as np
from switch_data.SecondGeneration.send import simulate_fsk_transmission
from switch_data.SecondGeneration.receive import de_modual
input_file = ""
Fs = 8000

def record(gen_sin:bool=False):
    print("Recording started. Please speak...")
    if gen_sin:
    # 錄音
        # print(audio_signal)
        # 假資料(正弦波)
        fs = 44100 # Hz
        f = 440 # Hz
        length = 1 #s
        sound_ary = np.arange(fs * length)
        sound_ary = np.sin(2 * np.pi * f / fs * sound_ary)
        sd.play(sound_ary, fs)
        sd.wait()  # Wait until playback finishes
        return sound_ary
    else:
        duration = 5  # 錄音持續時間
        audio_signal = sd.rec(int(duration * Fs), samplerate=Fs, channels=1, dtype='float32')
        sd.wait()
        audio_signal = audio_signal.flatten()
        audio_signal = audio_signal / np.max(np.abs(audio_signal))  # 標準化
        return audio_signal

def send_audio():
    original_audio_signal = record()
    print(len(original_audio_signal))
    fsk_signal_with_noise, pad_size, encoded_bits_crc, time=simulate_fsk_transmission(original_audio_signal)
    return fsk_signal_with_noise, pad_size, encoded_bits_crc, time
    
if "__main__" == __name__:
    while True:
        print("1. Record and send audio")
        print("2. Receive and play audio")
        print("3. Exit")
        choice = input("Enter choice: ").strip()
        if choice == '1':
            fsk_signal_with_noise, pad_size, encoded_bits_crc, time = send_audio()
            print(f"Audio sent. Signal length: {len(fsk_signal_with_noise)}")
        elif choice == '2':
            restored_audio_signal_filtered, restored_audio_signal, time= de_modual(fsk_signal_with_noise, pad_size, encoded_bits_crc, time)
            print(f"restored_audio_signal_filtered {len(restored_audio_signal_filtered)}")
            sd.play(restored_audio_signal_filtered, Fs)
            sd.wait()
        elif choice == '3':
            break
        else:
            print("Invalid choice. Please try again.")
            continue
        input("Press Enter to continue...")