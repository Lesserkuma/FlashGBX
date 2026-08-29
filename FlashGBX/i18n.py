# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import sys, os, io, ast, struct, array, locale, gettext, platform, re, subprocess, glob

OS_LANGUAGE = "en"
CONFIGURED_LANGUAGE = None
TRANSLATION_AUTHOR = None

# Language codes: code -> (English name, native name)
LANGUAGES = {"aa": ("Afar", "Qafar af"), "ab": ("Abkhazian", "Аԥсшәа"), "ae": ("Avestan", "Avesta"), "af": ("Afrikaans", "Afrikaans"), "ak": ("Akan", "Akan"), "am": ("Amharic", "አማርኛ"), "an": ("Aragonese", "Aragonés"), "ar": ("Arabic", "العربية"), "as": ("Assamese", "অসমীয়া"), "av": ("Avaric", "авар мацӀ"), "ay": ("Aymara", "Aymar aru"), "az": ("Azerbaijani", "Azərbaycan dili"), "ba": ("Bashkir", "Башҡорт теле"), "be": ("Belarusian", "Беларуская мова"), "bg": ("Bulgarian", "Български"), "bh": ("Bihari languages", "भोजपुरी"), "bi": ("Bislama", "Bislama"), "bm": ("Bambara", "Bamanankan"), "bn": ("Bengali", "বাংলা"), "bo": ("Tibetan", "བོད་སྐད་"), "br": ("Breton", "Brezhoneg"), "bs": ("Bosnian", "Bosanski"), "ca": ("Catalan", "Català"), "ce": ("Chechen", "Нохчийн мотт"), "ch": ("Chamorro", "Chamoru"), "co": ("Corsican", "Corsu"), "cr": ("Cree", "ᓀᐦᐃᔭᐍᐏᐣ"), "cs": ("Czech", "Čeština"), "cu": ("Church Slavonic", "Славе́нскїй ѧ҆зы́къ"), "cv": ("Chuvash", "Чӑваш чӗлхи"), "cy": ("Welsh", "Cymraeg"), "da": ("Danish", "Dansk"), "de": ("German", "Deutsch"), "dv": ("Divehi", "ދިވެހިބަސް"), "dz": ("Dzongkha", "རྫོང་ཁ"), "ee": ("Ewe", "Eʋegbe"), "el": ("Greek", "Ελληνικά"), "en": ("English", "English"), "eo": ("Esperanto", "Esperanto"), "es": ("Spanish", "Español"), "et": ("Estonian", "Eesti"), "eu": ("Basque", "Euskara"), "fa": ("Persian", "فارسی"), "ff": ("Fulah", "Fulfulde"), "fi": ("Finnish", "Suomi"), "fj": ("Fijian", "Na Vosa Vakaviti"), "fo": ("Faroese", "Føroyskt"), "fr": ("French", "Français"), "fy": ("Western Frisian", "Frysk"), "ga": ("Irish", "Gaeilge"), "gd": ("Scottish Gaelic", "Gàidhlig"), "gl": ("Galician", "Galego"), "gn": ("Guaraní", "Avañe'ẽ"), "gu": ("Gujarati", "ગુજરાતી"), "gv": ("Manx", "Gaelg"), "ha": ("Hausa", "Hausa"), "he": ("Hebrew", "עברית"), "hi": ("Hindi", "हिन्दी"), "ho": ("Hiri Motu", "Hiri Motu"), "hr": ("Croatian", "Hrvatski"), "ht": ("Haitian Creole", "Kreyòl Ayisyen"), "hu": ("Hungarian", "Magyar"), "hy": ("Armenian", "Հայերեն"), "hz": ("Herero", "Otjiherero"), "ia": ("Interlingua", "Interlingua"), "id": ("Indonesian", "Bahasa Indonesia"), "ie": ("Interlingue", "Interlingue"), "ig": ("Igbo", "Asụsụ Igbo"), "ii": ("Sichuan Yi", "ꆈꌠ꒿ Nuosuhxop"), "ik": ("Inupiaq", "Iñupiaq"), "io": ("Ido", "Ido"), "is": ("Icelandic", "Íslenska"), "it": ("Italian", "Italiano"), "iu": ("Inuktitut", "ᐃᓄᒃᑎᑐᑦ"), "ja": ("Japanese", "日本語"), "jv": ("Javanese", "Basa Jawa"), "ka": ("Georgian", "ქართული"), "kg": ("Kongo", "Kikongo"), "ki": ("Kikuyu", "Gĩkũyũ"), "kj": ("Kuanyama", "Kuanyama"), "kk": ("Kazakh", "Қазақ тілі"), "kl": ("Kalaallisut", "Kalaallisut"), "km": ("Khmer", "ខ្មែរ"), "kn": ("Kannada", "ಕನ್ನಡ"), "ko": ("Korean", "한국어"), "kr": ("Kanuri", "Kanuri"), "ks": ("Kashmiri", "कश्मीरी"), "ku": ("Kurdish", "Kurdî"), "kv": ("Komi", "Коми кыв"), "kw": ("Cornish", "Kernewek"), "ky": ("Kyrgyz", "Кыргызча"), "la": ("Latin", "Latina"), "lb": ("Luxembourgish", "Lëtzebuergesch"), "lg": ("Ganda", "Luganda"), "li": ("Limburgish", "Limburgs"), "ln": ("Lingala", "Lingála"), "lo": ("Lao", "ລາວ"), "lt": ("Lithuanian", "Lietuvių"), "lu": ("Luba-Katanga", "Tshiluba"), "lv": ("Latvian", "Latviešu"), "mg": ("Malagasy", "Malagasy"), "mh": ("Marshallese", "Kajin M̧ajeļ"), "mi": ("Māori", "Te Reo Māori"), "mk": ("Macedonian", "Македонски"), "ml": ("Malayalam", "മലയാളം"), "mn": ("Mongolian", "Монгол"), "mr": ("Marathi", "मराठी"), "ms": ("Malay", "Bahasa Melayu"), "mt": ("Maltese", "Malti"), "my": ("Burmese", "မြန်မာဘာသာ"), "na": ("Nauru", "Dorerin Naoero"), "nb": ("Norwegian Bokmål", "Norsk Bokmål"), "nd": ("North Ndebele", "isiNdebele"), "ne": ("Nepali", "नेपाली"), "ng": ("Ndonga", "Owambo"), "nl": ("Dutch", "Nederlands"), "nn": ("Norwegian Nynorsk", "Norsk Nynorsk"), "no": ("Norwegian", "Norsk"), "nr": ("South Ndebele", "isiNdebele"), "nv": ("Navajo", "Diné bizaad"), "ny": ("Chichewa", "ChiCheŵa"), "oc": ("Occitan", "Occitan"), "oj": ("Ojibwa", "ᐊᓂᔑᓈᐯᒧᐎᓐ"), "om": ("Oromo", "Afaan Oromoo"), "or": ("Odia", "ଓଡ଼ିଆ"), "os": ("Ossetian", "Ирон ӕвзаг"), "pa": ("Punjabi", "ਪੰਜਾਬੀ"), "pi": ("Pāli", "पाळि"), "pl": ("Polish", "Polski"), "ps": ("Pashto", "پښتو"), "pt": ("Portuguese", "Português"), "qu": ("Quechua", "Runa Simi"), "rm": ("Romansh", "Rumantsch"), "rn": ("Kirundi", "Ikirundi"), "ro": ("Romanian", "Română"), "ru": ("Russian", "Русский"), "rw": ("Kinyarwanda", "Ikinyarwanda"), "sa": ("Sanskrit", "संस्कृतम्"), "sc": ("Sardinian", "Sardu"), "sd": ("Sindhi", "سنڌي"), "se": ("Northern Sami", "Davvisámegiella"), "sg": ("Sango", "Yângâ tî sängö"), "si": ("Sinhala", "සිංහල"), "sk": ("Slovak", "Slovenčina"), "sl": ("Slovenian", "Slovenščina"), "sm": ("Samoan", "Gagana Samoa"), "sn": ("Shona", "ChiShona"), "so": ("Somali", "Soomaali"), "sq": ("Albanian", "Shqip"), "sr": ("Serbian", "Српски"), "ss": ("Swati", "SiSwati"), "st": ("Southern Sotho", "Sesotho"), "su": ("Sundanese", "Basa Sunda"), "sv": ("Swedish", "Svenska"), "sw": ("Swahili", "Kiswahili"), "ta": ("Tamil", "தமிழ்"), "te": ("Telugu", "తెలుగు"), "tg": ("Tajik", "Тоҷикӣ"), "th": ("Thai", "ไทย"), "ti": ("Tigrinya", "ትግርኛ"), "tk": ("Turkmen", "Türkmençe"), "tl": ("Tagalog", "Tagalog"), "tn": ("Tswana", "Setswana"), "to": ("Tonga", "Lea fakatonga"), "tr": ("Turkish", "Türkçe"), "ts": ("Tsonga", "Xitsonga"), "tt": ("Tatar", "Татарча"), "tw": ("Twi", "Twi"), "ty": ("Tahitian", "Reo Tahiti"), "ug": ("Uighur", "ئۇيغۇرچە"), "uk": ("Ukrainian", "Українська"), "ur": ("Urdu", "اردو"), "uz": ("Uzbek", "Oʻzbekcha"), "ve": ("Venda", "Tshivenḓa"), "vi": ("Vietnamese", "Tiếng Việt"), "vo": ("Volapük", "Volapük"), "wa": ("Walloon", "Walon"), "wo": ("Wolof", "Wolof"), "xh": ("Xhosa", "isiXhosa"), "yi": ("Yiddish", "ייִדיש"), "yo": ("Yoruba", "Èdè Yorùbá"), "za": ("Zhuang", "Vahcuengh"), "zh": ("Chinese", "中文"), "zu": ("Zulu", "isiZulu")}
# Add additional languages as needed (GNU gettext ll_CC format)
LANGUAGES.update({"zh_CN": ("Simplified Chinese", "简体中文"), "zh_TW": ("Traditional Chinese", "繁體中文")})

