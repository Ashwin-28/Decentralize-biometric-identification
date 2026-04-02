"""
fingerprint_reader.py  —  Windows Biometric Framework Bridge
============================================================
Reads fingerprint images directly from your laptop's capacitive
power-button sensor using the Windows Biometric Framework (WBF).

Two methods:
  Method A: WinBio API (ctypes)       — works on Windows 10/11
  Method B: libfprint via subprocess  — fallback for Linux

Usage in your Flask backend:
  from modules.fingerprint_reader import capture_fingerprint_image
  image_path = capture_fingerprint_image(save_dir='uploads')
  features   = extract_fingerprint_features(image_path)
"""

import os
import sys
import ctypes
import tempfile
import subprocess
import numpy as np
from typing import Optional
from datetime import datetime

# -------------------------------------------------------
#  WINDOWS BIOMETRIC FRAMEWORK CONSTANTS
# -------------------------------------------------------
WINBIO_TYPE_FINGERPRINT     = 0x00000008
WINBIO_POOL_SYSTEM          = 0x00000001
WINBIO_FLAG_RAW             = 0x00000040
WINBIO_FLAG_DEFAULT         = 0x00000000
WINBIO_ANSI_381_IMG         = 0x00000003   # Raw image data type

WINBIO_NO_FORMAT_OWNER_AVAILABLE = 0x00000000
WINBIO_NO_FORMAT_TYPE_AVAILABLE  = 0x00000000

# Timeout: 15 seconds to place finger
CAPTURE_TIMEOUT_MS = 15000


# -------------------------------------------------------
#  WINDOWS BIOMETRIC FRAMEWORK STRUCTURES
# -------------------------------------------------------
class WINBIO_SESSION_HANDLE(ctypes.Structure):
    _fields_ = [("Value", ctypes.c_void_p)]


class WINBIO_BIR_HEADER(ctypes.Structure):
    _fields_ = [
        ("ValidFields",      ctypes.c_uint16),
        ("HeaderVersion",    ctypes.c_uint8),
        ("PatronHeaderVersion", ctypes.c_uint8),
        ("DataFlags",        ctypes.c_uint8),
        ("Type",             ctypes.c_uint32),
        ("Subtype",          ctypes.c_uint8),
        ("Purpose",          ctypes.c_uint8),
        ("DataQuality",      ctypes.c_int8),
        ("CreationDate",     ctypes.c_int64),
        ("ValidityPeriod",   ctypes.c_int64 * 2),
        ("BiometricDataFormat", ctypes.c_uint32 * 2),
        ("ProductID",        ctypes.c_uint32 * 2),
    ]


# -------------------------------------------------------
#  METHOD A: WinBio API  (Windows 10/11)
# -------------------------------------------------------
def _capture_via_winbio(save_path: str) -> bool:
    """
    Capture raw fingerprint image using Windows Biometric Framework.
    Saves as PNG to save_path.
    Returns True on success.
    """
    if sys.platform != 'win32':
        print("[FP-READER] WinBio: not on Windows")
        return False

    try:
        winbio = ctypes.WinDLL('winbio.dll')
    except OSError:
        print("[FP-READER] winbio.dll not found")
        return False

    try:
        import cv2

        # Open a biometric session
        session_handle = ctypes.c_void_p()
        hr = winbio.WinBioOpenSession(
            WINBIO_TYPE_FINGERPRINT,   # biometricType
            WINBIO_POOL_SYSTEM,        # poolType
            WINBIO_FLAG_RAW,           # flags (raw data)
            None,                      # unitArray
            0,                         # unitCount
            None,                      # databaseId
            ctypes.byref(session_handle)
        )
        if hr != 0:
            print(f"[FP-READER] WinBioOpenSession failed: 0x{hr:08X}")
            return False

        print("[FP-READER] Session opened. TOUCH (do not press) the sensor lightly...")

        # Capture sample
        unit_id    = ctypes.c_uint32()
        sample_ptr = ctypes.c_void_p()
        sample_size= ctypes.c_size_t()
        reject_detail = ctypes.c_uint32()

        hr = winbio.WinBioCaptureSample(
            session_handle,
            WINBIO_NO_FORMAT_OWNER_AVAILABLE,
            WINBIO_NO_FORMAT_TYPE_AVAILABLE,
            ctypes.byref(unit_id),
            ctypes.byref(sample_ptr),
            ctypes.byref(sample_size),
            ctypes.byref(reject_detail)
        )

        if hr != 0:
            print(f"[FP-READER] WinBioCaptureSample failed: 0x{hr:08X}")
            print(f"[FP-READER] Reject detail: {reject_detail.value}")
            if hr == 0x80098034: # WINBIO_E_TIMEOUT
                print("[FP-READER] Capture timed out (15s). Did you touch the sensor?")
            elif hr == 0x80098005: # WINBIO_E_BAD_CAPTURE
                print("[FP-READER] Bad capture. Try touching the sensor again.")
            winbio.WinBioCloseSession(session_handle)
            return False

        print(f"[FP-READER] Sample captured! Size={sample_size.value} bytes")

        # Parse BIR structure to get image data
        # BIR = Biometric Information Record
        # Layout: WINBIO_BIR header + data blocks
        sample_bytes = ctypes.string_at(sample_ptr, sample_size.value)

        # The raw image data starts after the BIR header
        # For ANSI/INCITS 381 format, image follows a fixed header
        # Try to extract raw pixel data (heuristic: look for image dimensions)
        image_data = _parse_bir_image(sample_bytes)

        # Free sample memory
        winbio.WinBioFree(sample_ptr)
        winbio.WinBioCloseSession(session_handle)

        if image_data is not None:
            cv2.imwrite(save_path, image_data)
            print(f"[FP-READER] Image saved: {save_path}  "
                  f"({image_data.shape[1]}x{image_data.shape[0]}px)")
            return True
        else:
            print("[FP-READER] Could not parse BIR image data")
            return False

    except Exception as e:
        print(f"[FP-READER] WinBio exception: {e}")
        return False

