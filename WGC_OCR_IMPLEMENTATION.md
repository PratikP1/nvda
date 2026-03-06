# Windows Graphics Capture (WGC) OCR Implementation

## Overview

This implementation addresses [Issue #19164](https://github.com/nvaccess/nvda/issues/19164) by enabling OCR to work when screen curtain is active. The solution uses the Windows.Graphics.Capture API to capture window content directly from the DWM compositor, bypassing the Magnification API color transform that blacks out the screen.

## Original Contribution

This implementation is based on the code contributed by **Pratik Patel (@PratikP1)** in [comment #4010347709](https://github.com/nvaccess/nvda/issues/19164#issuecomment-4010347709) of Issue #19164.

The original research and implementation approach was suggested by:
- **@matt@toot.cafe** and **@mwcampbell** - Proposed using Windows.Graphics.Capture API
- **@ppatel@mstdn.social** (@PratikP1) - Researched compatibility and developed the implementation
- **@gexgd0419** - Identified the Windows.Graphics.Capture API requirements

## Technical Details

### How It Works

1. **Screen Curtain Detection**: When OCR is invoked, the code checks if screen curtain is active
2. **Automatic Fallback**: If screen curtain is active and WGC is supported (Windows 10 1903+), the recognizer automatically switches to WGC-based OCR
3. **Direct Window Capture**: WGC captures window content from the DWM compositor before the magnification API applies the black color transform
4. **Seamless Integration**: No user configuration needed - the system automatically chooses the best capture method

### Files Modified

#### C++ Implementation
- **nvdaHelper/localWin10/wgcCapture.h**: Header defining the WGC capture API
- **nvdaHelper/localWin10/wgcCapture.cpp**: C++ implementation using WinRT APIs
  - Uses Direct3D 11 for hardware acceleration
  - Implements CreateForWindow to capture from DWM compositor
  - Integrates with Windows.Media.Ocr for text recognition
  - Returns JSON-formatted OCR results

#### Build System
- **nvdaHelper/localWin10/sconscript**: Updated to build wgcCapture.cpp with d3d11 and dxgi libraries

#### Python Bindings
- **source/NVDAHelper/localWin10.py**: Added ctypes bindings for WGC functions
  - `wgcCapture_isSupported()`: Check if WGC is available
  - `wgcCapture_initialize()`: Create WGC capture instance
  - `wgcCapture_recognizeWindow()`: Capture entire window
  - `wgcCapture_recognizeWindowRegion()`: Capture window region
  - `wgcCapture_terminate()`: Clean up resources

#### Python Implementation
- **source/contentRecog/wgcCapture.py**: New ContentRecognizer implementation
  - Drop-in replacement for UwpOcr when screen curtain is active
  - Automatically detects target window from navigator object
  - Supports region-based capture for partial window recognition

#### Integration
- **source/contentRecog/recogUi.py**: Modified to automatically switch to WGC when screen curtain is active
  - Detects screen curtain state
  - Switches recognizer to WgcOcr if supported
  - Shows user-friendly message if WGC not available (Windows < 1903)

- **source/globalCommands.py**: Removed screen curtain blocking from OCR script
  - Previously blocked OCR when screen curtain was active
  - Now allows OCR to proceed (handled by recogUi)

## System Requirements

- **Windows Version**: Windows 10 Version 1903 (May 2019 Update) or later
- **APIs Used**:
  - Windows.Graphics.Capture
  - Windows.Media.Ocr
  - Direct3D 11
  - DXGI

## Testing Requirements

### Prerequisites
1. Windows 10 Version 1903 or later
2. NVDA built with the WGC implementation
3. Windows OCR language pack installed

### Test Scenarios

#### Test 1: OCR Without Screen Curtain (Regression Test)
1. Ensure screen curtain is disabled
2. Navigate to an object with text
3. Press NVDA+R to perform OCR
4. **Expected**: OCR should work as before using standard UwpOcr

#### Test 2: OCR With Screen Curtain (New Feature)
1. Enable screen curtain (NVDA+Control+Escape)
2. Navigate to an object with text
3. Press NVDA+R to perform OCR
4. **Expected**:
   - OCR should succeed using WGC
   - Debug log should show "recogUi: screen curtain active, using WGC capture"
   - Screen remains black (screen curtain active)
   - OCR results are displayed correctly

#### Test 3: OCR With Screen Curtain on Older Windows
1. Test on Windows 10 Version 1809 or earlier
2. Enable screen curtain
3. Press NVDA+R to perform OCR
4. **Expected**: User receives message: "Screen curtain is active. OCR requires Windows 10 version 1903 or later to work with screen curtain enabled. Please disable screen curtain or upgrade Windows."

#### Test 4: Window Selection
1. Enable screen curtain
2. Navigate to different objects in different windows
3. Perform OCR on each
4. **Expected**: WGC correctly identifies and captures the target window

#### Test 5: Region-Based OCR
1. Enable screen curtain
2. Use review cursor to select a specific screen region
3. Perform OCR
4. **Expected**: Only the selected region is recognized

#### Test 6: Language Selection
1. Enable screen curtain
2. Cycle through OCR languages (if multiple installed)
3. Perform OCR
4. **Expected**: WGC uses the selected language correctly

### Debug Logging

To enable debug logging for troubleshooting:
1. Set NVDA logging level to "Debug"
2. Look for messages prefixed with "wgcCapture:" or "recogUi:" in the log

### Known Limitations

1. **Window Handle Required**: WGC requires a valid window handle. Objects without window handles will fall back to standard OCR (if screen curtain is off)
2. **Yellow Border**: On Windows 11, a brief yellow border may appear around captured windows (can be disabled in code)
3. **Performance**: WGC capture may have slightly different performance characteristics than GDI capture

## Build Instructions

1. Ensure Visual Studio 2022 is installed with Windows 10 SDK 10.0.26100.x or later
2. Clone the NVDA repository with `--recursive` flag
3. Run the standard NVDA build process (requires uv, Python 3.13.12)
4. The build system will automatically compile wgcCapture.cpp and link with d3d11.lib and dxgi.lib

## Code Quality

- Python files pass `py_compile` syntax checks
- Code follows NVDA's existing patterns and conventions
- C++ code uses modern C++/WinRT coroutines for async operations
- Proper error handling with logging throughout

## Future Enhancements

Potential improvements for future PRs:
1. Add configuration option to force WGC mode always (not just with screen curtain)
2. Optimize frame capture timing for faster OCR
3. Add support for multi-monitor scenarios
4. Investigate using WGC for screenshot functionality

## Credits

- **Implementation**: Pratik Patel (@PratikP1)
- **Research & Testing**: Pratik Patel, @kaveinthran, @gexgd0419
- **Original Suggestion**: @matt@toot.cafe, @mwcampbell
- **Issue Reporter**: @SaschaCowley
- **Code Review & Integration**: Claude AI assistant
