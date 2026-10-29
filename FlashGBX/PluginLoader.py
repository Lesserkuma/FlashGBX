# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import ast, configparser, hashlib, importlib.util, json, os, platform, sys

from .i18n import __, c__
from .IniSettings import IniSettings

PLUGINS_INITIALIZED = False
PLUGINS = {}

def _GetSettings(config_path, main_section="Plugins"):
	settings = IniSettings(path=os.path.join(config_path, "settings.ini"), main_section=main_section)
	if settings.SETTINGS is None:
		raise OSError("Could not access plugin settings")
	return settings

def _GetPluginDirectory(config_path):
	path = _GetSettings(config_path, main_section="General").value("PluginDirectory", default="").strip()
	return os.path.abspath(os.path.join(config_path, os.path.expanduser(path) if path else "plugins"))

def _SavePluginSettings(config_path, filename, digest, enabled):
	_GetSettings(config_path).setValue(filename, json.dumps({"sha256": digest, "enabled": enabled}))

def _DeletePlugin(config_path, filename):
	plugin_dir = _GetPluginDirectory(config_path)
	path = os.path.abspath(os.path.join(plugin_dir, filename))
	if os.path.dirname(path) != plugin_dir:
		raise ValueError("Invalid plugin path")
	try:
		os.remove(path)
	except FileNotFoundError:
		pass
	_GetSettings(config_path).setValue(filename, None)
	PLUGINS.pop(filename, None)

def _MigrateApprovals(config_path, settings):
	path = os.path.join(config_path, "plugins.json")
	try:
		with open(path, "r", encoding="utf-8") as f:
			approvals = json.load(f)
		if not isinstance(approvals, dict):
			raise ValueError("Invalid plugin approvals")
		for filename, digest in approvals.items():
			if isinstance(digest, str) and settings.value(filename) is None:
				_SavePluginSettings(config_path, filename, digest, True)
		os.remove(path)
	except FileNotFoundError:
		pass
	except (OSError, ValueError, configparser.Error) as error:
		print("Could not migrate plugin approvals: {}".format(error))

def AddPluginMenu(parent, parent_menu, config_path):
	from .pyside import QtCore, QtWidgets
	from .app import AppInfo
	if not PLUGINS: return
	mnuPlugins = parent_menu.addMenu(__("Plugins"))

	def ManagePlugin(filename):
		plugin = PLUGINS[filename]
		msgbox = QtWidgets.QMessageBox(parent)
		msgbox.setWindowTitle("{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION))
		msgbox.setIcon(QtWidgets.QMessageBox.Question)
		msgbox.setTextFormat(QtCore.Qt.PlainText)
		details = [
			c__("Plugin management", "How would you like to manage this plugin?"),
			"",
			c__("Plugin management", "Name:") + " " + plugin["name"],
		]
		if plugin.get("version"):
			details.append(c__("Plugin loading", "Version: {version}", version=plugin["version"]))
		if plugin.get("description"):
			details.append(c__("Plugin loading", "Description: {description}", description=plugin["description"]))
		msgbox.setText("\n".join(details + [
			c__("Plugin management", "File:") + " " + filename,
			c__("Plugin management", "Load at startup:") + " " +  (c__("Plugin management", "Enabled") if plugin["enabled"] else c__("Plugin management", "Disabled")),
		]))
		msgbox.setInformativeText(c__("Plugin management", "Deleting permanently removes the plugin file."))
		button_toggle = msgbox.addButton(__("Disable") if plugin["enabled"] else __("Enable"), QtWidgets.QMessageBox.ActionRole)
		button_delete = msgbox.addButton(__("Delete"), QtWidgets.QMessageBox.DestructiveRole)
		button_cancel = msgbox.addButton(QtWidgets.QMessageBox.Cancel)
		msgbox.setDefaultButton(button_cancel)
		msgbox.setEscapeButton(button_cancel)
		(getattr(msgbox, "exec", None) or msgbox.exec_)()
		button_clicked = msgbox.clickedButton()
		if button_clicked not in (button_toggle, button_delete): return
		try:
			enabled = not plugin["enabled"] if button_clicked is button_toggle else False
			_SavePluginSettings(config_path, filename, plugin["sha256"], enabled)
			plugin["enabled"] = enabled
			if button_clicked is button_delete:
				_DeletePlugin(config_path, filename)
		except (OSError, ValueError, configparser.Error) as error:
			QtWidgets.QMessageBox.critical(parent, AppInfo.NAME, __("Could not update plugin settings.") + "\n" + str(error))
		else:
			if button_clicked is button_delete:
				msg = c__("Plugin loading", "The plugin file has been deleted.") + "\n\n" + filename + "\n\n" + c__("Plugin loading", "If the plugin was already loaded, restart FlashGBX to stop using it.")
			elif enabled:
				msg = c__("Plugin loading", "The plugin has been enabled.") + "\n\n" + c__("Plugin loading", "Restart FlashGBX to load it.")
			else:
				msg = c__("Plugin loading", "The plugin has been disabled.") + "\n\n" + c__("Plugin loading", "Restart FlashGBX for this change to take effect.")
			QtWidgets.QMessageBox.information(parent, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), msg)
		RefreshMenu()

	def RefreshMenu():
		mnuPlugins.clear()
		mnuPlugins.setTitle(__("Plugins"))
		mnuPlugins.menuAction().setVisible(bool(PLUGINS))
		for filename, plugin in PLUGINS.items():
			label = plugin["name"]
			if sum(item["name"] == label for item in PLUGINS.values()) > 1:
				label += " ({})".format(filename)
			if not plugin["enabled"]:
				label += " ({})".format(__("Disabled"))
			action = mnuPlugins.addAction(label.replace("&", "&&"))
			action.setCheckable(True)
			action.setChecked(plugin["enabled"])
			action.triggered.connect(lambda checked=False, filename=filename: ManagePlugin(filename))

	mnuPlugins.aboutToShow.connect(RefreshMenu)
	RefreshMenu()