class WINBIO_IDENTITY_VALUE_SID(ctypes.Structure):
    _fields_ = [
        ("Size", ctypes.c_uint32),
        ("Data", ctypes.c_ubyte * 68)
    ]

class WINBIO_IDENTITY_VALUE(ctypes.Union):
    _fields_ = [
        ("Null", ctypes.c_uint32),
        ("Wildcard", ctypes.c_uint32),
        ("TemplateGuid", ctypes.c_ubyte * 16),
        ("AccountSid", WINBIO_IDENTITY_VALUE_SID)
    ]

class WINBIO_IDENTITY(ctypes.Structure):
    _fields_ = [
        ("Type", ctypes.c_uint32),
        ("Value", WINBIO_IDENTITY_VALUE)
    ]

def capture_fingerprint_vector() -> Optional[str]:
    """
    Capture fingerprint vector identity using Windows Hello (WinBioIdentify).
    Uses a child subprocess to spawn a tiny top-level GUI so the sensor is granted foreground focus.
    
    Returns:
      - Real SID/GUID + subfactor string when sensor works (deterministic per finger)
      - None when sensor fails (caller must handle this)
    """
    if sys.platform != 'win32':
        return None

    try:
        import subprocess
        script_path = os.path.join(os.path.dirname(__file__), 'winhello_capture.py')
        print("[FP-READER] Spawning foreground capture GUI...")
        
        # Run child script with 18 second timeout (GUI times out at 15s)
        res = subprocess.run([sys.executable, script_path], 
                             capture_output=True, text=True, timeout=18)
        
        output = res.stdout.strip()
        print(f"[FP-READER] Capture Process Output: {output}")
        
        # Parse output
        for line in output.split('\n'):
            line = line.strip()
            if line.startswith("SUCCESS: "):
                vector = line.split("SUCCESS: ")[1]
                print(f"[FP-READER] Real fingerprint vector captured: {vector[:20]}...")
                return vector
            elif line == "UNKNOWN_ID":
                print("[FP-READER] Finger not enrolled in Windows Hello")
                return "ERR_UNKNOWN_ID"
            elif line == "TIMEOUT":
                print("[FP-READER] Capture timed out - finger not detected")
                return "ERR_TIMEOUT"
            elif line.startswith("ERROR: "):
                print(f"[FP-READER] WinBio Error: {line}")
                return None
                
        # If we got here, subprocess exited unexpectedly
        err_out = res.stderr.strip()
        if err_out:
            print(f"[FP-READER] Subprocess Error: {err_out}")
            
        return None
            
    except subprocess.TimeoutExpired:
        print("[FP-READER] Subprocess timed out completely.")
        return None
    except Exception as e:
        print(f"[FP-READER] WinBio error: {e}")
        return None


