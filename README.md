# FlashGBX (by Lesserkuma)

for Windows, Linux, macOS (→ [Download](https://github.com/Lesserkuma/FlashGBX/releases))

<img src="https://raw.githubusercontent.com/Lesserkuma/FlashGBX/master/.github/01.png" alt="FlashGBX on Windows 11" width="500"><br><img src="https://raw.githubusercontent.com/Lesserkuma/FlashGBX/master/.github/02.png" alt="GB Camera Album Viewer" width="500">

## Introduction

### Software features

- Backup, restore and erase save data from Game Boy and Game Boy Advance game cartridges including Real Time Clock registers
- Backup ROM data from Game Boy and Game Boy Advance game cartridges
- Write new ROMs to a wide variety of Game Boy and Game Boy Advance flash cartridges
- Many reproduction cartridges and flash cartridges can be auto-detected
- A flash chip query (including Common Flash Interface information) can be performed for flash cartridges
- Decode and extract Game Boy Camera photos from save data
- Generate ROM dump reports for game preservation purposes

### Compatible cartridge reader/writer hardware

- [GBxCart RW](https://www.gbxcart.com/) (tested with v1.4, v1.4a and v1.4c)
- [GBFlash](https://github.com/simonkwng/GBFlash) (tested with v1.2 and v1.3)
- [Joey Jr](https://bennvenn.myshopify.com/collections/game-cart-to-pc-interface/products/usb-gb-c-cart-dumper-the-joey-jr) (tested with V2++)

## Cartridge Compatibility
### Supported cartridge memory mappers
- Game Boy
  - All cartridges without memory mapping
  - MBC1
  - MBC2
  - MBC3
  - MBC30
  - MBC5
  - MBC6
  - MBC7
  - MBC1M
  - MMM01
  - MAC-GBD (Game Boy Camera)
  - G-MMC1 (GB-Memory Cartridge)
  - M161
  - HuC-1
  - HuC-3
  - TAMA5
  - Unlicensed 256M Mapper
  - Unlicensed Wisdom Tree Mapper
  - Unlicensed Xploder GB Mapper
  - Unlicensed Sachen Mapper
  - Unlicensed Datel Orbit V2 Mapper
  - Unlicensed MBCX Mapper

- Game Boy Advance
  - All cartridges without memory mapping
  - 8M FLASH DACS
  - 3D Memory (GBA Video)
  - Unlicensed 2G Mapper
  - Unlicensed GBA Movie Player v2

### Currently supported flash cartridges

- Game Boy

  - 29LV Series Flash BOY with 29LV160DB
  - Action Replay
  - BennVenn MBC3000 v4 RTC cart
  - BennVenn MBC3000 v5 RTC cart
  - BLAZE Xploder GB¹
  - BUNG Doctor GB Card 4M
  - BUNG Doctor GB Card 16M
  - BUNG Doctor GB Card 64M
  - Catskull 32k Gameboy Flash Cart
  - DIY cart with 28F016S5
  - DIY cart with AM29F010
  - DIY cart with AM29F016/29F016
  - DIY cart with AM29F032
  - DIY cart with AM29F040
  - DIY cart with AM29F080
  - DIY cart with AT49F040
  - DIY cart with HY29F800
  - DIY cart with M29F032D
  - DIY cart with MBM29F033C
  - DIY cart with MX29F040
  - DIY cart with MX29LV640
  - DIY cart with SST39SF040
  - DMG-MBC5-32M-FLASH (G/A) Development Cartridge, E201264
  - DMG-MBC5-32M-FLASH (G/A-I) Development Cartridge, E201264
  - Ferrante Crafts cart 32 KB
  - Ferrante Crafts cart 64 KB
  - Ferrante Crafts cart 512 KB
  - FunnyPlaying MidnightTrace 4 MiB Flash Cart
  - Gamebank-web DMG-29W-04 with M29W320DB
  - Gamebank-web DMG-29W-04 with M29W320EB
  - Gamebank-web DMG-29W-04 with M29W320ET
  - GameShark Pro
  - GB-CART32K-A with SST39SF020A
  - GB Smart 32M
  - GBFlash MBCX (8 MiB)
  - GBFlash MBCX (32 MiB)
  - GBFlash RTC with MX29LV320EB
  - HDR Game Boy Camera Flashcart
  - insideGadgets 32 KiB
  - insideGadgets 128 KiB
  - insideGadgets 256 KiB
  - insideGadgets 512 KiB
  - insideGadgets 1 MiB, 128 KiB SRAM
  - insideGadgets 2 MiB, 128 KiB SRAM/32 KiB FRAM
  - insideGadgets 2 MiB, 32 KiB FRAM, v1.0
  - insideGadgets 4 MiB, 128 KiB SRAM/FRAM
  - insideGadgets 4 MiB, 32 KiB FRAM, MBC3+RTC
  - insideGadgets 4 MiB (2× 2 MiB), 32 KiB FRAM, MBC5
  - insideGadgets MegaDuck 32K
  - ModRetro Chromatic Cartridge with 39VF1681
  - ModRetro Chromatic Cartridge with IS29GL032
  - Mr Flash 64M
  - Sillyhatday MBC5-DUAL-FLASH-4/8MB
  - Squareboi 4 MiB (2× 2 MiB)

- Game Boy Advance

  - Action Replay Ultimate Codes (with SST39VF800A)
  - Development AGB Cartridge 64M Flash, E201629¹
  - Development AGB Cartridge 64M Flash, E201629 (128M, with 4× LH28F320BJE)¹
  - Development AGB Cartridge 64M Flash S, E201843¹
  - Development AGB Cartridge 128M Flash S, E201850
  - Development AGB Cartridge 256M Flash S, E201868
  - DL9SEC GBA flashcart with TE28F128
  - DL9SEC GBA flashcart with TE28F256
  - Flash Advance Pro 256M
  - Flash2Advance 128M (with 2× 28F640J3A120)
  - Flash2Advance 256M (with 2× 28F128J3A150)
  - Flash2Advance Ultra 2G (with 4× 4400L0Y0Q0)
  - Flash2Advance Ultra 64M (with 2× 28F320C3B)
  - Flash2Advance Ultra 256M (with 8× 3204C3B100)
  - Flash Advance Card 64M (with 28F640J3A120)
  - FunnyPlaying MidnightTrace 32 MiB Flash Cart
  - GBA Movie Player v2 CF (with SST39VF400A)¹
  - GBFlash 1M FLASH RTC (AGB-R1M-02V3)
  - GBFlash 1M FLASH RTC (AGB-R1M-02V4)
  - insideGadgets 16 MiB, 64K EEPROM with Solar Sensor and RTC options
  - insideGadgets 32 MiB, 1M FLASH with RTC option
  - insideGadgets 32 MiB, 512K FLASH
  - insideGadgets 32 MiB, 4K/64K EEPROM
  - insideGadgets 32 MiB, 256K FRAM with Rumble option

*¹ = Cannot always be auto-detected, select cartridge type manually*

### Currently supported and tested reproduction cartridges

- Game Boy

  - 2006_TSOP_64BALL_QFP48 with AL016J55FFAR2
  - 256M29EWH (no PCB text)
  - 36VF3204 and ALTERA CPLD (no PCB text)
  - 512M29EWH (no PCB text)
  - DMG-DHCN-20 with MX29LV320ET
  - DMG-GBRW-20 with 29LV320ETMI-70G
  - DRV with 29LV320DB and ALTERA CPLD
  - DRV with AM29LV160DB and ALTERA CPLD
  - DRV with AM29LV160DT and ALTERA CPLD
  - DVP DRV with MX29LV320CB¹
  - DVP DRV with MX29LV320CT¹
  - ES29LV160_DRV with 29DL32TF-70
  - GB-M968 with 29LV160DB
  - GB-M968 with M29W160EB
  - GB-M968 with MX29LV320ABTC
  - HC007-BGA-V2 with M29W640
  - S29GL032N90T and ALTERA CPLD configured for MBC1 or MBC5
  - SD007_48BALL_64M with GL032M11BAIR4
  - SD007_48BALL_64M with M29W640
  - SD007_48BALL_64M_V2 with GL032M11BAIR4
  - SD007_48BALL_64M_V2 with M29W160ET
  - SD007_48BALL_64M_V3 with 29DL161TD-90
  - SD007_48BALL_64M_V5 with 36VF3203
  - SD007_48BALL_64M_V5 with 36VF3204
  - SD007_48BALL_64M_V6 with 36VF3204
  - SD007_48BALL_64M_V6 with 29DL163BD-90
  - SD007_48BALL_64M_V8 with M29W160ET
  - SD007_48BALL_SOP28 with M29W320ET
  - SD007_BGA48_71TV_T28_DEEP with M29W640
  - SD007_BV5 with 29LV160TE-70PFTN
  - SD007_BV5_DRV with M29W320DT
  - SD007_BV5_DRV with S29GL032M90TFIR4
  - SD007_BV5_V2 with HY29LV160TT
  - SD007_BV5_V2 with MX29LV320BTC
  - SD007_BV5_V3 with 26LV160BTC
  - SD007_BV5_V3 with 29LV160BE-90PFTN
  - SD007_BV5_V3 with HY29LV160BT-70
  - SD007_BV5_V3 with AM29LV160MB
  - SD007_K8D3216_32M with MX29LV160CT
  - SD007_T40_48BALL_71_TV_TS28 with M29W640
  - SD007_T40_6401B\*CD_71_TS28 with 39VF6401B
  - SD007_T40_64BALL_S71_TV_TS28 with TC58FVB016FT-85
  - SD007_T40_64BALL_SOJ28 with 29LV016T
  - SD007_T40_64BALL_TSOP28 with 29LV016T
  - SD007_T40_64BALL_TSOP28 with TC58FVB016FT-85¹
  - SD007_TSOP_29LV017D with L017D70VC
  - SD007_TSOP_29LV017D with S29GL032M90T
  - SD007_TSOP_48BALL with 36VF3204
  - SD007_TSOP_48BALL with AM29LV160DB
  - SD007_TSOP_48BALL with K8D3216UTC
  - SD007_TSOP_48BALL with M29W160ET
  - SD007_TSOP_48BALL with L160DB12VI
  - SD007_TSOP_48BALL_V9 with 29LV160CBTC-70G
  - SD007_TSOP_48BALL_V9 with 32M29EWB
  - SD007_TSOP_48BALL_V10 with 29DL164BE-70P
  - SD007_TSOP_48BALL_V10 with 29DL32TF-70
  - SD007_TSOP_48BALL_V10 with 29LV320CTXEI
  - SD007_TSOP_48BALL_V10 with GL032M10BFIR3
  - SD007_TSOP_48BALL_V10 with M29W320DT
  - SD007_TSOP_64BALL_SOJ28 with 29DL164BE-70P
  - SD007_TSOP_64BALL_SOJ28 with unlabeled flash chip
  - SD007_TSOP_64BALL_SOP28 with EN29LV160AB-70TCP
  - SD007_TSOP_64BALL_SOP28 with unlabeled flash chip
  - SD007_TSOP_64BALL_SOP28_V2 with unlabeled flash chip
  - SD008-6810-512S with MSP55LV512
  - SD008-6810-V4 with MX29GL256EL
  - SD008-6810-V5 with MX29CL256FH

- Game Boy Advance

  - 0121 with 0121M0Y0BE
  - 100BS6600_48BALL_V4 with 6600M0U0BE
  - 100SOP with MSP55LV100S
  - 2006-36-71_V2 with M36L0R8060B
  - 2006_TSOP_64BALL_6106 with W29GL128SH9B
  - 28F256L03B-DRV with 256L30B
  - 29LV128DBT2C-90Q and ALTERA CPLD
  - 3680x2 with TH50VSF3680
  - 36L0R8-39VF512 with M36L0R8060B
  - 36L0R8-39VF512 with M36L0R8060T
  - 4000L0ZBQ0 DRV with 3000L0YBQ0
  - 4050M0Y0Q0-39VF512 with 4050M0Y0Q0
  - 4050_4400_4000_4350_36L0R_V5 with 4050L0YTQ2
  - 4050_4400_4000_4350_36L0R_V5 with M36L0R7050T
  - 4050_4400_4000_4350_36L0R_V5 with M36L0T8060T
  - 4050_4400_4000_4350_36L0R_V5 with M36L0R8060T
  - 4350Q2 with 4050V0YBQ1
  - 4350Q2 with 4350LLYBQ2
  - 4400 with 4400L0ZDQ0
  - 4444-39VF512 with 4444LLZBBO
  - 4455_4400_4000_4350_36L0R_V3 with M36L0R7050T
  - AA1030_TSOP88BALL with M36W0R603
  - AGB-E05-01 with GL128S
  - AGB-E05-01 with MSP55LV100G
  - AGB-E05-01 with MSP55LV128M
  - AGB-E05-01 with MX29GL128FHT2I-90G
  - AGB-E05-01 with S29GL064
  - AGB-E05-02 with JS28F128
  - AGB-E05-02 with M29W128FH
  - AGB-E05-02 with M29W128GH
  - AGB-E05-02 with S29GL032
  - AGB-E05-03H with M29W128GH
  - AGB-E05-06L with 29LV128DBT2C-90Q
  - AGB-E08-09 with 29LV128DTMC-90Q
  - AGB-E20-30 with M29W128GH
  - AGB-E20-30 with S29GL256N10TFI01
  - AGB-SD-E05 with MSP55LV128
  - B100 with MX29LV640ET
  - B104 with MSP55LV128
  - B11 with 26L6420MC-90
  - B54 with MX29LV320ET
  - BGA64B-71-TV-DEEP with 256M29EML
  - BX2006_0106_NEW with S29GL128N10TFI01
  - BX2006_TSOP_64BALL with GL128S
  - BX2006_TSOP_64BALL with GL256S
  - BX2006_TSOPBGA_0106 with M29W640
  - BX2006_TSOPBGA_0106 with K8D6316UTM-PI07
  - BX2006_TSOPBGA_6108 with M29W640
  - DV15 with MSP55LV100G
  - F864-3 with M36L0R7050B
  - F0088_2G_BGA48 with F0088H0
  - F0095_4G_V1 with F0095H0
  - GA-07 with unlabeled flash chip
  - GE28F128W30 with 128W30B0
  - K5L2BX_32D_16D_V2 with K5L2833ATA
  - M36XXX_32A_EARTH with M36L0R806
  - M36XXX_T32_32D_16D with M36L0R806
  - M5M29-39VF512 with M5M29HD528
  - M5M29G130AN (no PCB text)
  - M6MGJ927 (no PCB text)
  - MSP54LV512 (no PCB text)
  - MX29GL128EHT2I and ALTERA CPLD
  - MXP54_16D_046 with MSP54LV256
  - MXP54_16D_ERATH with MSP54LV256
  - SUN100S_MSP54XXX with MSP54LV100
  - Unknown 29LV320 variant (no PCB text)

Many different reproduction cartridges share their flash chip command set, so even if yours is not on this list, it may still work fine or even be auto-detected as another one. Support for more cartridges can also be added by creating external config files that include the necessary flash chip commands.

*¹ = Cannot always be auto-detected, select cartridge type manually*

## Installing and running

### Pre-compiled binaries and packages

Available in the GitHub [Releases](https://github.com/Lesserkuma/FlashGBX/releases) section are pre-compiled downloads available for:

* **Windows (64-bit)** *(Windows 8 or newer)*
  * Setup: An installer that will add the application to the start menu and optionally create a desktop icon
  * Portable: Have everything in one place including the config files

* **Linux**
  * Ubuntu (.deb file): Install using `dpkg -i /path/to/FlashGBX_x.x_Ubuntu-all.deb`.
  * Other distributions: Pre-made Linux packages are available at [JJ-Fox’s repository](https://github.com/JJ-Fox/FlashGBX-Linux-builds/releases/latest).

* **macOS** *(Sequoia 15 or newer)*
  * x86-64/arm64 (.dmg file): Install by opening the .dmg file and copying over the “FlashGBX” application to the desktop.<br>If it doesn’t run, it probably got quarantined due to the lack of a Apple Developer Program certificate. Right-click the extracted FlashGBX icon, choose “Open Terminal at Folder” and enter this command to unquarantine it: `xattr -d com.apple.quarantine ../FlashGBX.app`.

  *(If you have a Joey Jr and use macOS, please run the [Joey Jr Firmware Updater](https://github.com/Lesserkuma/JoeyJr_FWUpdater) before using FlashGBX.)*

### Run via Python

FlashGBX can also be run in a Python environment like so:

1. Download and install [Python](https://www.python.org/downloads/) (version 3.10.11 is recommended)
2. Open a Terminal or Command Prompt window
3. Install FlashGBX with this command:<br>`pip3 install "FlashGBX[qt6]"`
* If installation fails, try this command instead:<br>`pip3 install "FlashGBX[qt5]"`
* If installation still fails, you can install the minimal version (command line interface) with this command:<br>`pip3 install FlashGBX`
* Update to the latest version by replacing `install` with `install -U`.

#### Running
Use this command in a Terminal or Command Prompt window to launch the installed FlashGBX application:

`python3 -m FlashGBX`

*FlashGBX should work on pretty much any operating system that supports Qt-GUI applications built using [Python](https://www.python.org/downloads/) with [PySide2](https://pypi.org/project/PySide2/) or [PySide6](https://pypi.org/project/PySide6/), [pyserial](https://pypi.org/project/pyserial/), [Pillow](https://pypi.org/project/Pillow/), [setuptools](https://pypi.org/project/setuptools/), [requests](https://pypi.org/project/requests/) and [python-dateutil](https://pypi.org/project/python-dateutil/) packages. To run FlashGBX in portable mode without installing, you can also download the source code archive and call `python3 run.py` after installing the prerequisites yourself.*

*Note: When using GBxCart RW or GBFlash on some Linux systems, the `brltty` module may render serial communication devices non-accessible. See the troubleshooting section for details.*

### Steam Deck
#### Installation
1. Boot your Steam Deck in Desktop Mode.
2. Open System Settings → Users.
3. Set a password for your user account (“deck”), if you do not have one set yet. (Make sure you do not forget this password in the future.)
4. Create a new folder where you want to install FlashGBX.
5. Right click the folder and select “Open Terminal Here”.
6. Enter the following commands in order:<br>
`python3 -m venv FlashGBX_venv`<br>
`source FlashGBX_venv/bin/activate`<br>
`wget https://bootstrap.pypa.io/get-pip.py`<br>
`python3 get-pip.py`<br>
`python3 -m pip install "FlashGBX[qt6]"`<br>
`deactivate`<br>
`sudo usermod -a -G uucp $USER`<br>
(You may need to enter the password you set earlier.)
7. Restart your Steam Deck.

#### Running
1. In Desktop Mode, right click your FlashGBX folder and select “Open Terminal Here”.
2. Use these commands to launch the installed FlashGBX application:<br>
`source FlashGBX_venv/bin/activate`<br>
`python3 -m FlashGBX`<br>

### Troubleshooting

* If something doesn’t work as expected, first try to clean the game cartridge contacts (best with IPA 99.9%+ on a cotton swab) and reconnect the device. An unstable cartridge connection is the most common reason for read or write errors.

* If your Game Boy Camera cartridge is not reading, make sure it’s connected the correct way around; screws go up.

* For save data backup/restore on Game Boy Advance reproduction cartridges, depending on how it was built, you may have to manually select the save type for it to work properly. However, the save data backup/restore feature may not work on certain reproduction cartridges with batteryless-patched ROMs. As those cartridges use the same flash chip for both ROM and save data storage, a full ROM backup will usually include the save data. Also, when flashing a new unpatched ROM to a cartridge like this, the game may not be able to save progress without soldering in a battery. See the [Flash Cart DB website](https://flashcartdb.com/index.php/Clone_and_Repo_Cart_Problems) for more information.

* Depending on your system configuration, you may have to use `pip` and `python` commands instead of `pip3` and `python3`.

* On some Linux systems, you may run into a *Permission Error* problem when trying to connect to USB devices without *sudo* privileges. To grant yourself the necessary permissions temporarily, you can run `sudo chmod 0666 /dev/ttyUSB0` (replace with actual device path) before running the app. For a permanent solution, add yourself to the usergroup that has access to serial devices by default (e.g. *dialout* on Debian-based distros; `sudo adduser $USER dialout`) and then reboot the system.

* On some Linux systems, you may need the *XCB Xinerama package* if you see an error regarding failed Qt platform plugin initialization. You can install it with `sudo apt install libxcb-xinerama0` etc. It was reported that this additional command is required on MX Linux: `sudo ln -s /usr/lib/x86_64-linux-gnu/libxcb-util.so.0.0.0 /usr/lib/x86_64-linux-gnu/libxcb-util.so.1`

* On some Linux systems like Fedora, you may need to install the `python3-pillow-qt` package manually in order for the GUI mode to work.

* On some Linux systems you may see the message “No devices found.” with the GBxCart RW or GBFlash hardware device, even though you’re using a USB cable capable of data transfers. This may be caused by a module called `brltty` (a driver for refreshable braille displays) that is erroneously interfering and taking over control of any connected USB device that uses the CH340/341 chipset. The solution would be to uninstall or blacklist the `brltty` driver and then reboot the system. This is not an issue with Joey Jr devices.

* If you’re using macOS version 10.13 or older, there may be no driver for serial communication devices installed on your system. You can either upgrade your macOS version to 10.14+ or manually install a driver which is available [here](https://github.com/adrianmihalko/ch340g-ch34g-ch34x-mac-os-x-driver).

* If you’re using macOS and get a “Segmentation Fault: 11.” error, try the “Run via Python” method with Python version 3.10.11 and install FlashGBX with `pip3 install "FlashGBX[qt5]"`.

* If the save data detection says “512K FLASH (64 KiB) or 1M FLASH (128 KiB)”, that means the size can not be determined until actual save data is written to the cartridge.

## Miscellaneous

* To use your own frame around extracted Game Boy Camera pictures, place a file called `pc_frame.png` (must be at least 160×144 pixels) into the configuration directory. (GUI mode only)

* To write only the differences between two ROMs, name the original one `<name>.gba` and the edited one `<name>.delta.gba`.

## Contributors

The author would like to thank the following very kind people for their help, contributions or documentation (in alphabetical order):

2358, 90sFlav, AcoVanConis, AdmirtheSableye, AlexiG, ALXCO-Hardware, AndehX, antPL, aronson, Ausar, bbsan, BennVenn, ccs21, chobby, ClassicOldSong, Cliffback, CodyWick13, Corborg, Cristóbal, crizzlycruz, Crystal, Därk, Davidish, delibird_deals, DevDavisNunez, Diddy_Kong, djedditt, Dr-InSide, dyf2007, easthighNerd, EchelonPrime, edo999, Eldram, Ell, EmperorOfTigers, endrift, Erba Verde, ethanstrax, eveningmoose, Falknör, FerrantePescara, frarees, Frost Clock, Gahr, gandalf1980, gboh, gekkio, Godan, Grender, HDR, Herax, Hiccup, hiks, howie0210, iamevn, Icesythe7, ide, infinest, inYourBackline, iyatemu, Jayro, Jenetrix, JFox, joyrider3774, jrharbort, JS7457, julgr, Kaede, kane159, KOOORAY, kscheel, kyokohunter, Leitplanke, litlemoran, LovelyA72, Lu, Luca DS, LucentW, luxkiller65, manuelcm1, marv17, Merkin, metroid-maniac, Mr_V, Mufsta, olDirdey, orangeglo, paarongiroux, Paradoxical, Pese, Rairch, Raphaël BOICHOT, redalchemy, RetroGorek, RevZ, RibShark, s1cp, Satumox, Sgt.DoudouMiel, SH, Shinichi999, Sillyhatday, simonK, Sithdown, skite2001, Smelly-Ghost, Sonikks, Squiddy, Stitch, Super Maker, t5b6_de, Tauwasser, TheNFCookie, Timville, twitnic, velipso, Veund, voltagex, Voultar, Warez Waldo, wickawack, Winter1760, Wkr, x7l7j8cc, xactoes, xukkorz, yosoo, Zeii, Zelante, zipplet, Zoo, zvxr

Thanks to the No-Intro project for their game databases which FlashGBX’s databases are partly based on.

## Third Party Notices and Licenses

Please view the <a href="https://github.com/Lesserkuma/FlashGBX/blob/master/Third%20Party%20Notices.md">Third Party Notices</a>.

## DISCLAIMER

This software is being developed by Lesserkuma as a hobby project. There is no direct affiliation with Nintendo or any other company. This software is provided as-is and the developer is not responsible for any damage that is caused by the use of it. Use at your own risk!