def _language_tag(language):
	language = re.split(r"[.@]", language or "", maxsplit=1)[0].replace("-", "_")
	parts = language.split("_")
	if parts[0].upper() == "C":
		return "C"
	return "_".join([parts[0].lower()] + [p.upper() if len(p) in (2, 3) else p.title() if len(p) == 4 else p for p in parts[1:]])

def set_locale(language=None):
	target = language or OS_LANGUAGE or ""
	if not target:
		return False

	candidates = [target]
	if "_" in target:
		candidates.append(target.split(".")[0])
		candidates.append(target.split("_")[0])
	if "-" in target:
		candidates.append(target.split("-")[0])
	if target.split("_")[0].split("-")[0].lower() == "en":
		# Ensure a stable dot decimal separator when only a generic English locale is configured.
		candidates.append("C")

	for candidate in candidates:
		try:
			locale.setlocale(locale.LC_ALL, candidate)
			return True
		except locale.Error:
			continue

	try:
		locale.setlocale(locale.LC_ALL, "")
		return True
	except locale.Error:
		return False

def loadTranslation(language):
	# Based on msgfmt.py by Martin v. Löwis: https://github.com/python/cpython/blob/main/Tools/i18n/msgfmt.py
	messages = {}
	section = None
	msgctxt = None
	msgid = b''
	msgstr = b''
	fuzzy = 0
	is_plural = False

	if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
		app_path = os.path.dirname(sys.executable)
	else:
		app_path = os.path.dirname(os.path.abspath(__file__))

	filename = os.path.join(app_path, "locale", f"{language}.po")
	if not os.path.exists(filename):
		raise FileNotFoundError(f"{filename} not found")

	with open(filename, 'r', encoding='utf-8') as f:
		lines = f.readlines()

	for line in lines:
		line = line.strip()
		if not line:
			continue

		if line.startswith('#,') and 'fuzzy' in line:
			fuzzy = 1

		if line.startswith('#'):
			if section == 'STR':
				key = b"%b\x04%b" % (msgctxt, msgid) if msgctxt else msgid
				if not fuzzy and msgstr:
					messages[key] = msgstr
			section = msgctxt = None
			fuzzy = 0
			continue

		if line.startswith('msgctxt'):
			section = 'CTXT'
			msgctxt = b''
			line = line[7:].strip()
		elif line.startswith('msgid') and not line.startswith('msgid_plural'):
			if section == 'STR':
				key = b"%b\x04%b" % (msgctxt, msgid) if msgctxt else msgid
				if not fuzzy and msgstr:
					messages[key] = msgstr
			section = 'ID'
			msgid = msgstr = b''
			is_plural = False
			line = line[5:].strip()
		elif line.startswith('msgid_plural'):
			msgid += b'\0'
			is_plural = True
			line = line[12:].strip()
		elif line.startswith('msgstr'):
			section = 'STR'
			if line.startswith('msgstr['):
				if not is_plural:
					raise ValueError("Plural msgstr found without msgid_plural")
				line = line.split(']', 1)[1].strip()
				if msgstr:
					msgstr += b'\0'
			else:
				if is_plural:
					raise ValueError("Non-indexed msgstr found for plural")
				line = line[6:].strip()

		val = ast.literal_eval(line).encode('utf-8')

		if section == 'CTXT':
			msgctxt += val
		elif section == 'ID':
			msgid += val
		elif section == 'STR':
			msgstr += val

	if section == 'STR':
		key = b"%b\x04%b" % (msgctxt, msgid) if msgctxt else msgid
		if not fuzzy and msgstr:
			messages[key] = msgstr

	keys = sorted(messages.keys())
	offsets = []
	ids = bytearray()
	strs = bytearray()
	for k in keys:
		offsets.append((len(ids), len(k), len(strs), len(messages[k])))
		ids += k + b'\0'
		strs += messages[k] + b'\0'

	keystart = 28 + 16 * len(keys)
	valuestart = keystart + len(ids)
	koffsets = []
	voffsets = []
	for o1, l1, o2, l2 in offsets:
		koffsets += [l1, o1 + keystart]
		voffsets += [l2, o2 + valuestart]

	mo = struct.pack("Iiiiiii", 0x950412de, 0, len(keys), 7 * 4, 7 * 4 + len(keys) * 8, 0, 0)
	mo += array.array("i", koffsets + voffsets).tobytes()
	mo += ids + strs

	return gettext.GNUTranslations(fp=io.BytesIO(mo))