def _parse_bir_image(bir_bytes: bytes) -> Optional[np.ndarray]:
    """
    Parse ANSI/INCITS 381-2004 fingerprint image record.
    Returns grayscale numpy array or None.
    """
    try:
        # ANSI 381 header structure:
        # Bytes 0-3: "FIR\0" magic
        # Bytes 4-5: version
        # Bytes 6-9: record length
        # Bytes 10-11: CBEFF product ID
        # Bytes 12-13: capture device ID
        # Bytes 14-15: image acquisition level
        # Bytes 16-17: number of fingers/palms
        # Bytes 18-19: scale units (1=PPI, 2=PPCM)
        # Bytes 20-21: X scan resolution
        # Bytes 22-23: Y scan resolution
        # Bytes 24-25: X image size (width)
        # Bytes 26-27: Y image size (height)
        # Bytes 28: pixel depth
        # Bytes 29: image compression algorithm
        # Then finger records follow

        if len(bir_bytes) < 32:
            return None

        # Try ANSI 381 parsing
        magic = bir_bytes[:4]
        if magic == b'FIR\x00':
            # Standard ANSI 381
            import struct
            # Each finger view header: 14 bytes
            # Offset to first finger: 36 bytes from start
            finger_offset = 36
            if len(bir_bytes) <= finger_offset + 14:
                return None

            # Finger view header:
            # 4 bytes: finger view length
            # 1 byte: finger position
            # 1 byte: count of views | view number
            # 1 byte: finger quality
            # 1 byte: impression type
            # 2 bytes: view width
            # 2 bytes: view height
            # 1 byte: reserved
            fv_len = struct.unpack_from('>I', bir_bytes, finger_offset)[0]
            width  = struct.unpack_from('>H', bir_bytes, finger_offset + 8)[0]
            height = struct.unpack_from('>H', bir_bytes, finger_offset + 10)[0]
            pixel_data_offset = finger_offset + 14

            expected = width * height
            available = len(bir_bytes) - pixel_data_offset

            if expected > 0 and available >= expected:
                pixels = np.frombuffer(
                    bir_bytes[pixel_data_offset:pixel_data_offset + expected],
                    dtype=np.uint8).reshape(height, width)
                return pixels

        # Fallback: treat raw bytes as raw pixels
        # Try common sensor sizes
        total = len(bir_bytes)
        for w, h in [(256, 360), (300, 400), (160, 160), (208, 288), (240, 320)]:
            if total >= w * h:
                # Skip first 'offset' bytes to find image
                for offset in [0, 28, 36, 44, 52]:
                    if total - offset >= w * h:
                        pixels = np.frombuffer(
                            bir_bytes[offset:offset + w*h],
                            dtype=np.uint8).reshape(h, w)
                        # Check it looks like a fingerprint
                        # (not all zeros or all 255)
                        if 10 < pixels.mean() < 245:
                            return pixels

        return None

    except Exception as e:
        print(f"[FP-READER] BIR parse error: {e}")
        return None


# -------------------------------------------------------
#  METHOD B: PowerShell Script  (Windows alternative)
# -------------------------------------------------------
def _capture_via_powershell(save_path: str) -> bool:
    """
    Use PowerShell with Windows.Devices.Enumeration + 
    Windows.Devices.Sensors to access fingerprint sensor.
    More compatible with consumer laptops than direct WinBio.
    """
    if sys.platform != 'win32':
        return False

    ps_script = r"""
Add-Type -AssemblyName System.Windows.Forms

# Use Windows Biometric Framework via P/Invoke
Add-Type @"
using System;
using System.Runtime.InteropServices;

public class WinBioCapture {
    [DllImport("winbio.dll")]
    public static extern int WinBioOpenSession(
        uint biometricType, uint poolType, uint flags,
        IntPtr unitArray, uint unitCount, IntPtr databaseId,
        out IntPtr sessionHandle);

    [DllImport("winbio.dll")]
    public static extern int WinBioCaptureSample(
        IntPtr sessionHandle, uint formatOwner, uint formatType,
        out uint unitId, out IntPtr sample, out uint sampleSize,
        out uint rejectDetail);

    [DllImport("winbio.dll")]
    public static extern int WinBioFree(IntPtr memory);

    [DllImport("winbio.dll")]
    public static extern int WinBioCloseSession(IntPtr sessionHandle);
}
"@

$WINBIO_TYPE_FINGERPRINT = 0x00000008
$WINBIO_POOL_SYSTEM = 0x00000001
$WINBIO_FLAG_RAW = 0x00000040

$sessionHandle = [IntPtr]::Zero
$hr = [WinBioCapture]::WinBioOpenSession(
    $WINBIO_TYPE_FINGERPRINT, $WINBIO_POOL_SYSTEM, $WINBIO_FLAG_RAW,
    [IntPtr]::Zero, 0, [IntPtr]::Zero, [ref]$sessionHandle)

if ($hr -ne 0) {
    Write-Error "WinBioOpenSession failed: 0x$($hr.ToString('X8'))"
    exit 1
}

Write-Host "TOUCH (do not press) the sensor lightly..."

$unitId = 0
$sample = [IntPtr]::Zero
$sampleSize = 0
$rejectDetail = 0

$hr = [WinBioCapture]::WinBioCaptureSample(
    $sessionHandle, 0, 0,
    [ref]$unitId, [ref]$sample, [ref]$sampleSize, [ref]$rejectDetail)

if ($hr -ne 0) {
    Write-Error "Capture failed: 0x$($hr.ToString('X8'))"
    [WinBioCapture]::WinBioCloseSession($sessionHandle)
    exit 1
}

# Read raw bytes
$bytes = New-Object byte[] $sampleSize
[System.Runtime.InteropServices.Marshal]::Copy($sample, $bytes, 0, $sampleSize)
[WinBioCapture]::WinBioFree($sample)
[WinBioCapture]::WinBioCloseSession($sessionHandle)

# Save raw bytes to file for Python to parse
[System.IO.File]::WriteAllBytes("$env:TEMP\fp_raw.bin", $bytes)
Write-Host "Saved $sampleSize bytes"
"""

    try:
        # Write script to temp file
        script_path = os.path.join(tempfile.gettempdir(), 'fp_capture.ps1')
        with open(script_path, 'w') as f:
            f.write(ps_script)

        result = subprocess.run(
            ['powershell', '-ExecutionPolicy', 'Bypass',
             '-File', script_path],
            capture_output=True, text=True, timeout=20)

        if result.returncode != 0:
            print(f"[FP-READER] PowerShell failed: {result.stderr}")
            return False

        # Read raw bin file and parse
        raw_path = os.path.join(tempfile.gettempdir(), 'fp_raw.bin')
        if not os.path.exists(raw_path):
            return False

        with open(raw_path, 'rb') as f:
            raw_bytes = f.read()

        img = _parse_bir_image(raw_bytes)
        if img is not None:
            import cv2
            cv2.imwrite(save_path, img)
            print(f"[FP-READER] PowerShell: image saved {img.shape}")
            return True

        return False

    except Exception as e:
        print(f"[FP-READER] PowerShell exception: {e}")
        return False


