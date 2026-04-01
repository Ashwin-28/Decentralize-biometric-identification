import sys
import ctypes
import threading

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

WINBIO_TYPE_FINGERPRINT = 0x00000008
WINBIO_POOL_SYSTEM = 0x00000001
WINBIO_FLAG_DEFAULT = 0x00000000

def capture_with_gui():
    try:
        import tkinter as tk
        root = tk.Tk()
        root.title("Windows Hello Scan")
        root.geometry("350x120")
        root.attributes('-topmost', True)
        root.configure(bg='#1c1c1e')
        
        lbl = tk.Label(root, text="Touch your fingerprint sensor...", 
                       fg="white", bg="#1c1c1e", font=("Arial", 14))
        lbl.pack(expand=True)
        
        # Force focus to this window so WBF allows sensor capture
        root.focus_force()
        root.update()

        def do_scan():
            try:
                winbio = ctypes.WinDLL('winbio.dll')
                session_handle = ctypes.c_void_p()
                hr = winbio.WinBioOpenSession(
                    WINBIO_TYPE_FINGERPRINT,
                    WINBIO_POOL_SYSTEM,
                    WINBIO_FLAG_DEFAULT,
                    None, 0, None, ctypes.byref(session_handle)
                )
                if hr != 0:
                    print(f"ERROR: WinBioOpenSession failed: {hr}")
                    root.quit()
                    return

                unit_id = ctypes.c_uint32()
                identity = WINBIO_IDENTITY()
                subfactor = ctypes.c_uint8()
                reject_detail = ctypes.c_uint32()

                def cancel_capture():
                    winbio.WinBioCancel(session_handle)

                # Timeout after 15 seconds
                timer = threading.Timer(15.0, cancel_capture)
                timer.start()

                hr = winbio.WinBioIdentify(
                    session_handle,
                    ctypes.byref(unit_id),
                    ctypes.byref(identity),
                    ctypes.byref(subfactor),
                    ctypes.byref(reject_detail)
                )

                timer.cancel()
                winbio.WinBioCloseSession(session_handle)

                if hr == 0 or hr == 0x00040003: # S_OK or WINBIO_I_MORE_DATA
                    sf = subfactor.value  # Which finger was scanned
                    if identity.Type == 4: # SID
                        sid_bytes = bytes(identity.Value.AccountSid.Data[:identity.Value.AccountSid.Size])
                        print(f"SUCCESS: SID_{sid_bytes.hex()}_SF{sf}")
                    elif identity.Type == 3: # GUID
                        guid_bytes = bytes(identity.Value.TemplateGuid)
                        print(f"SUCCESS: GUID_{guid_bytes.hex()}_SF{sf}")
                    else:
                        print("ERROR: Unknown identity type")
                elif hr == 0x8009802B: # WINBIO_E_UNKNOWN_ID
                    print("UNKNOWN_ID")
                elif hr == 0x80098002 or hr == 0x80098034:
                    print("TIMEOUT")
                else:
                    print(f"ERROR: Identify returned {hr}")

            except Exception as e:
                print(f"ERROR: {e}")
            finally:
                root.quit()

        # Run scan in background thread so GUI stays responsive
        threading.Thread(target=do_scan, daemon=True).start()
        
        # Center the window on screen
        root.eval('tk::PlaceWindow . center')
        root.mainloop()
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    capture_with_gui()