def __(msgid, **kwargs):
	msg = lang.gettext(msgid)
	try:
		return msg.format(**kwargs)
	except (KeyError, IndexError):
		return msgid.format(**kwargs)

def ___(singular, plural, n=1, **kwargs):
	msg = lang.ngettext(singular, plural, n)
	try:
		return msg.format(n=n, **kwargs)
	except (KeyError, IndexError):
		fallback = singular if n == 1 else plural
		return fallback.format(n=n, **kwargs)

def c__(context, msgid, **kwargs):
	try:
		msg = lang.pgettext(context, msgid)
	except AttributeError:
		msg = lang.gettext(msgid)
	try:
		return msg.format(**kwargs)
	except (KeyError, IndexError):
		return msgid.format(**kwargs)

def c___(context, singular, plural, n=1, **kwargs):
	try:
		msg = lang.npgettext(context, singular, plural, n)
	except AttributeError:
		msg = lang.ngettext(singular, plural, n)
	try:
		return msg.format(n=n, **kwargs)
	except (KeyError, IndexError):
		fallback = singular if n == 1 else plural
		return fallback.format(n=n, **kwargs)

def format_number(n):
	return locale.format_string("%d", n, grouping=False)

def format_decimal(value, precision=2, grouping=False, localized=True):
	if localized:
		return locale.format_string("%.{}f".format(precision), value, grouping=grouping)
	else:
		return "{:.{}f}".format(value, precision)

