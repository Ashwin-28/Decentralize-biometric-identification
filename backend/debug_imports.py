
import sys

def test_import(module_name):
    print(f"Testing import of {module_name}...")
    try:
        __import__(module_name)
        print(f"[OK] {module_name} imported successfully")
        return True
    except Exception as e:
        print(f"[FAIL] {module_name} failed: {e}")
        import traceback
        traceback.print_exc()
        return False

modules = [
    "flask",
    "web3",
    "cv2",
    "numpy",
    "deepface",
    "librosa",
    "speech_recognition",
    "tensorflow",
    "torch",
    "torchvision"
]

for m in modules:
    test_import(m)
    print("-" * 20)
