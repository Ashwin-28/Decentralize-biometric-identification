
import cv2
import numpy as np
import hashlib
from typing import Optional, List, Tuple

class FingerprintProcessor:
    """
    Fingerprint Processing Service logic as per requested specifications:
    - Preprocessing (Grayscale, Noise removal, Ridge enhancement)
    - Minutiae extraction (Endings, Bifurcations)
    - Template generation and Hashing (SHA256)
    """
    
    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold

    def preprocess(self, img_path: str) -> Optional[np.ndarray]:
        """Convert to grayscale, remove noise, and enhance ridges"""
        img = cv2.imread(img_path)
        if img is None:
            return None
        
        # 1. Grayscale conversion
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 2. Noise removal (Median blur)
        denoised = cv2.medianBlur(gray, 3)
        
        # 3. Ridge enhancement (CLAHE + Normalization)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)
        
        return enhanced

    def extract_minutiae(self, enhanced_img: np.ndarray) -> List[Tuple[int, int, float]]:
        """
        Extract minutiae points (Simplified demonstration logic)
        Format: [(x, y, angle), ...]
        """
        # Binarization for easier feature finding
        _, binary = cv2.threshold(enhanced_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        binary = cv2.bitwise_not(binary) # Invert to make ridges white
        
        # Skeletonization (Simplified using OpenCV)
        skeleton = self._skeletonize(binary)
        
        # Find minutiae (Endings and Bifurcations)
        minutiae = []
        rows, cols = skeleton.shape
        for i in range(1, rows - 1):
            for j in range(1, cols - 1):
                if skeleton[i, j] == 255:
                    # Check 8-neighbors
                    neighbors = [
                        skeleton[i-1, j-1], skeleton[i-1, j], skeleton[i-1, j+1],
                        skeleton[i, j-1],                     skeleton[i, j+1],
                        skeleton[i+1, j-1], skeleton[i+1, j], skeleton[i+1, j+1]
                    ]
                    # Count white neighbors
                    count = sum(1 for n in neighbors if n == 255)
                    
                    if count == 1: # Ridge Ending
                        minutiae.append((j, i, 0.0)) # (x, y, angle)
                    elif count == 3: # Bifurcation
                        minutiae.append((j, i, 45.0))
        
        # Limit to top 100 points for stable hashing
        return sorted(minutiae, key=lambda x: (x[1], x[0]))[:100]

    def _skeletonize(self, img):
        """Simple morphological skeletonization"""
        size = np.size(img)
        skel = np.zeros(img.shape, np.uint8)
        element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        done = False
        while not done:
            eroded = cv2.erode(img, element)
            temp = cv2.dilate(eroded, element)
            temp = cv2.subtract(img, temp)
            skel = cv2.bitwise_or(skel, temp)
            img = eroded.copy()
            zeros = size - cv2.countNonZero(img)
            if zeros == size:
                done = True
        return skel

    def generate_template_and_hash(self, minutiae: List[Tuple[int, int, float]]) -> Tuple[str, str]:
        """Generate string template and its SHA256 hash"""
        # Convert to stable string representation
        template_str = "|".join([f"{int(x)},{int(y)},{int(a)}" for x, y, a in minutiae])
        
        # Generate SHA256 hash
        fingerprint_hash = hashlib.sha256(template_str.encode()).hexdigest()
        
        return template_str, fingerprint_hash

    def get_similarity(self, template1: str, template2: str) -> float:
        """Compare two templates and return similarity score based on spatial point overlap.
        Instead of exact string matches (hash-like), we allow a small spatial tolerance.
        """
        if not template1 or not template2:
            return 0.0
            
        # Handle "stable" matching for demo/simulated sensors
        if "SIMULATED" in template1 or "SIMULATED" in template2:
            if "SIMULATED" in template1 and "SIMULATED" in template2:
                return 1.0
            return 0.0 # Don't match real with simulated
            
        def parse_points(t):
            pts = []
            for p in t.split("|"):
                try:
                    parts = p.split(",")
                    if len(parts) >= 2:
                        pts.append((int(parts[0]), int(parts[1])))
                except: continue
            return pts

        points1 = parse_points(template1)
        points2 = parse_points(template2)
        
        if not points1 or not points2:
            return 0.0
        
        # Count overlapping points within a 5-pixel radius (tolerance)
        tolerance = 5
        matches = 0
        used_p2 = [False] * len(points2)
        
        for x1, y1 in points1:
            for i, (x2, y2) in enumerate(points2):
                if not used_p2[i]:
                    dist = ((x1 - x2)**2 + (y1 - y2)**2)**0.5
                    if dist <= tolerance:
                        matches += 1
                        used_p2[i] = True
                        break
        
        # Calculate similarity score (Dice coefficient)
        score = (2.0 * matches) / (len(points1) + len(points2))
        
        print(f"[PROCESSOR] Matched {matches} points between {len(points1)} and {len(points2)}. Score: {score:.4f}")
        return score

    def verify(self, score: float) -> str:
        """Return MATCH or NOT MATCHED based on score"""
        return "MATCH" if score >= self.threshold else "NOT MATCHED"
