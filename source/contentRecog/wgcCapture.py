# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2026 Pratik Patel
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

"""Content recognizer using Windows.Graphics.Capture.
Captures window content via CreateForWindow (bypasses screen curtain),
then runs Windows.Media.Ocr. Drop-in alternative to UwpOcr.
"""

import json
from ctypes import c_uint
from typing import Optional, Callable

import NVDAHelper
from NVDAHelper.localWin10 import (
	wgcCapture_isSupported,
	wgcCapture_initialize,
	wgcCapture_recognizeWindow,
	wgcCapture_recognizeWindowRegion,
	wgcCapture_terminate,
	wgcCapture_Callback as _wgcCapture_Callback,
)
from contentRecog import (
	ContentRecognizer,
	LinesWordsResult,
	RecogImageInfo,
)
from logHandler import log
import winUser


def isSupported() -> bool:
	"""Check if WGC capture + OCR is available (Win10 1903+)."""
	try:
		dll = NVDAHelper.getHelperLocalWin10Dll()
		if dll is None:
			return False
		return wgcCapture_isSupported()
	except (OSError, AttributeError):
		return False


def _getRootWindow(hwnd: int) -> int:
	"""Walk up to the root owner window (required by CreateForWindow)."""
	root = winUser.getAncestor(hwnd, winUser.GA_ROOT)
	return root if root else hwnd


class WgcOcr(ContentRecognizer):
	"""OCR recognizer using Windows.Graphics.Capture.

	Works when screen curtain is active because WGC captures
	from the DWM compositor before the Magnification API transform.
	"""

	allowAutoRefresh: bool = True
	autoRefreshInterval: int = 1500

	def __init__(self, language: Optional[str] = None):
		from contentRecog.uwpOcr import getConfigLanguage
		self._language = language or getConfigLanguage()
		self._dll = NVDAHelper.getHelperLocalWin10Dll()
		self._handle = None
		self._onResult: Optional[Callable] = None
		self._cCallbackRef = None  # prevent GC of C callback

	@staticmethod
	def getResizeFactor(width: int, height: int):
		"""WGC captures at native resolution; no resize needed."""
		return 1

	def recognize(
		self,
		pixels,
		imageInfo: RecogImageInfo,
		onResult: Callable,
	):
		"""Capture the target window and run OCR.

		The pixels parameter is ignored; WGC captures its own frames
		via HWND. Kept for ContentRecognizer interface compatibility.
		"""
		self._onResult = onResult

		hwnd = self._getTargetHwnd(imageInfo)
		if not hwnd:
			log.error("wgcCapture: could not find target HWND")
			self._fireResult(None)
			return

		@_wgcCapture_Callback
		def _cCallback(resultJson):
			self._onCppResult(resultJson, imageInfo, hwnd)

		self._cCallbackRef = _cCallback

		self._handle = wgcCapture_initialize(
			self._language,
			self._cCallbackRef,
		)
		if not self._handle:
			log.error(
				"wgcCapture: failed to initialize (language=%s)",
				self._language,
			)
			self._fireResult(None)
			return

		windowRect = winUser.getWindowRect(hwnd)
		if windowRect:
			relX = max(0, imageInfo.screenLeft - windowRect[0])
			relY = max(0, imageInfo.screenTop - windowRect[1])
			wgcCapture_recognizeWindowRegion(
				self._handle,
				hwnd,
				c_uint(relX),
				c_uint(relY),
				c_uint(imageInfo.screenWidth),
				c_uint(imageInfo.screenHeight),
			)
		else:
			wgcCapture_recognizeWindow(
				self._handle,
				hwnd,
			)

	def _getTargetHwnd(
		self, imageInfo: RecogImageInfo
	) -> Optional[int]:
		"""Get the top-level HWND for the target screen location."""
		import api

		nav = api.getNavigatorObject()
		if nav and hasattr(nav, "windowHandle") and nav.windowHandle:
			return _getRootWindow(nav.windowHandle)

		# Fallback: WindowFromPoint at center of region
		centerX = imageInfo.screenLeft + imageInfo.screenWidth // 2
		centerY = imageInfo.screenTop + imageInfo.screenHeight // 2
		hwnd = winUser.user32.WindowFromPoint(
			winUser.POINT(centerX, centerY)
		)
		if hwnd:
			return _getRootWindow(hwnd)
		return None

	def _onCppResult(
		self,
		resultJson: Optional[str],
		imageInfo: RecogImageInfo,
		hwnd: int,
	):
		"""Parse C++ OCR JSON results into LinesWordsResult."""
		if not self._onResult:
			return

		if not resultJson:
			log.debugWarning("wgcCapture: OCR returned no results")
			self._fireResult(None)
			return

		try:
			data = json.loads(resultJson)
			self._fireResult(LinesWordsResult(data, imageInfo))
		except (json.JSONDecodeError, KeyError, TypeError) as e:
			log.error(
				"wgcCapture: failed to parse OCR result: %s", e
			)
			self._fireResult(None)

	def _fireResult(self, result):
		"""Fire the result callback and clean up C++ resources."""
		callback = self._onResult
		self._onResult = None
		self._cleanup()
		if callback:
			if result is None:
				callback(RuntimeError("WGC OCR failed"))
			else:
				callback(result)

	def _cleanup(self):
		"""Terminate the C++ WGC instance and release references."""
		if self._handle:
			wgcCapture_terminate(self._handle)
			self._handle = None
		self._cCallbackRef = None

	def cancel(self):
		"""Cancel any pending recognition."""
		self._onResult = None
		self._cleanup()

	def validateObject(self, nav) -> bool:
		"""WGC requires a valid HWND on the navigator object."""
		return bool(getattr(nav, "windowHandle", None))
