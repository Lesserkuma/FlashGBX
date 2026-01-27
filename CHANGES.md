# Release notes
### v4.6 (released 2026-01-27)
- Added support for a new Game Boy Advance bootleg flash save chip (SST39VF6401B) used on “Quetzal” bootlegs *(thanks Grender, marv17, Pese)*
- Added support for Gamebank-web DMG-29W-04 with M29W320DB
- Updated the Game Boy and Game Boy Advance lookup databases for save types, ROM sizes and checksums

### v4.5 (released 2025-12-06)
- Added support for SD007_T40_6401B\*CD_71_TS28 with 39VF6401B
- Added support for ModRetro Chromatic Cartridge with IS29GL032 *(thanks Jayro)*
- Added support for MXP54_16D_ERATH with MSP54LV256
- Added support for a new Game Boy Advance bootleg flash save chip
- Confirmed support for MXP54_16D_046 with MSP54LV256
- Updated the Game Boy and Game Boy Advance lookup databases for save types, ROM sizes and checksums

### v4.4 (released 2025-05-23)
- Added a few workarounds for instabilities with some GBxCart RW devices
- Fixed save data access for “Korokoro Puzzle - Happy Panecchu!” (AGB-KHPJ-JPN)
- Updated the LK firmware to version L14 (fixes the save data problem for the above game title and adds support for new cartridges)
- Added support for the 7 extra flash slots of the PHOTO! homebrew
- Now experimentally supports Batteryless SRAM save data backup and restore for Game Boy reproduction cartridges (GUI-mode only), but mostly requires manual configuration
- Added support for DMG-MBC5-32M-FLASH (G/A-I) Development Cartridge, E201264 *(thanks infinest)*
- Added support for ModRetro Chromatic Cartridge with 39VF1681 *(thanks infinest)*
- Added support for Gamebank-web DMG-29W-04 with M29W320EB *(thanks marv17)*
- Added support for BennVenn MBC3000 v5 RTC cart *(thanks Gahr)*
- Updated the Game Boy and Game Boy Advance lookup databases for save types, ROM sizes and checksums
- Discontinued the Windows 7 binary builds; if needed, please follow the “Run via Python” instructions using old Python version 3.8.10
- Bug fixes and improvements *(thanks delibird_deals, luxkiller65, marv17, xukkorz)*

### v4.3 (released 2024-11-07)
- Added support for DVP DRV with MX29LV320CT *(thanks Mufsta)*
- Added support for insideGadgets’ MegaDuck 32K flash cart
- Added support for GBFlash 1M FLASH RTC (AGB-R1M-02V4)
- Added support for the unlicensed MBCX Mapper by Geeksimon
- Added support for GBFlash MBCX (8 MiB)
- Added support for GBFlash MBCX (32 MiB)
- Updated the Game Boy and Game Boy Advance lookup databases for save types, ROM sizes and checksums
- Minor bug fixes and improvements

### v4.2 (released 2024-08-04)
- Fixed an issue with MBC2 save data on Nintendo Power GB-Memory Cartridges (DMG-MMSA-JPN) *(thanks iyatemu)*
- Updated LK firmware to version L13 (fixes an issue with some FRAM-modded Game Boy cartridges) *(thanks jrharbort)*
- Updated the Game Boy and Game Boy Advance lookup databases for save types, ROM sizes and checksums
- Minor bug fixes and improvements

### v4.1 (released 2024-07-14)
- Added support for M36XXX_32A_EARTH with M36L0R8060T *(thanks inYourBackline)*
- Fixed a bug with Game Boy Advance Real Time Clock register saving *(thanks Sonikks)*
- Added support for Development AGB Cartridge 64M Flash, E201629 (128M, with 4× LH28F320BJE) *(thanks Squiddy)*
- Updated the Game Boy and Game Boy Advance lookup databases for save types, ROM sizes and checksums
- Minor bug fixes and improvements

### v4.0.1 (released 2024-06-30)
- Bug fixes *(thanks marv17, RibShark)*

### v4.0 (released 2024-06-30)
- Updated GBxCart RW firmware to version R42+L12 (improves flash cart compatibility)
- Improved support for M5M29-39VF512 with M5M29HD528 *(thanks marv17)*
- Improved writing speed for Game Boy Action Replay and GameShark with the Datel Orbit V2 mapper
- Updated the Game Boy and Game Boy Advance lookup databases for save types, ROM sizes and checksums
- Added the feature of displaying the Game Boy Advance bootlogo *(thanks Winter1760 for the huffman decompression algorithm)*
- Added support for K5L2BX_32D_16D_V2 with K5L2833ATA *(thanks Warez Waldo)*
- Fixed a problem with TAMA5 cartridges
- Added the option of changing the internal Real Time Clock values in GUI mode
- Added support for Development AGB Cartridge 64M Flash, E201629
- Added support for SD008_512ND_4M with epoxy flash chip *(thanks gandalf1980)*
- Changed the Analyze Flash Cart process, flash cartridges will now be auto-detected faster
- Improved support for the DMG-MBC5-32M-FLASH Development Cartridge
- Added support for Vast Fame bootlegs *(thanks RibShark)*
- Added support for GBFlash RTC with MX29LV320EB *(thanks simonK)*
- Added support for GBFlash 1M FLASH RTC (AGB-R1M-02V3)
- Added support for GBA Movie Player v2 CF (SST39VF400A)
- Added support for the GBflash hardware device *(thanks simonK)*
- Added support for M36XXX_32A_EARTH with M36L0R8060B *(thanks Herax)*
- Added support for BUNG Doctor GB Card 4M *(thanks chobby)*
- Added support for BUNG Doctor GB Card 16M *(thanks chobby)*
- Added support for DIY cart with MX29F040 *(thanks Grender)*
- Added support for the Joey Jr hardware device *(thanks BennVenn)*
- Confirmed support for F0088_2G_BGA48 with F0088H0
- Added support for DVP DRV with MX29LV320CB *(thanks Lu)*
- The insideGadgets’ firmware protocol of older GBxCart RW devices (Mini, v1.2 and older) is no longer supported
- Minor bug fixes and improvements *(thanks aronson, simonK, marv17)*

### v3.37 (released 2024-03-01)
- Bundles GBxCart RW firmware version R42+L11 (improves flash cart compatibility)
- Added support for F0095_4G_V1 with F0095H0 *(thanks Ausar)*
- Improved support for 256M29EWH (no PCB text)
- Confirmed and improved support for 512M29EWH (no PCB text)
- Updated the Game Boy and Game Boy Advance lookup databases for save types, ROM sizes and checksums
- Minor bug fixes and improvements

### v3.36 (released 2024-01-15)
- Added support for DIY cart with 28F016S5 *(thanks alexbc2999)*
- Fixed a problem with reading Sachen cartridges *(thanks xukkorz)*
- Updated the Game Boy and Game Boy Advance lookup databases for save types, ROM sizes and checksums
- Minor bug fixes and improvements *(thanks djedditt, AlexiG)*