def loadQtTranslation(app=None, language=None):
	global _qt_translator
	try:
		from .pyside import QtCore
	except Exception:
		return False

	if language is None:
		language = CONFIGURED_LANGUAGE or OS_LANGUAGE or ""
	if not language:
		return False

	try:
		qt_locale = QtCore.QLocale(language)
	except Exception:
		qt_locale = QtCore.QLocale.system()
	try:
		QtCore.QLocale.setDefault(qt_locale)
	except Exception:
		pass
	set_locale(qt_locale.name())

	try:
		translations_path = QtCore.QLibraryInfo.path(QtCore.QLibraryInfo.TranslationsPath)
	except AttributeError:
		translations_path = QtCore.QLibraryInfo.location(QtCore.QLibraryInfo.TranslationsPath)

	translator = QtCore.QTranslator(app)
	for catalog in ("qtbase", "qt"):
		if translator.load(qt_locale, catalog, "_", translations_path):
			if app is not None:
				app.installTranslator(translator)
			_qt_translator = translator
			return True

	return False

def init_language(config_path, override=None):
	global lang, CONFIGURED_LANGUAGE, LANGUAGES, TRANSLATION_AUTHOR

	if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
		app_path = os.path.dirname(sys.executable)
	else:
		app_path = os.path.dirname(os.path.abspath(__file__))
	available_langs = ["en"] # Always include English
	available_langs += [os.path.splitext(os.path.basename(f))[0] for f in glob.glob(os.path.join(app_path, "locale", "*.po"))]
	filtered_langs = {code: name for code, name in LANGUAGES.items() if code in available_langs}
	LANGUAGES = dict(sorted(filtered_langs.items(), key=lambda x: x[1][1]))

	try:
		from .IniSettings import IniSettings
	except ImportError:
		from IniSettings import IniSettings

	settings = IniSettings(path=os.path.join(config_path, "settings.ini"))
	if override:
		language_setting = override
		settings.SetValue("Language", override)
	else:
		language_setting = settings.GetValue("Language", default="auto")

	system_language = _language_tag(OS_LANGUAGE)

	if language_setting and language_setting.lower() != "auto":
		CONFIGURED_LANGUAGE = lang_code = _language_tag(language_setting)
	else:
		lang_code = system_language if system_language and system_language != "C" else "en"
		if lang_code not in LANGUAGES.keys():
			lang_code = lang_code.split("_")[0].lower()
		CONFIGURED_LANGUAGE = lang_code

	if lang_code not in LANGUAGES.keys():
		lang_code = lang_code.split("_")[0].lower()
		if lang_code not in LANGUAGES.keys():
			lang_code = "en"
		CONFIGURED_LANGUAGE = lang_code

	if lang_code and lang_code != "en":
		try:
			lang = loadTranslation(lang_code)
			empty = ""
			metadata = lang.gettext(empty)
			for line in metadata.splitlines():
				if line.lower().startswith("last-translator:"):
					TRANSLATION_AUTHOR = line.split(":", 1)[1].strip()
					break
		except Exception as e:
			lang = gettext.NullTranslations()
			print(f"Could not load translation for '{lang_code}': {e}")
	else:
		lang = gettext.NullTranslations()

	set_locale(CONFIGURED_LANGUAGE)