def _GetPluginMetadata(source, filename):
	metadata = {"name": None}
	fields = {"PLUGIN_NAME": "name", "PLUGIN_DESCRIPTION": "description", "PLUGIN_VERSION": "version"}
	try:
		for node in ast.parse(source, filename=filename).body:
			if isinstance(node, ast.Assign):
				targets = node.targets
			elif isinstance(node, ast.AnnAssign):
				targets = [node.target]
			else:
				continue
			if any(isinstance(target, ast.Name) and target.id in fields for target in targets):
				try:
					value = ast.literal_eval(node.value)
				except (ValueError, TypeError):
					continue
				if isinstance(value, str) and value.strip():
					for target in targets:
						if isinstance(target, ast.Name) and target.id in fields:
							metadata[fields[target.id]] = value.strip()
	except (SyntaxError, ValueError):
		pass
	return metadata

def _GetPluginName(source, filename):
	return _GetPluginMetadata(source, filename)["name"]

def _ConfirmPlugin(filename, digest, gui, config_path=None, name=None, description=None, version=None):
	details = [
		c__("Plugin loading", "Plugin: {filename}", filename=filename),
		c__("Plugin loading", "Name: {name}", name=name or filename[:-3]),
	]
	if version:
		details.append(c__("Plugin loading", "Version: {version}", version=version))
	if description:
		details.append(c__("Plugin loading", "Description: {description}", description=description))
	details.append("")
	details += ["SHA-256:", digest]
	msg = "\n\n".join((
		c__("Plugin loading", "A new plugin has been found in the plugins directory."),
		"\n".join(details),
		" ".join((
			c__("Plugin loading", "This plugin contains executable Python code and runs with the same permissions as FlashGBX."),
			c__("Plugin loading", "Only load plugins from trusted sources."),
		)),
	))
	if gui:
		from .app import AppInfo
		from .IniSettings import IniSettings
		from .pyside import QApplication, QtCore, QtGui, QtWidgets, GetQtVersion, IsDarkMode
		qt_app = QApplication.instance()
		if qt_app is None: return None
		try:
			if config_path is not None and GetQtVersion() >= (6, 5, 0):
				settings = IniSettings(path=os.path.join(config_path, "settings.ini"))
				if settings.value("AllowDarkMode", default="enabled") == "disabled":
					QtGui.QGuiApplication.styleHints().setColorScheme(QtCore.Qt.ColorScheme.Light)
			if platform.system() == "Windows":
				qt_app.setStyle("fusion" if IsDarkMode() else "windowsvista")
		except (AttributeError, OSError, RuntimeError, TypeError):
			pass
		msgbox = QtWidgets.QMessageBox()
		msgbox.setWindowTitle("{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION))
		icon_filename = "icon.png" if platform.system() == "Linux" else "icon.ico"
		msgbox.setWindowIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__), "res", icon_filename)))
		msgbox.setStyleSheet("QMessageBox { messagebox-text-interaction-flags: 5; }")
		msgbox.setIcon(QtWidgets.QMessageBox.Warning)
		msgbox.setTextFormat(QtCore.Qt.PlainText)
		msgbox.setText(msg)
		button_load = msgbox.addButton(__("Load"), QtWidgets.QMessageBox.AcceptRole)
		button_reject = msgbox.addButton(__("Do not load"), QtWidgets.QMessageBox.RejectRole)
		button_delete = msgbox.addButton(__("Delete"), QtWidgets.QMessageBox.DestructiveRole)
		button_delete.setEnabled(config_path is not None)
		msgbox.setInformativeText(__("Delete permanently removes the plugin file."))
		msgbox.setDefaultButton(button_reject)
		msgbox.setEscapeButton(button_reject)
		(getattr(msgbox, "exec", None) or msgbox.exec_)()
		if msgbox.clickedButton() is button_delete:
			try:
				_DeletePlugin(config_path, filename)
			except (OSError, ValueError, configparser.Error) as error:
				QtWidgets.QMessageBox.critical(None, AppInfo.NAME, __("Could not delete plugin: {error}", error=str(error)))
			else:
				QtWidgets.QMessageBox.information(msgbox, msgbox.windowTitle(), __("The plugin file has been deleted:\n{filename}", filename=filename))
			return None
		return msgbox.clickedButton() is button_load
	if sys.stdin is None or not sys.stdin.isatty(): return None
	try:
		return input(msg + "\n\n" + __("Load plugin?") + " [y/N] ").strip().lower() == "y"
	except (EOFError, OSError, KeyboardInterrupt):
		return None

