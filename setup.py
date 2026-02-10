# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import setuptools

with open("README.md", "r", encoding="utf-8") as fh: long_description = fh.read()

setuptools.setup(
	name="FlashGBX",
	version="4.6",
	author="Lesserkuma",
	description="Reads and writes Game Boy and Game Boy Advance cartridge data",
	url="https://github.com/Lesserkuma/FlashGBX",
	packages=setuptools.find_packages(),
	install_requires=['pyserial>=3.5', 'Pillow', 'setuptools', 'requests', 'python-dateutil', 'bitarray', 'ch347api'],
	extras_require={
		"qt5":["PySide2>=5.14"],
		"qt6":["PySide6"]
	},
	include_package_data=True,
	classifiers=[
		"Development Status :: 5 - Production/Stable",
		"Environment :: X11 Applications :: Qt",
		"Topic :: Terminals :: Serial",
		"Operating System :: OS Independent",
		"Programming Language :: Python :: 3",
		"License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
		'Intended Audience :: End Users/Desktop',
		'Intended Audience :: Developers',
	],
	project_urls={
		'Source': 'https://github.com/Lesserkuma/FlashGBX/',
		'Tracker': 'https://github.com/Lesserkuma/FlashGBX/issues',
	},
	entry_points={
		'console_scripts': (
			'flashgbx = FlashGBX.FlashGBX:main',
		)
	},
	python_requires='>=3.7',
	long_description_content_type="text/markdown",
	long_description=long_description,
)