### v3.35 (released 2023-11-25)
- Added support for DRV with 29LV320DB and ALTERA CPLD *(thanks TheNFCookie)*
- Added support for HC007-BGA-V2 with M29W640 *(thanks LucentW)*
- Added support for reading and writing the save data of some GBA multigame bootleg cartridges
- Updated the Game Boy and Game Boy Advance lookup databases for save types, ROM sizes and checksums

### v3.34 (released 2023-09-26)
- Minor bug fixes and improvements

### v3.33 (released 2023-09-25)
- Updated the Game Boy and Game Boy Advance lookup databases for save types, ROM sizes and checksums
- Minor bug fixes and improvements *(thanks Eldram, Grender)*

### v3.32 (released 2023-07-25)
- Added support for M5M29-39VF512 with M5M29HD528 *(thanks marv17)*
- Added support for SD007_BV5_V3 with 26LV160BTC
- Added support for DL9SEC GBA flashcart with TE28F128 *(thanks olDirdey)*
- Added support for DL9SEC GBA flashcart with TE28F256 *(thanks olDirdey)*
- Added support for M36XXX_T32_32D_16D with M36L0R8060T *(thanks Merkin)*
- Added support for Gamebank-web DMG-29W-04 with M29W320ET *(thanks zipplet)*
- Added support for a new bootleg save type based on 1M FLASH
- Added support for another flash chip used on the BennVenn MBC3000 RTC cart
- Added support for 3680x2 with TH50VSF3680 (only up to 8 MiB) *(thanks kane159)*
- Fixed support for BGA64B-71-TV-DEEP with 256M29EML
- Confirmed support for FunnyPlaying MidnightTrace 4 MiB Game Boy Flash Cart *(thanks AlexiG)*
- Confirmed support for FunnyPlaying MidnightTrace 32 MiB Game Boy Advance Flash Cart *(thanks AlexiG)*
- Confirmed support for 2006-36-71_V2 with M36L0R8060B *(thanks kane159)*
- Updated the Game Boy Advance lookup databases for save types, ROM sizes and checksums
- Minor bug fixes and improvements *(thanks Falknör, Crystal)*

### v3.31 (released 2023-06-18)
- Improved support for 32 MiB cartridges that have one of the EEPROM save types (fixes both backups and writes of B3CJ, B53E, B53P, BBAE, BBAP, BC2J, BFRP, BH3E, BH3P, BH8E, BJPP, BU7E, BU7P, BX3E, BX3P, BYUE, BYUJ, BYUP)
- Confirmed support for BGA64B-71-TV-DEEP with 256M29EML *(thanks Leitplanke)*
- Updated the Game Boy Advance lookup databases for save types, ROM sizes and checksums
- Minor bug fixes and improvements

### v3.30 (released 2023-06-06)
- Improved auto-detection of official GBA Video cartridges with the 3D Memory mapper including those that are less than 64 MiB
- Added support for Unknown 29LV320 variant (no PCB text) *(thanks Zoo)*
- Added support for new insideGadgets flash cart revisions *(thanks Smelly-Ghost)*
- Added support for Sillyhatday MBC5-DUAL-FLASH-4/8MB *(thanks Sillyhatday)*
- Confirmed support for SD007_T40_48BALL_71_TV_TS28 with M29W640 *(thanks marv17)*
- Updated the Game Boy and Game Boy Advance lookup databases for save types, ROM sizes and checksums

### v3.29 (released 2023-05-14)
- Fixed an issue with writing to some flash cartridges using the old GBxCart RW v1.3 hardware revision *(thanks yosoo)*
- Fixed an issue with Batteryless SRAM save data restore *(thanks antPL)*
- Confirmed support for SD007_TSOP_64BALL_SOP28_V2 with unlabeled flash chip *(thanks DevDavisNunez)*
- Added support for SD007_BGA48_71TV_T28_DEEP with M29W640 *(thanks Cristóbal)*
- Minor bug fixes and improvements

### v3.28 (released 2023-05-05)
- Improved support for the BennVenn MBC3000 RTC cart; can now write to Real Time Clock registers
- Updated the Game Boy Advance lookup database for save types, ROM sizes and checksums
- Improved support for 8M FLASH DACS cartridges; can now backup and restore the boot sector
- Nintendo Power GB-Memory Cartridge (DMG-MMSA-JPN): Added more information to the dump reports
- Nintendo Power GB-Memory Cartridge (DMG-MMSA-JPN): When making a ROM backup, individual games will now also be extracted
- Improved support for e-Reader, Card e-Reader and Card e-Reader+ cartridges; will now prevent overwriting calibration data accidentally
- Minor bug fixes and improvements

### v3.27 (released 2023-04-26)
- Bundles GBxCart RW v1.4/v1.4a firmware version R42+L10 (improves flash cart compatibility) *(thanks wickawack)*
- Added support for cartridges with MX29GL128EHT2I and ALTERA CPLD *(thanks Merkin)*
- Improved writing speed for cartridges with MSP54LV512 (no PCB text) *(thanks SH for the contribution)*
- Minor bug fixes and improvements *(thanks ide)*

### v3.26 (released 2023-04-18)
- Fixed a bug that made exporting Game Boy Camera pictures with a frame not work *(thanks Ell)*
- Fixed a bug with Game Boy ROM write verification on sectors smaller than 0x4000 bytes *(thanks KOOORAY)*
- Improved auto-detect for the BennVenn MBC3000 RTC cart

### v3.25 (released 2023-04-14)
- Bundles GBxCart RW v1.4/v1.4a firmware version R41+L9 (minor improvements)
- Fixed an issue with the Game Boy Camera Album Viewer *(thanks CodyWick13)*
- Switched from PyInstaller to providing Windows Setup/Portable packages with embedded Python runtimes, so FlashGBX can be run from source as well (requires 64-bit Windows installation)
- Added support for DRV with AM29LV160DT and ALTERA CPLD *(thanks Corborg)*
- Verification after writing a ROM is now a lot faster (requires firmware R41+L9)
- Now shows the No-Intro game title in the main window if the cartridge is in the database
- Cleaned up the list of Game Boy mappers in the GUI to only list the unique types; detailed info is still available in dump reports
- Updated the Game Boy Advance lookup database for save types, ROM sizes and checksums

### v3.24 (released 2023-04-09)
- Improved support for Batteryless SRAM save data backup and restore for Game Boy Advance reproduction cartridges *(thanks metroid-maniac and LucentW)*
- When checking for available updates, version information is now read via the GitHub API instead of the PyPI API
- Updated InnoSetup and the PyInstaller bootloader (Windows binaries only)
- Minor bug fixes and improvements