####

try:
	locale.setlocale(locale.LC_ALL, "")
except locale.Error:
	pass

lang_country = None
try:
	lang_country, _ = locale.getlocale()
except (TypeError, ValueError):
	lang_country = None

OS_LANGUAGE = lang_country

if not OS_LANGUAGE and platform.system() == "Darwin":
	try:
		defaults_output = subprocess.check_output(
			["defaults", "read", "-g", "AppleLanguages"],
			stderr=subprocess.DEVNULL,
			text=True,
		).strip()
		apple_languages = []
		for raw_line in defaults_output.splitlines():
			cleaned = raw_line.strip().strip(",").strip().strip('"')
			if cleaned and cleaned not in ("(", ")"):
				apple_languages.append(cleaned)
		if apple_languages:
			OS_LANGUAGE = apple_languages[0]
	except Exception:
		pass

if not OS_LANGUAGE:
	for env_name in ("LC_ALL", "LC_MESSAGES", "LANG"):
		env_value = os.environ.get(env_name)
		if env_value:
			candidate = re.split(r"[.@]", env_value, maxsplit=1)[0].strip()
			if candidate:
				OS_LANGUAGE = candidate
				break

if not OS_LANGUAGE:
	OS_LANGUAGE = "en"

_qt_translator = None
lang = gettext.NullTranslations()
