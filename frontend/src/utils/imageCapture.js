/**
 * Utility to crop a base64 webcam image based on the biometric guide dimensions.
 * @param {string} imageSrc      - Base64 image from webcam
 * @param {string} biometricType - 'facial' | 'iris' | 'fingerprint'
 * @param {string} eyeSide       - 'left' | 'right'  (only used for iris)
 * @returns {Promise<string>}    - Cropped base64 image
 */
export const cropBiometricImage = (imageSrc, biometricType, eyeSide = 'left') => {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.src = imageSrc;
    img.onload = () => {
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');

      const videoWidth  = img.width;
      const videoHeight = img.height;
      const containerW  = 400;
      const scale       = videoWidth / containerW;

      let cropW, cropH, startX, startY;

      if (biometricType === 'iris') {
        // Periocular crop: wider than old iris, offset for L/R eye
        // Guide: 110px wide oval, offset ±60px from centre
        const guideW = 180;   // wider to capture periocular region
        const guideH = 130;
        const offsetPx = 60;  // matches CSS translateX(60px)

        cropW = guideW * scale;
        cropH = guideH * scale;

        // Centre of image
        const cx = videoWidth / 2;
        const cy = videoHeight / 2;

        // Left eye (person's left) = right side of image = positive X offset
        // Right eye (person's right) = left side of image = negative X offset
        const xOffset = eyeSide === 'left' ? offsetPx * scale : -offsetPx * scale;

        startX = cx + xOffset - cropW / 2;
        startY = cy - cropH / 2;

      } else if (biometricType === 'fingerprint') {
        // Fingerprint: centre rectangle
        const guideW = 180;
        const guideH = 240;
        cropW  = guideW * scale;
        cropH  = guideH * scale;
        startX = (videoWidth  - cropW) / 2;
        startY = (videoHeight - cropH) / 2;

      } else {
        // Facial: centre oval
        const guideW = 200;
        const guideH = 260;
        cropW  = guideW * scale;
        cropH  = guideH * scale;
        startX = (videoWidth  - cropW) / 2;
        startY = (videoHeight - cropH) / 2;
      }

      // Clamp to image bounds
      startX = Math.max(0, Math.min(startX, videoWidth  - cropW));
      startY = Math.max(0, Math.min(startY, videoHeight - cropH));

      canvas.width  = cropW;
      canvas.height = cropH;
      ctx.drawImage(img, startX, startY, cropW, cropH, 0, 0, cropW, cropH);

      resolve(canvas.toDataURL('image/jpeg', 0.92));
    };
    img.onerror = (err) => reject(err);
  });
};