### v3.23/v3.23.1 (released 2023-04-06)
- Bundles GBxCart RW v1.4/v1.4a firmware version R40+L8 (Game Boy Camera flash cart fix on insideGadgets software, Pokémon Mini support on insideGadgets software, fixes a problem with reading GBA Video cartridges and other minor improvements)
- Confirmed support for Flash Advance Pro 256M *(thanks Erba Verde)*
- Added support for Flash2Advance Ultra 2G with 4× 4400L0Y0Q0
- Added support for DIY cart with Fujitsu-branded 29F016 *(thanks sillyhatday)*
- Save data is now read twice if the extra data verification option is enabled
- Added a save chip stress test feature, can be used to detect a dry SRAM battery or bad soldering
- Updated the Game Boy Advance lookup database for save types, ROM sizes and checksums and also added a database for Game Boy and Game Boy Color titles
- No-Intro-style file names are now enabled by default when creating backups (e.g. `Pocket Monsters Gin (Japan) (Rev 1) (SGB Enhanced) (GB Compatible).gbc` instead of `POKEMON_SLV_AAXJ-1.gbc`) (GUI-mode only)
- Now supports Batteryless SRAM save data backup and restore for Game Boy Advance reproduction cartridges (GUI-mode only) *(thanks BennVenn and metroid-maniac)*
- Improved support for the BennVenn MBC3000 RTC cart; can now write the entire 8 MiB *(thanks BennVenn)*
- Fixed a problem with forward-adjusting the Real Time Clock from Game Boy Advance save data files *(thanks Smelly-Ghost)*
- Windows Setup Package: Updated the CH340/CH341 driver to the latest version (02/11/2023, 3.8.2023.02)
- Fixed an issue with restoring Batteryless SRAM save data that is smaller than the flash chip’s sector size *(thanks marv17)*
- Minor bug fixes and improvements

### v3.22 (released 2023-02-09)
- Added support for DRV with AM29LV160DB and ALTERA CPLD *(thanks ccs21)*
- Added support for DIY cart with HY29F800 *(thanks Kaede)*
- Added more information to the dump report of Nintendo Power GB-Memory Cartridges (DMG-MMSA-JPN)
- Updated the Game Boy Advance lookup database for save types, ROM sizes and checksums
- Minor bug fixes and improvements

### v3.21 (released 2023-01-16)
- Bundles GBxCart RW v1.4/v1.4a firmware version R39+L8 (adds support for insideGadgets WonderSwan and Game Gear flash carts)
- Added support for SD007_48BALL_SOP28 with M29W320ET *(thanks DevDavisNunez)*
- Added support for the BennVenn MBC3000 RTC cart *(thanks LucentW)*
- Added support for Flash2Advance Ultra 256M with 8× 3204C3B100 *(thanks djedditt)*
- Added support for SD007_T40_64BALL_SOJ28 with 29LV016T *(thanks Stitch)*
- Confirmed support for SD007_T40_64BALL_S71_TV_TS28 with TC58FVB016FT-85 *(thanks edo999)*
- Added support for F864-3 with M36L0R7050B *(thanks s1cp)*
- Allowed for switching between different Write Enable pins during chip erase and sector erase command sequences via a third parameter (“WR” or “AUDIO”) *(thanks ALXCO-Hardware for the suggestion)*
- Added support for the Squareboi 4 MB (2× 2 MB) cart *(thanks ALXCO-Hardware)*
- Added an option to limit the baud rate for GBxCart RW v1.4/v1.4a
- Minor bug fixes and improvements *(thanks gboh, Grender, orangeglo and marv17)*

### v3.20 (released 2022-11-30)
- Bundles GBxCart RW v1.4/v1.4a firmware version R38+L8 (minor improvements)
- Will now retry failed flash sector writes a few times before stopping the process (requires firmware version L1+)
- Added delta ROM writing (only write the difference between two ROMs); requires both the original &lt;name&gt;.&lt;ext&gt; ROM file and the changed &lt;name&gt;.delta.&lt;ext&gt; ROM file in the same directory (requires firmware version L1+) *(thanks djedditt for the suggestion)*
- Fixed support for Flash2Advance Ultra 64M with 2× 28F320C3B
- Fixed support for BX2006_TSOPBGA_0106/BX2006_TSOPBGA_6108 with M29W640 (requires firmware version L8+)
- Confirmed support for 4444-39VF512 with 4444LLZBBO *(thanks marv17)*
- Added support for SUN100S_MSP54XXX with MSP54LV100 *(thanks Därk)*
- Minor bug fixes and improvements

### v3.19 (released 2022-10-24)
- Fixed a bug not allowing FlashGBX to run correctly if there were square brackets in the file path *(thanks kscheel)*
- Added support for MSP54LV512 (no PCB text) *(thanks ethanstrax)*
- Added support for DIY cart with MBM29F033C *(thanks Godan)*
- Added support for marv17 32 KB Homebrew Flashcard (SST39SF040) *(thanks marv17)*
- Minor adjustments to the format of GBA RTC register data was made as it is now also supported by the mGBA emulator from version 0.10.0 *(thanks endrift)*
- Updated the Game Boy Advance lookup database for save types, ROM sizes and checksums *(thanks Falknör)*
- Added support for saving and restoring RTC registers of official TAMA5 cartridges inside save data files
- Now decodes and displays the embedded Boot Logo of Game Boy games *(thanks Jenetrix)*
- Bundles GBxCart RW v1.1/v1.2/v1.3 firmware version R31 *(thanks AlexiG)*
- Minor bug fixes and improvements

### v3.18 (released 2022-08-18)
- Fixed a problem with writing MBC2 save data onto cartridges that use a different mapper
- Improved support for the insideGadgets LinkNLoad flash cartridges

