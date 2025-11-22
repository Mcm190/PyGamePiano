import os
import wave
import numpy as np

# --- CONFIGURATION ---
SOURCE_FOLDER = "assets/sounds"
OUTPUT_FOLDER = "assets/sounds/final"
TARGET_PEAK = 0.9 
IDEAL_VELOCITY = 12 
NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

def parse_file_info(filename):
    """ 
    Returns (midi_number, velocity) or (None, None)
    Handles both 'A0v1.wav' and '21.wav' 
    """
    if filename.startswith('.'): return None, None
    if any(x in filename for x in ['rel', 'harm', 'pedal', 'stac']): return None, None

    name = os.path.splitext(filename)[0]
    
    # CASE 1: Numbered File (e.g., "60.wav")
    if name.isdigit():
        return int(name), IDEAL_VELOCITY # Assume it's good if it's already numbered

    # CASE 2: Named File (e.g., "C4v12.wav")
    try:
        parts = name.split('v')
        base_name = parts[0]
        
        # Extract Velocity
        velocity = IDEAL_VELOCITY # Default
        if len(parts) > 1 and parts[1].isdigit():
            velocity = int(parts[1])
            
        if len(base_name) < 2: return None, None

        if base_name[1] == '#':
            note_str = base_name[:2]
            octave = int(base_name[2:])
        else:
            note_str = base_name[:1]
            octave = int(base_name[1:])
            
        midi = 12 + (octave * 12) + NOTES.index(note_str)
        return midi, velocity
    except:
        return None, None

def load_wav(path):
    with wave.open(path, 'rb') as f:
        frames = f.readframes(f.getnframes())
        data = np.frombuffer(frames, dtype=np.int16)
        if f.getnchannels() == 2: data = data[::2]
        return data, f.getframerate()

def save_wav(path, data, rate=44100):
    with wave.open(path, 'wb') as f:
        f.setnchannels(1) 
        f.setsampwidth(2) 
        f.setframerate(rate)
        f.writeframes(data.tobytes())

def change_pitch(data, semitones):
    if semitones == 0: return data
    factor = 2 ** (semitones / 12.0)
    old_indices = np.arange(len(data))
    new_indices = np.linspace(0, len(data) - 1, int(len(data) / factor))
    new_data = np.interp(new_indices, old_indices, data)
    return new_data.astype(np.int16)

def normalize_audio(data):
    float_data = data.astype(np.float32)
    current_max = np.max(np.abs(float_data))
    if current_max == 0: return data
    gain = (32767 * TARGET_PEAK) / current_max
    normalized = float_data * gain
    return np.clip(normalized, -32767, 32767).astype(np.int16)

def build():
    if not os.path.exists(SOURCE_FOLDER):
        print(f"ERROR: Source folder '{SOURCE_FOLDER}' does not exist.")
        return
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    print(f"Scanning '{SOURCE_FOLDER}'...")
    
    best_samples = {}
    files_seen = 0
    
    for f in os.listdir(SOURCE_FOLDER):
        if f.endswith(".wav"):
            files_seen += 1
            midi, vel = parse_file_info(f)
            
            if midi is not None:
                full_path = os.path.join(SOURCE_FOLDER, f)
                
                if midi not in best_samples:
                    best_samples[midi] = {'path': full_path, 'velocity': vel}
                else:
                    # Compare velocities to find the best one
                    curr_diff = abs(best_samples[midi]['velocity'] - IDEAL_VELOCITY)
                    new_diff = abs(vel - IDEAL_VELOCITY)
                    if new_diff < curr_diff:
                        best_samples[midi] = {'path': full_path, 'velocity': vel}

    print(f"Scanned {files_seen} files.")
    print(f"Found {len(best_samples)} unique usable notes.")

    if len(best_samples) == 0:
        print("CRITICAL ERROR: No valid note files found.")
        print("Please ensure your 'assets/sounds' folder contains .wav files.")
        print("Example valid name: 'A0v1.wav' OR '21.wav'")
        return

    print("Generating normalized piano keys...")
    
    for target_midi in range(21, 109):
        dst_path = os.path.join(OUTPUT_FOLDER, f"{target_midi}.wav")
        
        # Source MIDI to use (Exact or Neighbor)
        if target_midi in best_samples:
            source_midi = target_midi
        else:
            source_midi = min(best_samples.keys(), key=lambda x: abs(x - target_midi))
            
        diff = target_midi - source_midi
        src_info = best_samples[source_midi]
        
        # Process
        try:
            data, rate = load_wav(src_info['path'])
            if diff != 0:
                print(f"Key {target_midi}: Pitching {source_midi} by {diff} steps")
                data = change_pitch(data, diff)
            
            data = normalize_audio(data)
            save_wav(dst_path, data, 44100)
        except Exception as e:
            print(f"Error processing key {target_midi}: {e}")

    print("\nSUCCESS! Piano built in 'assets/sounds/final'")

if __name__ == "__main__":
    build()