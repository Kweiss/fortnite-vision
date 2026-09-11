import unittest

from PIL import Image

from droid_monitor.ocr import preprocess_for_ocr


class OcrPreprocessingTests(unittest.TestCase):
    def test_preprocessing_retains_rgb_color_information(self) -> None:
        source = Image.new("RGB", (12, 8), color=(255, 0, 200))

        processed = preprocess_for_ocr(source)

        self.assertEqual(processed.mode, "RGB")
        self.assertEqual(processed.size, (36, 24))
        self.assertGreater(processed.getpixel((18, 12))[0], 0)
        self.assertGreater(processed.getpixel((18, 12))[2], 0)