### v3.17 (released 2022-08-01)
- Improved MBC1 ROM banking based on the [Game Boy: Complete Technical Reference](https://github.com/Gekkio/gb-ctr) by gekkio (fixes games such as Super Chinese Fighter GB)

### v3.16/v3.16.1 (released 2022-07-26)
- Added support for 256M29EWH (no PCB text) *(thanks Diddy_Kong)*
- Added support for a new insideGadgets 4 MB flash cartridge *(thanks AlexiG)*
- Added support for Ferrante Crafts cart 32 KB V2 *(thanks FerrantePescara)*
- Bundles GBxCart RW v1.4 firmware version R37+L7 (improves support for some Game Boy flash cartridges)
- Updated the Game Boy Advance lookup database for save types, ROM sizes and checksums
- Added an option for manually specifying the device port to use via command line argument `--device-port`
- Support added for Pocket Camera save data files made using 2bit PXLR Studio
- Minor bug fixes and improvements *(thanks JFox)*

### v3.15 (released 2022-07-05)
- Improved support for several flash cartridge types
- Confirmed support for the Catskull 32k Gameboy Flash Cart *(thanks CodyWick13)*
- Minor bug fixes and improvements

### v3.14 (released 2022-06-11)
- Fixed a bug with extracting the Game Boy Camera’s Game Face image *(thanks 2358)*
- Improved the default file names, now includes the ROM revision information as well
- The default file name format can now be configured within the `settings.ini` file
- Updated the Game Boy Advance lookup database for save types, ROM sizes and checksums (fixes some games such as Yoshi’s Universal Gravitation) *(thanks 2358)*
- FlashGBX now experimentally supports both PySide2 and PySide6 GUI frameworks which should make it easier to use on Apple M1 macOS systems *(thanks JFox)*

### v3.13 (released 2022-05-30)
- Bundles GBxCart RW v1.4 firmware version R36+L7 (fixes a problem with insideGadgets’ GBxCam application)
- Added smaller selectable ROM sizes for Game Boy Advance ROM backups
- Minor bug fixes and improvements

### v3.12 (released 2022-05-27)
- Added proper detection of the Sachen 8B-001 mono unlicensed cartridge *(thanks voltagex)*
- Fixed an issue with dumping large-size GBA Video cartridges in CLI mode
- Added the option to generate ROM dump reports in CLI mode
- Minor bug fixes and improvements

### v3.11 (released 2022-05-25)
- Added the option to generate ROM dump reports for game preservation purposes *(thanks Hiccup)*
- Bundles GBxCart RW v1.4 firmware version R35+L7 (improves SRAM access on reproduction cartridges and Game Boy Camera access)
- Added support for DIY cart with M29F032D @ AUDIO *(thanks Godan)*

### v3.10 (released 2022-05-17)
- Added support for the Datel Orbit V2 mapper (Action Replay and GameShark) *(thanks Jenetrix)*
- Fixed verification with AA1030_TSOP88BALL with M36W0R603 *(thanks DevDavisNunez)*
- Added support for SD007_TSOP_48BALL_V9 with 32M29EWB *(thanks marv17)*
- Improved support for Nintendo Power GB-Memory Cartridges (DMG-MMSA-JPN) *(thanks kyokohunter)*
- Minor bug fixes and improvements

### v3.9 (released 2022-04-29)
- Added support for Ferrante Crafts cart 64 KB *(thanks FerrantePescara)*
- Added support for Ferrante Crafts cart 512 KB *(thanks FerrantePescara)*
- Fixed a bug with querying MBC3/MBC30 Real Time Clock values *(thanks HDR and AdmirtheSableye)*

### v3.8 (released 2022-04-21)
- Added support for AGB-E05-01 with MSP55LV100G *(thanks EmperorOfTigers)*
- Added support for DV15 with MSP55LV100G *(thanks zvxr)*
- Added support for SD007_T40_64BALL_TSOP28 with 29LV016T *(thanks Wkr)*
- Confirmed support for AGB-E05-03H with M29W128GH *(thanks Wkr)*
- The integrated firmware updater can now also update the firmware of insideGadgets GBxCart RW v1.1, v1.2, XMAS v1.0 and Mini v1.0 device revisions
- Added experimental support for writing ISX files to Game Boy flash cartridges
- Bundles GBxCart RW v1.4 firmware version R34+L6 (changes the way Game Boy cartridges are read and enables support for some more flash cartridges)
- Added support for the BLAZE Xploder GB unlicensed cheat cartridge (requires firmware version L6+)
- Added support for the unlicensed Sachen mapper (requires firmware version L6+)
- Added support for insideGadgets 128 KB flash cartridges *(thanks AlexiG)*
- Added support for insideGadgets 256 KB flash cartridges *(thanks AlexiG)*
- Minor bug fixes and improvements

### v3.7 (released 2022-03-31)
- Updated the Game Boy Advance lookup database for save types, ROM sizes and checksums (improves support for Classic NES Series, NES Classics and Famicom Mini cartridges)
- When writing new ROMs to Nintendo Power GB-Memory Cartridges (DMG-MMSA-JPN), hidden sector data will now be auto-generated if it’s not provided by the user in form of a .map file
- Erasing save data of Game Boy Advance cartridges with the 512K FLASH and 1M FLASH save types is now faster
- Windows Setup Package: Updated the CH340/CH341 driver to the latest version (01/18/2022, 3.7.2022.01)
- Fixed a bug introduced in v3.4 that broke writing ROMs to SD008-6810-V5 with MX29CL256FH cartridges
- Added support for AGB-E05-01 with S29GL064 *(thanks DevDavisNunez)*
- Added support for DIY carts with MBC1 and AM29F010 @ AUDIO *(thanks JS7457)*
- Added support for DIY carts with MBC1 and AM29F040 @ AUDIO *(thanks JS7457)*
- Added support for DIY carts with MBC1 and AM29F080 @ AUDIO *(thanks Timville)*
- Added support for DIY carts with MBC1 and AT49F040 @ AUDIO *(thanks Timville)*
- Added support for DIY carts with MBC1 and SST39SF040 @ AUDIO *(thanks Timville)*
- Added support for B100 with MX29LV640ET *(thanks Mr_V)*
- Added support for B54 with MX29LV320ET *(thanks Mr_V)*
- Added support for AGB-E05-02 with S29GL032 *(thanks redalchemy)*
- Minor bug fixes and improvements

### v3.6 (released 2022-03-09)
- When opening Game Boy Camera Album Viewer manually, the save data will now automatically be loaded if a Game Boy Camera or Pocket Camera cartridge is connected
- Fixed a bug with the insideGadgets 4 MB (S29GL032M) cartridge *(thanks frarees)*
- Fixed a “MemoryError” bug when writing a smaller ROM to the 100BS6600_48BALL_V4 with 6600M0U0BE cartridge with full chip erase mode enabled
- Added support for Flash Advance Card 64M with 28F640J3A120 *(thanks manuelcm1)*
- Fixed a bug with writing ROMs to insideGadgets rumble cartridges on the GBxCart RW v1.3 hardware running the L1 firmware *(thanks DevDavisNunez)*
- In GUI mode, flashable cartridges can now completely be wiped of their ROM data by not selecting any file when using the Write ROM feature *(thanks daidianren for the suggestion)*
- Fixed a bug introduced in v3.4 with making a ROM backup of Nintendo Power GB-Memory Cartridges (DMG-MMSA-JPN)
- Bundles GBxCart RW v1.4 firmware version R34+L5 (enables support for some more flash cartridges)
- Added support for DIY cartridges with the AT49F040 flash chip for up to 512 KB of ROM data (requires at least GBxCart RW revision v1.4 and firmware version R34+L5) *(thanks Timville)*
- Added support for the insideGadgets 512 KB flash cartridge (requires at least GBxCart RW revision v1.4 and firmware version R34+L5) *(thanks Timville and marv17)*
- Added support for 100SOP with MSP55LV100S *(thanks Jayro)*

### v3.5 (released 2022-02-14)
- Fixed a bug related to the 100BS6600_48BALL_V4 with 6600M0U0BE cartridge when using the Detect Flash Cart button *(thanks to redalchemy)*
- Fixed a bug with the full chip erase feature via sector erase mode
- When reading save data from a Game Boy Camera or Pocket Camera cartridge via custom command line switches, you will no longer be asked if you’d also like to extract pictures. This is to make it easier to use FlashGBX for scripting. You can still use `--action gbcamera-extract` to extract pictures in a second step, or use the interactive mode.

### v3.4 (released 2022-02-04)
- Confirmed support for SD007_TSOP_64BALL_SOJ28 with unlabeled flash chip *(thanks x7l7j8cc)*
- Added support for SD008-6810-512S with MSP55LV512
- Added support for SD007_TSOP_48BALL_V10 with 29DL164BE-70P *(thanks Herax)*
- Added support for the unlicensed Wisdom Tree mapper *(thanks AlexiG and Smelly-Ghost)*
- Added support for 4000L0ZBQ0 DRV with 3000L0YBQ0 *(thanks iamevn)*
- Added support for SD007_T40_64BALL_TSOP28 with TC58FVB016FT-85 *(thanks joyrider3774)* (cannot be auto-detected, select cartridge type manually)
- Added support for SD007_TSOP_64BALL_SOJ28 with 29DL164BE-70P *(thanks Herax)*
- Confirmed support for Development AGB Cartridge 64M Flash S, E201843
- Added support for the DMG-MBC5-32M-FLASH Development Cartridge, E201264 (requires GBxCart RW firmware L1 or higher)
- If the full chip erase preference is enabled but only sector erase mode is available, the entire chip will now still be erased, so no previous data will remain

### v3.3 (released 2022-01-10)
- Added support for Flash2Advance 128M with 2× 28F640J3A120 *(thanks twitnic)*
- Added support for 36VF3204 and ALTERA CPLD (no PCB text) *(thanks Herax and Davidish)*
- Added support for SD008-6810-V4 with unlabeled flash chip *(thanks LucentW)*
- Will now check written save data for errors if the verification option is enabled (requires GBxCart RW firmware L1 or higher)
- Added a zoom factor setting for extracted Game Boy Camera pictures
- Extracted Game Boy Camera pictures can now have a frame around them; this frame can be customized by placing a file called `pc_frame.png` (must be at least 160×144 pixels) into the configuration directory

### v3.2 (released 2021-12-18)
- Fixed the configuration files for DIY carts with AM29F016/AM29F016B *(thanks dyf2007)*
- Added support for SD008-6810-V5 with MX29CL256FH (multigame cartridge with 32 MB of ROM and 512 KB of save data)
- Added support for SD008-6810-V4 with MX29GL256EL *(thanks LucentW)*
- Added support for the [HDR Game Boy Camera Flashcart](https://github.com/HDR/Gameboy-Camera-Flashcart) (select manually if auto-detected option doesn’t work)
- Removed the Fast Read Mode setting which was experimental on old firmware versions and will now always be used on newer firmware versions
- Fixed a bug with paths that include a percent sign *(thanks Shinichi999)*

### v3.1 (released 2021-12-01)
- Added support for the GBxCart RW Mini v1.0d hardware revision
- Added support for insideGadgets 4 MB (2× 2 MB), 32 KB FRAM, MBC5 flash cartridges *(thanks AlexiG)*
- Bundles GBxCart RW v1.4 firmware version R33+L4 (fixes an issue with accessing save data of some FRAM cartridge modifications)
- Added support for SD007_TSOP_48BALL with AM29LV160DT *(thanks crizzlycruz)*
- Confirmed support for SD007_TSOP_48BALL_V10 with 29LV320CTXEI *(thanks marv17)*
- Added support for AA1030_TSOP88BALL with M36W0R603 *(thanks LucentW)*
- Added support for Ferrante Crafts cart with SST39SF010A *(thanks skite2001)*

### v3.0 (released 2021-11-15)
- Added support for the GBxCart RW v1.4a hardware revision
- Bundles GBxCart RW v1.4 firmware version R32+L3 (improves ROM writing speed for Development AGB Cartridge 256M Flash S, E201868)
- Added support for 0883_DRV with ES29LV160ET *(thanks RetroGorek)*
- Confirmed support for 2006_TSOP_64BALL_QFP48 with AL016J55FFAR2 *(thanks Sithdown)*
- Added support for GB-CART32K-A with SST39SF020A *(thanks Icesythe7)*
- Added support for 29LV Series Flash BOY with 29LV160DB *(thanks Luca DS)*
- Fixed a bug with reading ROMs of HuC-1 cartridges *(thanks Satumox)*
- When writing a save data file that is smaller than the selected save type suggests, repeats of the data will now be written instead of blank data; this can be useful for games like “Pokémon Pinball” on a flash cartridge with larger SRAM/FRAM than required
- Confirmed support for SD007_TSOP_64BALL_SOP28 with unlabeled flash chip *(thanks marv17)*
- Added support for SD007_TSOP_64BALL_SOP28 with EN29LV160AB-70TCP *(thanks marv17)*
- Added support for SD007_TSOP_48BALL_V10 with 29DL32TF-70
- Improved the auto-detection of flash cartridges
- Fixed the auto-adjustment of Real Time Clock register values as the day counter was inaccurate
- Added the detection of a cartridge’s actual save type (requires save data to be present)

### v2.8 (released 2021-09-05)
- Added an option to fix wrong header checksums when writing a ROM *(thanks Voultar for the suggestion)*
- Fixed a bug with the auto-detect feature *(thanks Voultar)*
- Fixed the save data size detection of the Classic NES Series and Famicom Mini game cartridges for Game Boy Advance

### v2.7 (released 2021-09-02)
- Added support for AGB-E20-30 with M29W128GH *(thanks hiks)*
- Added support for SD007_TSOP_48BALL_V9 with 29LV160CBTC-70G *(thanks marv17)*
- Fixed a bug with parsing an invalid settings.ini *(thanks Rairch)*
- Added the image that was last seen by the GB Camera Sensor to the GB Camera Album Viewer *(thanks Raphaël BOICHOT for the suggestion)*

### v2.6 (released 2021-08-09)
- Bundles GBxCart RW v1.4 firmware version R31+L2 (fixes a very rare bug with SRAM access on Game Boy cartridges)
- Added a firmware updater for GBxCart v1.4 devices
- Configuration path bug fix for systems that do not support PySide2 *(thanks JFox)*
- Added support for S29GL032N90T and ALTERA CPLD (configured for MBC1) *(thanks t5b6_de)*
- Flashing rumble enabled Game Boy Advance flash cartridges by insideGadgets is no longer noisy *(thanks AlexiG)*
- Confirmed support for DMG-GBRW-20 with 29LV320ETMI-70G
- Confirmed support for AGB-E20-30 with S29GL256N10TFI01
- Minor bug fixes with the firmware updater *(thanks marv17)*

### v2.5 (released 2021-07-15)
- Added support for 4350Q2 with 4050V0YBQ1 *(thanks Shinichi999)*
- Fixed Real Time Clock register access for MBC3B and MBC30 cartridges on the GBxCart RW v1.4 hardware
- Added support for SD007_BV5 with 29LV160TE-70PFTN *(thanks RetroGorek)*

### v2.4 (released 2021-06-20)
- Added support for 4050_4400_4000_4350_36L0R_6108 with M36L0R7050B *(thanks Jayro)*
- Added support for AGB-E05-02 with JS28F128 *(thanks marv17)*
- Confirmed support for SD007_TSOP_48BALL_V9 with 29LV320CBTC-70G *(thanks AcoVanConis)*
- Fixed a bug when running FlashGBX without GUI support, the command line interface mode will now launch without extra parameters again *(thanks howie0210)*

### v2.3 (released 2021-06-08)
- Added support for AGB-E05-06L with 29LV128DBT2C-90Q *(thanks marv17)*
- Nintendo Power GB-Memory Cartridges (DMG-MMSA-JPN) will now be unlocked properly even if they’re stuck in erase mode *(thanks Grender for testing)*
- Confirmed support for SD007_TSOP_48BALL_V10 with GL032M10BFIR3 *(thanks Mr_V)*
- Added support for 2006_TSOP_64BALL_6106 with W29GL128SH9B *(thanks marv17)*
- Fixed support for insideGadgets 1 MB, 128 KB SRAM *(thanks AlexiG)*
- The [setup package](https://github.com/Lesserkuma/FlashGBX/releases) now includes the CH341 USB serial driver for insideGadgets GBxCart RW devices

### v2.2 (released 2021-06-03)
- Added support for insideGadgets 2 MB, 32 KB FRAM, v1.0 *(thanks t5b6_de)*
- Added support for SD007_TSOP_29LV017D with M29W320DT *(thanks marv17)*
- Added support for SD007_TSOP_29LV017D with S29GL032M90T *(thanks marv17)*
- Fixed detection of Classic NES Series and Famicom Mini game cartridges for Game Boy Advance *(thanks LucentW)*
- Added support for 29LV128DBT2C-90Q and ALTERA CPLD (configured for MBC5) *(thanks Sgt.DoudouMiel)*
- Added support for 0121 with 0121M0Y0BE *(thanks RetroGorek)*
- Fixed detection of Pocket Monsters Ruby v1.1 (AGB-AXVJ-JPN) and Pocket Monsters Sapphire v1.1 (AGB-AXPJ-JPN) genuine game cartridges *(thanks Icesythe7)*
- Fixed flash chip query for flash cartridges that have no CFI data but swapped pins *(thanks marv17)*
- Added support for M5M29G130AN (no PCB text) *(thanks Mr_V)*
- Added support for GA-07 with unlabeled flash chip *(thanks Mr_V)*
- Added support for SD007_TSOP_48BALL_V10 with M29W320DT *(thanks Jayro)*
- Fixed a problem of reading from a certain type of cartridge that uses the GL256S flash chip *(thanks marv17)*
- Added support for B11 with 26L6420MC-90 *(thanks dyf2007)*
- Added support for DIY carts with MX29LV640 *(thanks eveningmoose)*

### v2.1 (released 2021-05-05)
- Fixed support for SD007_TSOP_29LV017D with L017D70VC *(thanks marv17 and 90sFlav)*
- Added support for DIY carts with MBC1 and AM29F080 *(thanks skite2001)*
- Added support for SD007_TSOP_48BALL_V8 with 29LV320CTTC *(thanks Jayro)*
- Added the MBC5+SRAM mapper type which is officially unused, but is actually used by GB Studio *(thanks Jayro)*
- The GBxCart RW v1.3 firmware updater should now also work if the device is below firmware version R19
- Adjusted the baudrate used for updating the firmware which fixes a problem on some macOS systems
- Added support for Flash2Advance Ultra 64M with 2× 28F320C3B
- Confirmed support for 4350Q2 with 4350LLYBQ2

### v2.0 (released 2021-05-01)
- Added an integrated firmware updater for GBxCart v1.3 devices which includes the latest official firmware version at time of FlashGBX release; also supports external firmware files
- Added support for the new GBxCart RW v1.4 hardware
- Created a custom high compatibility firmware for GBxCart v1.3 and v1.4 devices, completely written from scratch
  - Version L1 for GBxCart RW v1.3
    - Works with all officially released Game Boy and Game Boy Advance cartridges including those with rare mappers, except cartridges that use memory cards and other external peripherals
    - Supported mappers: MBC1, MBC2, MBC3, MBC30, MBC5, MBC6, MBC7, MBC1M, MMM01, GBD (Game Boy Camera), G-MMC1 (GB-Memory), M161, HuC-1, HuC-3, TAMA5, DACS, 3D Memory (GBA Video)
    - Enables support for a few more reproduction and flash cartridges including:
      - 4050M0Y0Q0-39VF512 with 4050M0Y0Q0
      - Development AGB Cartridge 128M Flash S, E201850
      - Development AGB Cartridge 256M Flash S, E201868
      - Flash2Advance 256M (non-Ultra)
    - Faster transfer rates for most operations
    - Currently only supported by FlashGBX, not supported by official interface software
    - Available through the integrated Firmware Updater
    - It’s possible to return to the official firmware at any time using FlashGBX or the official firmware updater
  - Version L1 for GBxCart v1.4
    - Same as above but already integrated into the official firmware of GBxCart RW v1.4
- Added support for official cartridges with the MBC6 memory bank controller including its flash memory; tested with “Net de Get: Minigame @ 100” (CGB-BMVJ-JPN) *(thanks to endrift’s research at [gbdev](https://gbdev.gg8.se/forums/viewtopic.php?id=544))* (requires GBxCart RW firmware version L1+)
- Previously preliminarily added mapper support including for MBC7 and GBA Video cartridges is now working (requires GBxCart RW firmware version L1+)
- Added support for writing compilation ROMs to Nintendo Power GB-Memory Cartridges (DMG-MMSA-JPN); requires a .map file in the same directory as the ROM file; all this can be generated using orangeglo’s [GBNP ROM builder website](https://orangeglo.github.io/gbnp/index.html)
- Confirmed support for GB-M968 with 29LV160DB *(thanks bbsan)*
- Added support for ROM backup as well as save data backup and restore for 8M FLASH DACS cartridges
- Confirmed support for SD007_TSOP_29LV017D with L017D70VC *(thanks marv17)*
- Added support for 100BS6600_48BALL_V4 with 6600M0U0BE (the “369IN1” cartridge) *(thanks to BennVenn’s research on Discord)*
- Removed broken support for saving and restoring RTC registers of official TAMA5 cartridges inside the save file as it became clear that the year value was not correctly written; more research needed
- Support for optionally saving RTC registers of official Game Boy Advance cartridges inside the save file was added, however currently no emulator has support for synchronizing the clock
- Added an option for updating the RTC values (like the clock was running in the background) when restoring a save data file that has these values stored inside

### v1.4.2 (released 2021-03-17)
- Confirmed support for SD007_48BALL_64M_V8 with M29W160ET *(thanks marv17)*
- Fixed minor bugs

### v1.4.1 (released 2021-03-15)
- Added ROM and map backup support for official Nintendo Power GB-Memory Cartridges (DMG-MMSA-JPN); save data handling and ROM writing is not supported yet
- Added preliminary support for 4050M0Y0Q0-39VF512 with 4050M0Y0Q0 (requires a future firmware update of GBxCart RW)
- Added preliminary support for official cartridges with the MBC7 memory bank controller; tested with “Korokoro Kirby” (CGB-KKKJ-JPN) (requires a future firmware update of GBxCart RW)
- Added support for official cartridges with the M161 memory bank controller; tested with “Mani 4 in 1: Tetris + Alleyway + Yakuman + Tennis” (DMG-601CHN) (requires GBxCart RW firmware R26 or newer)
- Added support for B104 with MSP55LV128 *(thanks Zelante)*
- Added save data backup and restore support for official cartridges with ATMEL AT29LV512 flash chips; tested with a copy of “Mario Kart: Super Circuit” (AGB-AMKP-EUR)

### v1.4 (released 2021-02-28)
- Added a command line interface (CLI) as an alternative to the GUI interface; see `--help` command line switch for details or run interactive mode with `--cli`
- Fixed some minor compatibility issues for older systems that only have access to slightly outdated versions of the PySide2 package
- Added support for DMG-DHCN-20 with MX29LV320ET *(thanks Veund)*
- Added the option to export Game Boy Camera pictures in more file formats
- Added support for SD007_BV5_DRV with S29GL032M90TFIR4
- Confirmed support for SD007_BV5_DRV with MX29LV320BTC
- Added support for SD007_K8D3216_32M with MX29LV160CT *(thanks marv17)*
- Added support for AGB-E05-02 with M29W128FH
- Reading the sector map from CFI is experimental and can be enabled by adding `"sector_size_from_cfi":true,` to a flash cartridge config file
- Several flash cartridge types can now be written via full chip erase mode
- For specifying a specific MBC for writing to a DIY flash cartridge, it is now possible to add `"mbc":3,` or the like to its config file
- Removed officially unused Game Boy MBC types and ROM sizes from the drop down lists
- Added support for AGB-E05-01 with MX29GL128FHT2I-90G *(thanks antPL)*
- Added support for official cartridges with the HuC-1 memory bank controller; tested with “Pokémon Card GB” (DMG-ACXJ-JPN)
- Added support for official cartridges with the HuC-3 memory bank controller; tested with “Robot Poncots Sun Version” (DMG-HREJ-JPN)
- Added support for official cartridges with the TAMA5 memory bank controller; tested with “Game de Hakken!! Tamagotchi Osutchi to Mesutchi” (DMG-AOMJ-JPN) (requires GBxCart RW firmware R26 or newer)
- Added preliminary support for official GBA Video cartridges with 3D Memory; tested with “Shrek 2” (AGB-M2SE-USA) *(thanks to endrift’s article [“Dumping the Undumped”](https://mgba.io/2015/10/20/dumping-the-undumped/))* (requires a future firmware update of GBxCart RW)
- Added support for optionally saving and restoring RTC registers of official TAMA5 cartridges inside the save file
- Experimental support for optionally saving RTC registers of official MBC3+RTC+SRAM+BATTERY cartridges inside the save file using the 48 bytes save format explained on the [BGB website](https://bgb.bircd.org/rtcsave.html) was added. Latching the RTC register and restoring RTC register values to the cartridge is not supported at this time as it requires a new GBxCart RW hardware device revision.
- Added support for 4050_4400_4000_4350_36L0R_V5 with 4050L0YTQ2 *(thanks Shinichi999)*
- Fixed GUI support on macOS Big Sur *(thanks paarongiroux)*
- Added support for official cartridges with the MBC1M memory bank controller; tested with “Bomberman Collection” (DMG-ABCJ-JPN); save data backup is untested but should work
- Added support for official cartridges with the MMM01 memory bank controller; tested with “Momotarou Collection 2” (DMG-AM3J-JPN) (requires GBxCart RW firmware R26 or newer)
- Support for optionally saving and restoring RTC registers of official HuC-3+RTC+SRAM+BATTERY cartridges inside the save file using the 12 bytes save format used by the [hhugboy emulator](https://github.com/tzlion/hhugboy) was added.
- Added support for SD007_TSOP_48BALL with K8D3216UTC *(thanks marv17)*

### v1.3 (released 2021-01-21)
- Fixed a bug introduced in v1.1 that broke support for AGB-E08-09 with 29LV128DTMC-90Q *(thanks LucentW for reporting)*
- Will now show the application’s version number in message boxes

### v1.2.1 (released 2021-01-16)
- Fixed a bug introduced in v1.1 that broke MBC3 handling *(thanks marv17 for reporting)*
- Will now default back to 5V for Game Boy cartridges after unsuccessful flash chip auto-detection
- Added support for DIY carts with the AT49F040 flash chip *(thanks howie0210)*
- Minor bug fixes

### v1.1 (released 2021-01-11)
- Added support for GE28F128W30 with 128W30B0 *(thanks bbsan)*
- Added support for BX2006_TSOP_64BALL with GL256S *(thanks Paradoxical)*
- Confirmed support for SD007_48BALL_64M_V2 with M29W160ET *(thanks Paradoxical)*
- Added support for M6MGJ927 (no PCB text) *(thanks Super Maker)*
- Added a warning for very old reproduction cartridges with DRM that show “YJencrypted” as their game title *(thanks Super Maker)*
- Added a firmware check when writing to cartridges with flash chips manufactured by Sharp (unsupported by GBxCart RW firmware R25)
- Added optional verification of written data after ROM flashing *(thanks marv17 for the suggestion)*

### v1.0 (released 2021-01-01)
- Added a firmware check when writing to insideGadgets Game Boy Advance flash cartridges (requires GBxCart RW firmware R20 or newer)
- Confirmed support for Mr Flash 64M (rebranded BUNG Doctor GB Card 64M)
- Fixed a problem with writing to the insideGadgets 512 KB Game Boy flash cartridge

### v0.10 (released 2020-12-27)
- Fixed an issue with Raspberry Pi compatibility *(thanks ClassicOldSong)*
- Confirmed support for SD007_TSOP_48BALL with AM29LV160DB *(thanks marv17)*
- Fixed timeout errors with ROMs that have non-standard file sizes (e.g. trimmed files)
- Improved writing speed for most Game Boy reproduction cartridges by up to 40% (requires GBxCart RW firmware R24 or newer)
- Improved writing speed for M36L0R and similar flash chips by up to 80% (requires GBxCart RW firmware R24 or newer)
- Confirmed support for 4400 with 4400L0ZDQ0 *(thanks Zeii)*
- Backup and restore save data of flash chips manufactured by SANYO requires GBxCart RW firmware R24 or newer; a warning message for this will now be displayed in necessary cases
- Added the option to check for updates at application start *(thanks Icesythe7 and JFox for the suggestion and help)*
- Added support for BX2006_TSOPBGA_0106 with K8D6316UTM-PI07 *(thanks LucentW)*
- Added support for the currently available insideGadgets Game Boy Advance flash cartridges *(thanks AlexiG)*
- Added a Game Boy Camera album viewer and picture extractor

### v0.9β (released 2020-12-17)
- Confirmed support for BX2006_TSOP_64BALL with GL128S
- Confirmed support for SD007_48BALL_64M_V2 with GL032M11BAIR4
- Added support for 4050_4400_4000_4350_36L0R_V5 with M36L0R8060T/M36L0T8060T
- Rewrote parts of the GBxCart RW interface code
- When flashing ROM files, empty chunks of data will now be skipped
- Fixed config files for MSP55LV128 and MSP55LV128M flash chips
- Confirmed support for SD007_48BALL_64M_V6 with 36VF3204
- Confirmed support for SD007_TSOP_48BALL with 36VF3204
- Added the option to add date and time to suggested file names for save data backups *(thanks easthighNerd for the suggestion)*
- Added a check and warning for unstable ROM readings
- Added Common Flash Interface query for both unknown and known flash cartridge types
- Added support for 36L0R8-39VF512 with M36L0R8060B *(thanks LucentW)*
- Added support for another version of 36L0R8-39VF512 with M36L0R8060B/M36L0R8060T *(thanks AndehX)*
- Added support for AGB-E05-02 with M29W128GH *(thanks marv17)*
- Added backup and restore of 1M SRAM save data in GBA mode
- Confirmed support for BX2006_TSOPBGA_0106 with M29W640GB6AZA6 *(thanks LucentW)*
- Confirmed support for AGB-E05-01 with GL128S
- Improved writing speed for MSP55LV128M, S29GL128 and similar flash chips (requires GBxCart RW firmware R23 or newer)
- Before flashing a ROM it will now be checked if its logo data and header checksum are valid and a warning will be shown if not
- Added support for SD007_BV5_V3 with 29LV160BE-90PFTN *(thanks LucentW)*
- Added support for SD007_BV5_V3 with HY29LV160BT *(thanks LucentW)*
- Added support for SD007_48BALL_64M_V5 with 36VF3203 *(thanks LucentW)*
- Added support for SD007_TSOP_48BALL with M29W160ET *(thanks LucentW)*
- Added support for AGB-E08-09 with 29LV128DTMC-90Q *(thanks LucentW)*
- Confirmed support for SD007_TSOP_48BALL with L160DB12VI *(thanks marv17)*
- Added support for SD007_BV5_DRV with M29W320DT *(thanks Frost Clock)*
- Added experimental *Fast Read Mode* support for GBxCart RW with firmware R19+; can be up to 20% faster, but the functioning currently heavily relies on system performance and drivers
- Bumped the required minimum firmware version of GBxCart RW to R19
- Confirmed support for 4050_4400_4000_4350_36L0R_V5 with M36L0R7050T
- Added the option to enable the preference of sector erase over chip erase when flashing a ROM; this can improve flashing speed for ROMs smaller than the flash chip capacity
- Some flash chips may have reversed sectors despite shared flash ID; if you think your cartridge is affected, you can add `"sector_reversal":true,` to its config file for a prompt upon flashing
- Renamed config.ini to settings.ini to avoid confusion with the term “config file”

### v0.8β (released 2020-10-03)
- Added support for DIY carts with AM29F016/AM29F016B with AUDIO as WE *(thanks AndehX)*
- Renamed `VIN` to `AUDIO` in config files and the command line switch `--resetconfig` to `--reset`
- Added experimental support for GBxCart RW revisions other than v1.3 and fixed a crash when connecting to unknown revisions of the GBxCart RW
- The app is now available as a package and can be installed directly through *pip* *(thanks JFox)*
- Changed the way configuration files are stored (for details call with `--help` command line switch)
- Added a button that opens a file browser to the currently used config directory for easy access
- Added the option to erase/wipe the save data on a cartridge
- Rearranged some buttons on the main window so that the newly added button popup menus don’t block anything
- Improved the database for Game Boy Advance titles (now detects SRAM_F_V### save types properly)
- Rewrote some of the save data handling for Game Boy Advance cartridges to speed transfers up a bit
- Fixed a couple of instability issues that used to caused timeouts on macOS *(thanks julgr)*
- Confirmed support for SD007_48BALL_64M_V5 with 29DL163BD-90 *(thanks julgr)*
- Added an option for flashing at 5V for a few flash cartridge types that sometimes require this; if you think your cartridge is affected, you can add `"voltage_variants":true,` to the config file for it
- Fixed support for Windows 7 when using pre-compiled exe file packages
- Reduced size and decompression time of the pre-compiled exe file packages by excluding unnecessary DLL files
- Fixed a timing issue that could sometimes cause a loss of save data when hot-swapping Game Boy cartridges
- Added some warnings that may help with troubleshooting
- Added taskbar progress visualization on Windows systems

### v0.7β (released 2020-09-25)
- First started tracking changes
- Added a way to launch the flash cartridge type auto-detection process from the type list
- Added support for SD007_48BALL_64M_V6 with 29DL163BD-90 *(thanks LovelyA72)*
- Confirmed support for BX2006_0106_NEW with S29GL128N10TFI01 (same as AGB-E05-01 with MSP55LV128M) *(thanks litlemoran)*
- Fixed config file for 4455_4400_4000_4350_36L0R_V3 with M36L0R705 (sector size map was incomplete)
- Renamed some labels of flash cartridge types
- Made config files UTF-8 compatible
- File open and save dialogs will now remember the last used directory for ROM files and save data files respectively (stored in settings.ini in AppData/Roaming), clearable with the `--reset` switch or by editing/deleting settings.ini
- Added CRC32 checksum comparison for Game Boy Advance games by using a database based on header SHA1 hashes
- Fixed a bug with save data restore and improved save data backup speed
- Fixed a few status message errors
- Added a warning when changing platforms
- Made some messages suppressible (stored in settings.ini)
- Added detection of ungraceful device disconnects when starting a new task, with optional automatic reconnect
- First public beta release