def LoadPlugins(config_path, gui=False):
	global PLUGINS_INITIALIZED
	if PLUGINS_INITIALIZED: return
	PLUGINS_INITIALIZED = True
	try:
		settings = _GetSettings(config_path)
		plugin_dir = _GetPluginDirectory(config_path)
	except (OSError, ValueError, configparser.Error) as error:
		print("Could not read plugin approvals: {}".format(error))
		return
	try:
		os.makedirs(plugin_dir, exist_ok=True)
		with os.scandir(plugin_dir) as entries:
			filenames = sorted(entry.name for entry in entries if entry.name.endswith(".py") and entry.is_file(follow_symlinks=False))
	except OSError as error:
		print("Could not scan plugins: {}".format(error))
		return

	try:
		_MigrateApprovals(config_path, settings)
	except (OSError, ValueError, configparser.Error) as error:
		print("Could not read plugin approvals: {}".format(error))
		return

	for filename in filenames:
		module_name = None
		try:
			path = os.path.join(plugin_dir, filename)
			with open(path, "rb") as f: source = f.read()
			metadata = _GetPluginMetadata(source, filename)
			try:
				approval = json.loads(settings.value(filename) or "{}")
			except ValueError:
				approval = {}
			if not isinstance(approval, dict):
				approval = {}
			if not metadata["name"]:
				if approval.get("sha256"):
					PLUGINS[filename] = {**metadata, "name": filename[:-3], "sha256": approval["sha256"], "enabled": approval.get("enabled") is not False}
				continue
			digest = hashlib.sha256(source).hexdigest()
			if approval.get("enabled") is False:
				PLUGINS[filename] = {**metadata, "sha256": approval.get("sha256"), "enabled": False}
				continue
			if approval.get("sha256") != digest:
				decision = _ConfirmPlugin(filename, digest, gui, config_path, name=metadata["name"], description=metadata.get("description"), version=metadata.get("version"))
				if decision is False:
					PLUGINS[filename] = {**metadata, "sha256": approval.get("sha256"), "enabled": False}
					_SavePluginSettings(config_path, filename, approval.get("sha256"), False)
				if decision is not True: continue
				try:
					_SavePluginSettings(config_path, filename, digest, True)
				except OSError as error:
					print("Could not save plugin approvals: {}".format(error))

			PLUGINS[filename] = {**metadata, "sha256": digest, "enabled": True}
			module_name = "_flashgbx_plugin_" + filename[:-3]
			spec = importlib.util.spec_from_file_location(module_name, path)
			module = importlib.util.module_from_spec(spec)
			sys.modules[module_name] = module
			exec(compile(source, path, "exec"), module.__dict__)
			entry = getattr(module, "plugin_entry", None)
			if entry is not None:
				entry()
		except (Exception, SystemExit, KeyboardInterrupt) as error:
			if module_name is not None:
				sys.modules.pop(module_name, None)
			print("Could not load plugin {}:\n{}: {}".format(filename, type(error).__name__, error))
