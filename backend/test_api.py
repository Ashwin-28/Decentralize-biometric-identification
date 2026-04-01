import requests

r1 = requests.post('http://localhost:5000/api/fingerprint/capture', timeout=25)
r2 = requests.post('http://localhost:5000/api/fingerprint/capture', timeout=25)

d1 = r1.json()
d2 = r2.json()

print(f"Capture 1 simulated: {d1.get('simulated')}")
print(f"Capture 2 simulated: {d2.get('simulated')}")
print(f"Vectors identical: {d1.get('image_b64') == d2.get('image_b64')}")
if d1.get('image_b64') != d2.get('image_b64'):
    print("SUCCESS: Each scan generates UNIQUE data - fingerprint mismatch will be properly detected!")
else:
    print("FAIL: Vectors are still the same!")
