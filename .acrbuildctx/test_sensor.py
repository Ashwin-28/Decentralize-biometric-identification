import sys
import os
sys.path.append(os.getcwd())
from modules.fingerprint_reader import is_sensor_available
print(f"Sensor available: {is_sensor_available()}")
