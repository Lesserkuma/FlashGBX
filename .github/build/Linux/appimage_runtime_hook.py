import ctypes, sys
from pathlib import Path

def load_fallback_libraries(directory):
	pending = {path.name: path for path in sorted(directory.glob("*.so*")) if path.is_file()}
	handles = {}
	errors = {}
	while pending:
		previous_count = len(pending)
		for name, path in list(pending.items()):
			try:
				try:
					handles[name] = ctypes.CDLL(name, mode=ctypes.RTLD_LOCAL)
				except OSError as error:
					if str(error.__cause__ or error) != f"{name}: cannot open shared object file: No such file or directory":
						raise
					handles[name] = ctypes.CDLL(str(path), mode=ctypes.RTLD_LOCAL)
				del pending[name]
				errors.pop(name, None)
			except OSError as error:
				errors[name] = str(error.__cause__ or error)
		# Retry only if newly loaded libraries may have resolved dependencies.
		if len(pending) == previous_count:
			break
	return handles, errors

if hasattr(sys, "_MEIPASS"):
	_appimage_libraries, _appimage_library_errors = load_fallback_libraries(
		Path(sys._MEIPASS) / "fallback-libs"
	)
	for _name, _error in _appimage_library_errors.items():
		print(f"FlashGBX: could not load library {_name}: {_error}", file=sys.stderr)
