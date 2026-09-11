# Windows 11 OCR feasibility — 2026-07-18

## Conclusion

Yes: a Windows 11 equivalent is practical. The supplied macOS code cannot run unchanged because both `osascript` and Apple Vision are macOS-only. This project uses a local Python OCR stack for its first Windows build.

## Native Windows OCR

Microsoft's [`Windows.Media.Ocr`](https://learn.microsoft.com/en-us/uwp/api/windows.media.ocr?view=winrt-26100) provides OCR through `OcrEngine` and can recognize a `SoftwareBitmap`. It is a viable future option for a packaged Windows app.

However, Microsoft states that `Windows.Media.Ocr` is supported for desktop apps with **package identity**, which means an MSIX-installed app. Its [desktop WinRT guidance](https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/winrt-apis-desktop-apps) likewise calls out package identity for some APIs. Requiring MSIX and a WinRT bridge would make a first Python prototype harder to install and debug.

## Selected first-build engine

The project therefore uses [RapidOCR](https://github.com/rapidai/rapidocr) with ONNX Runtime. Its official install path is `pip install rapidocr onnxruntime`, it supports cross-platform deployment, and it runs recognition locally. This keeps capture and OCR in the user's process and avoids an additional Windows installer.

## Later packaging path

After crop calibration and alert parsing are proven on real Windows screenshots, the next build step can be a PyInstaller executable. If a single native Windows package is preferred after that, replacing the `RapidOcrEngine` adapter with `Windows.Media.Ocr` inside an MSIX-packaged desktop application is feasible without changing the capture, parsing, cooldown, or notification design.