# -------------------------------------------------------
#  METHOD C: libfprint (Linux)
# -------------------------------------------------------
def _capture_via_libfprint(save_path: str) -> bool:
    """
    Use fprintd / libfprint on Linux.
    Run: sudo apt install fprintd python3-gi gir1.2-fprint-2.0
    """
    if sys.platform == 'win32':
        return False
    try:
        result = subprocess.run(
            ['fprintd-verify', '--finger', 'right-index-finger'],
            capture_output=True, text=True, timeout=15)
        print(f"[FP-READER] libfprint: {result.stdout}")
        # libfprint doesn't easily export raw images via CLI
        # This is just a verify path — for image export need Python GI bindings
        return False
    except Exception as e:
        print(f"[FP-READER] libfprint error: {e}")
        return False


# -------------------------------------------------------
#  PUBLIC API
# -------------------------------------------------------
def capture_fingerprint_image(save_dir: str = 'uploads',
                               filename:  str = None) -> Optional[str]:
    """
    Capture one fingerprint from the laptop sensor and save as PNG.

    Args:
        save_dir: Directory to save the image
        filename: Optional filename (auto-generated if None)

    Returns:
        Full path to saved PNG, or None on failure.

    Usage:
        path = capture_fingerprint_image(save_dir='backend/uploads')
        features = extract_fingerprint_features(path)
    """
    os.makedirs(save_dir, exist_ok=True)

    if filename is None:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        filename = f"fingerprint_{ts}.png"

    save_path = os.path.join(save_dir, filename)

    # Try methods in order
    print("[FP-READER] Attempting capture from sensor...")

    if _capture_via_winbio(save_path):
        return save_path

    if _capture_via_powershell(save_path):
        return save_path

    if _capture_via_libfprint(save_path):
        return save_path

    print("[FP-READER] All capture methods failed.")
    print("[FP-READER] Make sure:")
    print("  Windows: Windows Biometric Service is running")
    print("           (services.msc -> 'Windows Biometric Service' -> Started)")
    print("  Run backend as Administrator for raw sensor access")
    return None


def is_sensor_available() -> bool:
    """Check if a fingerprint sensor is accessible."""
    if sys.platform != 'win32':
        return False
    try:
        winbio = ctypes.WinDLL('winbio.dll')
        # Try to get unit count
        count = ctypes.c_size_t()
        hr = winbio.WinBioEnumBiometricUnits(
            WINBIO_TYPE_FINGERPRINT,
            ctypes.byref(ctypes.c_void_p()),
            ctypes.byref(count))
        available = (hr == 0 and count.value > 0)
        print(f"[FP-READER] Sensor available: {available} (units={count.value})")
        return available
    except Exception:
        return False
