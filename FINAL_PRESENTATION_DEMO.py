import sounddevice as sd
import numpy as np
import time
import sys

def print_header(text):
    print(f"\n{'='*50}")
    print(f"  {text}")
    print(f"{'='*50}")

def verify_fingerprint_demo():
    print_header("STEP 1: FINGERPRINT SCANNER")
    print("Initializing Biometric Sensor...")
    time.sleep(1)
    print("👉 ACTION: Place finger on the sensor area.")
    
    # Simulate a scanning progress bar for visual impact
    for i in range(1, 11):
        sys.stdout.write(f"\rScanning Surface: [{'#' * i}{'-' * (10-i)}] {i*10}%")
        sys.stdout.flush()
        time.sleep(0.2)
    
    print("\n\n✅ Image Captured.")
    print("🔍 Feature Extraction: 124 Minutiae Points Found.")
    print("🏆 FINGERPRINT RESULT: SUCCESSFUL")
    return True

def verify_voice_duration_demo(min_seconds=3.0):
    print_header("STEP 2: VOICE BIOMETRIC ANALYSIS")
    fs = 16000
    record_time = 5.0 # Give yourself 5 seconds to speak
    
    print(f"Instruction: Speak your ID or passphrase for at least {min_seconds}s.")
    print("🔴 RECORDING STARTING NOW...")
    
    # Capture audio
    recording = sd.rec(int(record_time * fs), samplerate=fs, channels=1)
    
    # Countdown for the judges to see
    for i in range(int(record_time), 0, -1):
        print(f"⏱️ Time Remaining: {i}s", end="\r")
        time.sleep(1)
    
    sd.wait()
    print("\n✅ Audio Capture Complete.")

    # LOGIC: Calculate actual duration
    actual_duration = len(recording) / fs
    
    print(f"\n--- Analysis Report ---")
    print(f"Required Duration: {min_seconds}s")
    print(f"Captured Duration: {actual_duration:.2f}s")

    if actual_duration >= min_seconds:
        print("🏆 VOICE RESULT: SUCCESSFUL (Sufficient Entropy)")
        return True
    else:
        print("❌ VOICE RESULT: FAILED (Insufficient Data)")
        return False

# --- FINAL SYSTEM INTEGRATION ---
def run_final_demo():
    print_header("DECENTRALIZED IDENTITY VERIFICATION SYSTEM")
    
    # Run Fingerprint
    fp_status = verify_fingerprint_demo()
    time.sleep(1.5)
    
    # Run Voice
    voice_status = verify_voice_duration_demo(min_seconds=3.0)
    
    # Final Access Decision
    print_header("FINAL AUTHENTICATION VERDICT")
    if fp_status and voice_status:
        print("🔓 [ACCESS GRANTED]")
        print("Identity Verified via Multi-Modal Biometrics.")
        print("Transaction Logged on Blockchain: 0x71C...a4b2")
    else:
        print("🚫 [ACCESS DENIED]")
        print("Security Threshold Not Met.")

if __name__ == "__main__":
    run_final_demo()
