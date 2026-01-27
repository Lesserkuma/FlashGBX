/*****************************************************************************
**                      Copyright  (C)  WCH  2001-2023                      **
**                      Web:  http://wch.cn                                 **
*****************************************************************************/

//USB bus interface chip CH341/7 parallel port application layer interface library, CH347 based on 480mbps high-speed USB bus, extends UART/SPI/I2C/JTAG
//CH347-DLL  V1.2
//Environment: Windows 98/ME, Windows 2000/XP, WIN7/8/10/11,and later.
//support USB chip: CH341, CH341A,CH347
//USB => Parallel, I2C, SPI, JTAG, SWD, UART ...
//Notes:
//Copyright (c) 2023 Nanjing Qinheng Microelectronics Co., Ltd.


#ifndef _CH347_DLL_H
#define _CH347_DLL_H

#ifdef __cplusplus
extern "C" {
#endif

#ifdef _WIN64
#define mOFFSET(s, m) ((ULONG_PTR) & (((s *)0)->m)) // Define macro, get relative offset address of structure member
#else
#define mOFFSET(s, m) ((ULONG) & (((s *)0)->m)) // Define macro, get relative offset address of structure member
#endif

#ifndef max
#define max(a, b) (((a) > (b)) ? (a) : (b)) // Determine maximum value
#endif

#ifndef min
#define min(a, b) (((a) < (b)) ? (a) : (b)) // Determine minimum value
#endif

#ifdef ExAllocatePool
#undef ExAllocatePool // Delete memory allocation with TAG
#endif

#ifndef NTSTATUS
typedef LONG NTSTATUS; // Return status
#endif

// Sharing CH341WDM driver with CH341DLL
#ifndef _CH341_DLL_H
typedef struct _USB_SETUP_PKT { // USB control transfer structure
    UCHAR mUspReqType;          // 00H request type
    UCHAR mUspRequest;          // 01H request code
    union {
        struct {
            UCHAR mUspValueLow;  // 02H Value parameter low byte
            UCHAR mUspValueHigh; // 03H Value parameter high byte
        };
        USHORT mUspValue; // 02H-03H value parameters
    };
    union {
        struct {
            UCHAR mUspIndexLow;  // 04H index parameter low byte
            UCHAR mUspIndexHigh; // 05H index parameter high byte
        };
        USHORT mUspIndex; // 04H-05H index parameter
    };
    USHORT mLength; // 06H-07H data length
} mUSB_SETUP_PKT, *mPUSB_SETUP_PKT;

typedef struct _WIN32_COMMAND { // Define WIN32 command interface structure
    union {
        ULONG mFunction;  // Specify function code or pipe number when input
        NTSTATUS mStatus; // Return operation status when output
    };
    ULONG mLength; // Access length, return the length of subsequent data
    union {
        mUSB_SETUP_PKT mSetupPkt; // Data request in the setup phase of USB control transfer
        UCHAR mBuffer[512];       // Data buffer, the length is 0 to 255B
    };
} mWIN32_COMMAND, *mPWIN32_COMMAND;
// WIN32 application layer interface command
#define IOCTL_CH341_COMMAND (FILE_DEVICE_UNKNOWN << 16 | FILE_ANY_ACCESS << 14 | 0x0f34 << 2 | METHOD_BUFFERED) // Private interface

#define mWIN32_COMMAND_HEAD mOFFSET(mWIN32_COMMAND, mBuffer) // Header length of WIN32 command interface

#define mCH341_MAX_NUMBER 32 // Maximum number of CH341/7 connected at the same time

#define mMAX_BUFFER_LENGTH 0x1000 // Maximum length of the data buffer is 4096

#define mMAX_COMMAND_LENGTH (mWIN32_COMMAND_HEAD + mMAX_BUFFER_LENGTH) // Maximum data length plus command structure header length

#define mDEFAULT_BUFFER_LEN 0x0400 // Data buffer default length is 1024

#define mDEFAULT_COMMAND_LEN (mWIN32_COMMAND_HEAD + mDEFAULT_BUFFER_LEN) // default data length plus command structure header length

// CH341 endpoint address
#define mCH347_ENDP_DATA_UP   0x86 // Data upload endpoint of CH347
#define mCH347_ENDP_DATA_DOWN 0x06 // Data download endpoint of CH347

// Pipeline operation command provided by equipment layer interface
#define mPipeDeviceCtrl 0x00000004 // CH347 integrated control pipeline
#define mPipeDataUp     0x00000006 // CH347 data block upload pipeline
#define mPipeDataDown   0x00000007 // CH347 data block download pipeline

// Function code of application layer interface
#define mFuncNoOperation  0x00000000 // No operation
#define mFuncGetVersion   0x00000001 // Get driver version number
#define mFuncGetConfig    0x00000002 // Get USB device configuration descriptor
#define mFuncSetTimeout   0x00000009 // Set USB communication timeout
#define mFuncSetExclusive 0x0000000b // Set exclusive use
#define mFuncResetDevice  0x0000000c // Reset USB device
#define mFuncResetPipe    0x0000000d // Reset USB pipe
#define mFuncAbortPipe    0x0000000e // Cancel data request of USB pipe
#define mFuncBufferMode   0x00000020 // Set buffer upload mode and query data length in the buffer
#define mFuncBufferModeDn 0x00000021 // Set buffer download mode and query data length in the buffer
#define mFuncGetVersionEx 0x00000022 // Get driver version number and chip model
// USB device standard request code
#define mUSB_CLR_FEATURE 0x01
#define mUSB_SET_FEATURE 0x03
#define mUSB_GET_STATUS  0x00
#define mUSB_SET_ADDRESS 0x05
#define mUSB_GET_DESCR   0x06
#define mUSB_SET_DESCR   0x07
#define mUSB_GET_CONFIG  0x08
#define mUSB_SET_CONFIG  0x09
#define mUSB_GET_INTERF  0x0a
#define mUSB_SET_INTERF  0x0b
#define mUSB_SYNC_FRAME  0x0c

// Vendor specific request type of CH341 control transfer
#define mCH341_VENDOR_READ  0xC0 // CH341 vendor-specific read operation via control transfer
#define mCH341_VENDOR_WRITE 0x40 // CH341 vendor-specific write operation via control transfer

#define mCH341A_CMD_I2C_STREAM 0xAA // Command package of I2C, starting with the second  byte is I2C command stream
#define mCH341A_CMD_UIO_STREAM 0xAB // Command package of UIO, starting with the second  byte is command stream
#define mCH341A_CMD_PIO_STREAM 0xAE // Command package of PIO, starting with the second  byte is data stream
// Vendor specific request code of CH341A control transfer
#define mCH341A_BUF_CLEAR 0xB2 // Clear incomplete data
#define mCH341A_I2C_CMD_X 0x54 // Issue command of I2C interface and executes it immediately
#define mCH341A_DELAY_MS  0x5E // Delay specified time, in millisecond
#define mCH341A_GET_VER   0x5F // Get chip version

#define mCH341A_CMD_I2C_STM_STA 0x74                              // I2C interface command stream: generate start bit
#define mCH341A_CMD_I2C_STM_STO 0x75                              // I2C interface command stream: generate stop bit
#define mCH341A_CMD_I2C_STM_OUT 0x80                              // I2C interface command stream: output data, bit5 - bit0 is length, subsequent bytes are data, length 0 only sends one byte and returns an response
#define mCH341A_CMD_I2C_STM_IN  0xC0                              // I2C interface command stream: input data, bit 5-bit 0 is length, length 0 only receives one byte and sends no response
#define mCH341A_CMD_I2C_STM_MAX (min(0x3F, mCH341_PACKET_LENGTH)) // Maximum length of a single command input/output data of I2C interface command stream
#define mCH341A_CMD_I2C_STM_SET 0x60                              // I2C interface command stream: set parameters, bit2=SPI I/O number (0= single input single output, 1= double input double output), bit1 bit0=I2C speed (00= low speed, 01= standard, 10= fast, 11= high speed)
#define mCH341A_CMD_I2C_STM_US  0x40                              // I2C interface command stream: delay in microseconds, bit3 - bit0 is delay value
#define mCH341A_CMD_I2C_STM_MS  0x50                              // I2C interface command stream: delay in milliseconds, bit3 - bit0 is delay value
#define mCH341A_CMD_I2C_STM_DLY 0x0F                              // Maximum value of a single command delay of I2C interface command stream
#define mCH341A_CMD_I2C_STM_END 0x00                              // I2C interface command stream: command package ends in advance

#define mCH341A_CMD_UIO_STM_IN  0x00 // UIO interface command stream: input data D7-D0
#define mCH341A_CMD_UIO_STM_DIR 0x40 // UIO interface command stream: set I/O direction D5-D0, bit5 - bit0 is direction data
#define mCH341A_CMD_UIO_STM_OUT 0x80 // UIO interface command stream: output data D5-D0, bit5 - bit0 is data
#define mCH341A_CMD_UIO_STM_US  0xC0 // UIO interface command stream: delay in microseconds, bit5 - bit0 is delay value
#define mCH341A_CMD_UIO_STM_END 0x20 // UIO interface command stream: command package ends in advance

#define MAX_DEVICE_PATH_SIZE 128 // Maximum number of characters for device name
#define MAX_DEVICE_ID_SIZE   64  // Maximum number of characters for device ID
#endif _CH341_DLL_H

// Driver interface
#define CH347_USB_VENDOR 0
#define CH347_USB_HID    2
#define CH347_USB_VCP    3

// CH347_USB_VENDOR support CH341/7
#define CHIP_TYPE_CH341  0
#define CHIP_TYPE_CH347  1
#define CHIP_TYPE_CH347F 2
#define CHIP_TYPE_CH347T CHIP_TYPE_CH347

// Chip function interface type
#define CH347_FUNC_UART         0
#define CH347_FUNC_SPI_IIC      1
#define CH347_FUNC_JTAG_IIC     2
#define CH347_FUNC_JTAG_IIC_SPI 3 // CH347F

#define DEFAULT_READ_TIMEOUT  500 // Default read timeout milliseconds
#define DEFAULT_WRITE_TIMEOUT 500 // Default write timeout milliseconds

#define mCH347_PACKET_LENGTH 512 // Length of data packet supported by CH347
#pragma pack(1)
// SPI controller configuration
typedef struct _SPI_CONFIG {
    UCHAR iMode;                  // 0-3:SPI Mode0/1/2/3
    UCHAR iClock;                 // 0=60MHz, 1=30MHz, 2=15MHz, 3=7.5MHz, 4=3.75MHz, 5=1.875MHz, 6=937.5KHz, 7=468.75KHz
    UCHAR iByteOrder;             // 0=LSB, 1=MSB
    USHORT iSpiWriteReadInterval; // SPI regular read/write data command, in uS
    UCHAR iSpiOutDefaultData;     // Default output data when SPI reads data
    ULONG iChipSelect;            // Chip select control, Bit7=0: ignore chip select control; bit7=1: parameter is valid, bit1/bit0 are 00/01 to select the CS1/CS2 pins as low-level active chip select, respectively.
    UCHAR CS1Polarity;            // Bit0: CS1 polarity control: 0: active low; 1: active high;
    UCHAR CS2Polarity;            // Bit0: CS2 polarity control: 0: active low; 1: active high;
    USHORT iIsAutoDeativeCS;      // Auto undo chip selection or not after operation is completed
    USHORT iActiveDelay;          // Setting delay time for performing read/write operations after chip selection, in uS
    ULONG iDelayDeactive;         // Delay time for read/write operations after de-selecting chip selection, in uS
} mSpiCfgS, *mPSpiCfgS;

// Device information
typedef struct _DEV_INFOR {
    UCHAR iIndex;                // Currently open index
    UCHAR DevicePath[MAX_PATH];  // Device link name, used for CreateFile
    UCHAR UsbClass;              // Driver Type 0:CH347_USB_CH341, 2:CH347_USB_HID, 3:CH347_USB_VCP
    UCHAR FuncType;              // Functional Type 0:CH347_FUNC_UART, 1:CH347_FUNC_SPI_I2C, 2:CH347_FUNC_JTAG_I2C
    CHAR DeviceID[64];           // USB\VID_xxxx&PID_xxxx
    UCHAR ChipMode;              // Chip Mode, 0:Mode0(UART0/1); 1:Mode1(Uart1+SPI+I2C); 2:Mode2(HID Uart1+SPI+I2C) 3:Mode3(Uart1+Jtag+I2C) 4:CH347F(Uart*2+Jtag/SPI/I2C)
    HANDLE DevHandle;            // Device handle
    USHORT BulkOutEndpMaxSize;   // Upload endpoint size
    USHORT BulkInEndpMaxSize;    // Downstream endpoint size
    UCHAR UsbSpeedType;          // USB speed, 0:FS,1:HS,2:SS
    UCHAR CH347IfNum;            // USB interface number: CH347T: IF0:UART;   IF1:SPI/IIC/JTAG/GPIO
                                 //                       CH347F: IF0:UART0;  IF1:UART1; IF2:SPI/IIC/JTAG/GPIO
    UCHAR DataUpEndp;            // Bulk upload endpoint address
    UCHAR DataDnEndp;            // Bulk download endpoint address
    CHAR ProductString[64];      // USB product string
    CHAR ManufacturerString[64]; // USB manufacturer string
    ULONG WriteTimeout;          // USB write timeout
    ULONG ReadTimeout;           // USB read timeout
    CHAR FuncDescStr[64];        // Interface function descriptor
    UCHAR FirewareVer;           // Firmware version, hex value

} mDeviceInforS, *mPDeviceInforS;
#pragma pack()

// CH347 each mode public function, support CH347 all modes of open, close, USB read, USB write, including HID
// Open USB device
HANDLE WINAPI CH347OpenDevice(ULONG DevI);

// Close USB device
BOOL WINAPI CH347CloseDevice(ULONG iIndex);

// Get device information
BOOL WINAPI CH347GetDeviceInfor(ULONG iIndex, mDeviceInforS *DevInformation);

// Get CH347 chip type:CHIP_TYPE_CH347T/CHIP_TYPE_CH347F
UCHAR WINAPI CH347GetChipType(ULONG iIndex); // Specify device serial number

// Obtain driver version, library version, device version and chip type(CH341(FS)/CH347HS)
BOOL WINAPI CH347GetVersion(ULONG iIndex,
                            PUCHAR iDriverVer,
                            PUCHAR iDLLVer,
                            PUCHAR ibcdDevice,
                            PUCHAR iChipType); // CHIP_TYPE_CH341/7

typedef VOID(CALLBACK *mPCH347_NOTIFY_ROUTINE)( // Device plug/unplug notification event callback routine
    ULONG iEventStatus);                        // Device plug/unplug event and current status (define below): 0=Device unplug event, 3=Device insertion event

#define CH347_DEVICE_ARRIVAL     3 // Device insertion event, has been inserted
#define CH347_DEVICE_REMOVE_PEND 1 // Device wil be unplugged
#define CH347_DEVICE_REMOVE      0 // Device unplug event, has been pulled out

// Set the device event notification routine
BOOL WINAPI CH347SetDeviceNotify(ULONG iIndex,                           // Specify device serial number, 0 corresponds to the first device
								 PCHAR iDeviceID,                        // Optional parameter, points to a string, specifying the monitored device ID, ending with \0.
								 mPCH347_NOTIFY_ROUTINE iNotifyRoutine); // Specifies the port device event callback program. If it is NULL, tehn cancel the event notification, otherwise call the routine when an event is detected.

// Read USB data block
BOOL WINAPI CH347ReadData(ULONG iIndex,     // Specify device serial number
                          PVOID oBuffer,    // Points to a buffer large enough to save the read data
                          PULONG ioLength); // Points to length unit; When input, it is the length to be read, and after return, it is the actual length to be read.

// Write USB data block
BOOL WINAPI CH347WriteData(ULONG iIndex,     // Specify device serial number
                           PVOID iBuffer,    // Points to a buffer large enough to save the written data
                           PULONG ioLength); // Points to length unit; When input, it is the length to be written, and after return, it is the actual length to be written.

// Set the timeout of USB data read/write
BOOL WINAPI CH347SetTimeout(ULONG iIndex,        // Specify device serial number
                            ULONG iWriteTimeout, // Specifies the timeout for USB to write data blocks, in mS, 0xFFFFFFFF specifies no timeout (default)
                            ULONG iReadTimeout); // Specifies the timeout for USB to read data blocks, in mS, 0xFFFFFFFF specifies no timeout (default)

/***************SPI********************/
// SPI controller initialization
BOOL WINAPI CH347SPI_Init(ULONG iIndex, mSpiCfgS *SpiCfg);

//CH347F set SPI clock frequency. iSpiSpeedHz= 0=60MHz,  1=30MHz,  2=15MHz,  3=7.5MHz,  4=3.75MHz,  5=1.875MHz,  6=937.5KHz锛� 7=468.75KHz
BOOL WINAPI CH347SPI_SetFrequency(ULONG iIndex, ULONG iSpiSpeedHz);

// CH347F set the SPI databit
BOOL WINAPI CH347SPI_SetDataBits(ULONG iIndex,
                                 UCHAR iDataBits); // iDataBits= 0:8bit, 1:16bit

// Get SPI controller configuration information
BOOL WINAPI CH347SPI_GetCfg(ULONG iIndex, mSpiCfgS *SpiCfg);

// Sets the chip select state, call CH347SPI_Init to set up the CS before use
BOOL WINAPI CH347SPI_ChangeCS(ULONG iIndex,   // Specify device serial number
                              UCHAR iStatus); // 0= Undo chip select, 1=Set chip select

// Set SPI chip select
BOOL WINAPI CH347SPI_SetChipSelect(ULONG iIndex,           // Specify device serial number
                                   USHORT iEnableSelect,   // Lower 8-bit is CS1, higher 8-bit is CS2; A byte value of 1= sets CS, 0= ignores this CS setting
                                   USHORT iChipSelect,     // Lower 8-bit is CS1, higher 8-bit is CS2; A byte value of 1= sets CS, 0= ignores this CS setting
                                   ULONG iIsAutoDeativeCS, // Lower 16-bit is CS1, higher 16-bit is CS2; auto undo chip selection or not after operation is completed
                                   ULONG iActiveDelay,     // Lower 16-bit is CS1, higher 16-bit is CS2; set the delay time of performing read/write operations after chip selection, in us
                                   ULONG iDelayDeactive);  // Lower 116-bit is CS1, higher 16-bit is CS2; do not set the delay time of performing read/write operations after chip selection, in us

// SPI4 write data
BOOL WINAPI CH347SPI_Write(ULONG iIndex,      // Specify device serial number
                           ULONG iChipSelect, // Chip select control, bit7=0: ignore chip select control, bit7=1: perform chip select
                           ULONG iLength,     // Number of data bytes ready to be transferred
                           ULONG iWriteStep,  // Length of a single block to be read
                           PVOID ioBuffer);   // Point to a buffer, place the data to be written out from MOSI

// SPI4 read data, no need to write data first, much more efficient than CH347SPI_WriteRead
BOOL WINAPI CH347SPI_Read(ULONG iIndex,      // Specify device serial number
                          ULONG iChipSelect, // Chip select control, bit7=0: ignore chip select control, bit7=1: perform chip select
                          ULONG oLength,     // Number of data bytes ready to be transferred
                          PULONG iLength,    // Number of data bytes of data to be read
                          PVOID ioBuffer);   // Points to a buffer, place the data to be written out from DOUT, returned data is read from DIN

// Handle SPI data stream, 4-wire interface
BOOL WINAPI CH347SPI_WriteRead(ULONG iIndex,      // Specify device serial number
                               ULONG iChipSelect, // Chip select control, bit7=0: ignore chip select control, bit7=1: perform chip select
                               ULONG iLength,     // Number of data bytes ready to be transferred
                               PVOID ioBuffer);   // Points to a buffer that place the data to be written out from DOUT, returned data is read from DIN

// Handle SPI data stream, 4-wire interface
BOOL WINAPI CH347StreamSPI4(ULONG iIndex,      // Specify device serial number
                            ULONG iChipSelect, // Chip select control, bit7=0: ignore chip select control, bit7=1: parameter is valid
                            ULONG iLength,     // Number of data bytes ready to be transferred
                            PVOID ioBuffer);   // Points to a buffer, places data to be written out from DOUT, returned data is read from DIN

/***************JTAG********************/
// JTAG interface initialization, set mode and speed
BOOL WINAPI CH347Jtag_INIT(ULONG iIndex,
                           UCHAR iClockRate); // Communication speed; valid values are 0-5, larger values indicating faster speeds

// Gets Jtag speed configuration
BOOL WINAPI CH347Jtag_GetCfg(ULONG iIndex,      // Specify device serial number
                             UCHAR *ClockRate); // Communication speed; valid values are 0-5, larger values indicating faster speeds
							 
// Changing the TMS value for state switching
BOOL WINAPI CH347Jtag_TmsChange(ULONG iIndex,    // Specify device serial number
                                PUCHAR tmsValue, // TMS bit value for switching, in bytes
                                ULONG Step,      // Number of valid TMS bits stored in tmsValue
                                ULONG Skip);     // Valid start bit

// Read/write data in the shift-dr/ir state, switch to Exit DR/IR state after execution.
// State machine: Shift-DR/ ir.rw.->Exit DR/IR
BOOL WINAPI CH347Jtag_IoScan(ULONG iIndex,
                             PUCHAR DataBits,  // Data bits to be transmitted
                             ULONG DataBitsNb, // Number of bits of data to be transmitted
                             BOOL IsRead);     // Read data or not

// Switch to shift-dr/ir state for read/write, after execution is complete, If it is the last packet, then shift to Exit DR/IR; if not, then in Shift-DR/IR
// State machine :Shift-DR/IR.RW.. ->[Exit DR/IR]
BOOL WINAPI CH347Jtag_IoScanT(ULONG iIndex,     // Specify the device number
                              PUCHAR DataBits,  // Data bits to be transmitted
                              ULONG DataBitsNb, // Number of bits of data to be transmitted
                              BOOL IsRead,      // Read data or not
                              BOOL IsLastPkt);  // Is it the last packet or not

// CH347 reset Tap state function. six or more consecutive TCKs & TMS are high锟斤拷will set the state machine to Test-Logic Reset
ULONG WINAPI CH347Jtag_Reset(ULONG iIndex);

// CH347 operates TRST to complete a hardware reset
BOOL WINAPI CH347Jtag_ResetTrst(ULONG iIndex, BOOL TRSTLevel);

// Bit band mode JTAG IR/DR data read/write, suitable for read/write small amounts of data. Such as command operation, state machine switching and other control transfer. For batch data transmission, recommended CH347Jtag_WriteRead_Fast
// Command packages are read/write in batches of 4096 bytes
// State machine: Run-Test->Shift-IR/DR..->Exit IR/DR -> Run-Test
BOOL WINAPI CH347Jtag_WriteRead(ULONG iIndex,          // Specify device serial number
                                BOOL IsDR,             // =TRUE: DR data read/write, =FALSE:IR data read/write
                                ULONG iWriteBitLength, // Write length, the length to be written
                                PVOID iWriteBitBuffer, // Points to a buffer to place data ready to be written out
                                PULONG oReadBitLength, // Points to the length unit, returned length is the actual length read
                                PVOID oReadBitBuffer); // Points to a buffer large enough to place the read data

// JTAG IR/DR data batch read/write, for multi-byte sequential read/write. Such as JTAG download firmware. Because the hardware has a 4K buffer, if you write first and read later, the length will not exceed 4096 bytes. The buffer size can be adjusted by yourself
// State machine: Run-Test->Shift-IR/DR..->Exit IR/DR -> Run-Test
BOOL WINAPI CH347Jtag_WriteRead_Fast(ULONG iIndex,          // Specify device serial number
                                     BOOL IsDR,             // =TRUE: DR data read/write, =FALSE:IR data read/write
                                     ULONG iWriteBitLength, // Write length, length to be written
                                     PVOID iWriteBitBuffer, // Points to a buffer to place data ready to be written out
                                     PULONG oReadBitLength, // Point to the length unit, returned length is the actual length read.
                                     PVOID oReadBitBuffer); // Points to a buffer large enough to place the read data

// Bitband mode JTAG IR/DR data read/write, suitable for read/write small amounts of data. Such as command operation, state machine switching and other control transfer. For batch data transmission, recommended CH347Jtag_WriteRead_Fast
// Command packages are read/write in batches of 4096 bytes
// State machine:Run-Test-> Shift-IR/DR..->Exit IR/DR -> Run-Test
BOOL WINAPI CH347Jtag_WriteReadEx(ULONG iIndex,          // Specify device serial number
                                  BOOL IsInDrOrIr,       // =TRUE: in SHIFT-DR read/write  ==FALSE: Run-Test->Shift-IR/DR.(perform data interaction).->Exit IR/DR -> Run-Test
                                  BOOL IsDR,             // =TRUE: DR data read/write, =FALSE:IR data read/write
                                  ULONG iWriteBitLength, // Write length, The length to be written
                                  PVOID iWriteBitBuffer, // Points to a buffer to place data ready to be written out
                                  PULONG oReadBitLength, // Point to the length unit, returned length is the actual length read
                                  PVOID oReadBitBuffer); // Points to a buffer large enough to place the read data

// JTAG IR/DR data batch read/write, for multi-byte sequential read/write. Such as JTAG download firmware. Because the hardware has a 4K buffer, if you write first and read later, the length will not exceed 4096 bytes. The buffer size can be adjusted by yourself
// State machine:Run-Test->Shift-IR/DR..->Exit IR/DR -> Run-Test
BOOL WINAPI CH347Jtag_WriteRead_FastEx(ULONG iIndex,          // Specify the device number
                                       BOOL IsInDrOrIr,       // =TRUE: In SHIFT-DR read/write  ==FALSE: Run-Test->Shift-IR/DR.(perform data interaction).->Exit IR/DR -> Run-Test
                                       BOOL IsDR,             // =TRUE: DR read/write, =FALSE:IR data read/write
                                       ULONG iWriteBitLength, // Write length. The length to be written
                                       PVOID iWriteBitBuffer, // Points to a buffer to place data ready to be written out
                                       PULONG oReadBitLength, // Point to the length unit, returned length is the actual length read
                                       PVOID oReadBitBuffer); // Points to a buffer large enough to place the read data

// Switch the JTAG state machine
BOOL WINAPI CH347Jtag_SwitchTapState(UCHAR TapState);

// JTAG DR Write, in bytes, for multi-byte sequential read/write. such as JTAG firmware download operations.
// State machine: Run-Test->Shift-DR..->Exit DR -> Run-Test
BOOL WINAPI CH347Jtag_ByteWriteDR(ULONG iIndex,        // Specify the device serial number
                                  ULONG iWriteLength,  // Write length, length of bytes to be written
                                  PVOID iWriteBuffer); // Points to a buffer, place the data ready to be written out

// JTAG DR read, in bytes, for multi-byte sequential read.
// State machine: Run-Test->Shift-DR..->Exit DR -> Run-Test
BOOL WINAPI CH347Jtag_ByteReadDR(ULONG iIndex,       // Specify the device serial number
                                 PULONG oReadLength, // Points to the length unit, returned length is the actual length read
                                 PVOID oReadBuffer); // Points to a buffer large enough to place the read data

// JTAG IR write, in bytes, for multi-byte sequential write.
// State machine: Run-Test->Shift-IR..->Exit IR -> Run-Test
BOOL WINAPI CH347Jtag_ByteWriteIR(ULONG iIndex,        // Specify device serial number
                                  ULONG iWriteLength,  // Write length, the length of bytes to be written
                                  PVOID iWriteBuffer); // Points to a buffer, place the data ready to be written out

// JTAG IR read, in bytes, for multi-byte sequential read/write.
// The state machine: Run-Test->Shift-IR..->Exit IR -> Run-Test
BOOL WINAPI CH347Jtag_ByteReadIR(ULONG iIndex,       // Specify device serial number
                                 PULONG oReadLength, // Points to the length unit, returned data is the length of actual bytes read.
                                 PVOID oReadBuffer); // Points to a buffer large enough to place the read data

// Bitband mode JTAG DR data write. suitable for read/write small amounts of data. Such as command operation, state machine switching and other control transfer. For batch data transmission, recommended CH347Jtag_ByteWriteDR
// The state machine: Run-Test->Shift-DR..->Exit DR -> Run-Test
BOOL WINAPI CH347Jtag_BitWriteDR(ULONG iIndex,           // Specify device serial number
                                 ULONG iWriteBitLength,  // Points to the length unit, returned data is the length of actual bytes read.
                                 PVOID iWriteBitBuffer); // Points to a buffer large enough to place the read data

// Bit band mode JTAG IR data write. Suitable for read/write small amounts of data. Such as command operation, state machine switching and other control transfer. For batch data transmission, recommended CH347Jtag_ByteWriteIR
// The state machine: Run-Test->Shift-IR..->Exit IR -> Run-Test
BOOL WINAPI CH347Jtag_BitWriteIR(ULONG iIndex,           // Specify device serial number
                                 ULONG iWriteBitLength,  // Points to the length unit, returned data is the length of actual bytes read.
                                 PVOID iWriteBitBuffer); // Points to a buffer large enough to place the read data

// Bit band mode JTAG IR data read. Suitable for reading and writing small amounts of data. Such as command operation, state machine switching, etc. For batch data transfer, CH347Jtag_ByteReadIR is recommended.
// The state machine: Run-Test->Shift-IR..->Exit IR -> Run-Test
BOOL WINAPI CH347Jtag_BitReadIR(ULONG iIndex,          // Specify device serial number
                                PULONG oReadBitLength, // Points to the length unit, returned data is the length of actual bytes read.
                                PVOID oReadBitBuffer); // Points to a buffer large enough to place the read data

// Bit band mode JTAG DR data read. Suitable for reading and writing small amounts of data. For batch and high-speed data transfer, CH347Jtag_ByteReadDR is recommended
// The state machine: Run-Test->Shift-DR..->Exit DR -> Run-Test
BOOL WINAPI CH347Jtag_BitReadDR(ULONG iIndex,          // Specify device serial number
                                PULONG oReadBitLength, // Points to the length unit, returned data is the length of actual bytes read.
                                PVOID oReadBitBuffer); // Points to a buffer large enough to place the read data

/***************GPIO********************/
// Get the GPIO direction and pin level of CH347
BOOL WINAPI CH347GPIO_Get(ULONG iIndex,
                          UCHAR *iDir,   // Pin direction: GPIO0-7 corresponding bit0-7, 0: input; 1: output
                          UCHAR *iData); // GPIO0 level: GPIO0-7 corresponding bit0-7, 0: low level; 1: high level

// Set the GPIO direction and pin level of CH347
BOOL WINAPI CH347GPIO_Set(ULONG iIndex,		  // Specify device serial number
                          UCHAR iEnable,      // Data valid flag: corresponding bit0-7, correspond to GPIO0-7.
                          UCHAR iSetDirOut,   // Sets I/O direction, A bit is 0 means corresponding pin is input, a bit is 1 means corresponding pin is output. GPIO0-7 corresponds to bit0-7.
                          UCHAR iSetDataOut); // Output data. If I/O direction is output, then a pin outputs low level when a bit cleared to 0, a pin outputs high level when a bit set to 1

typedef VOID(CALLBACK *mPCH347_INT_ROUTINE)( // Interrupt service routine
    PUCHAR iStatus);                         // For interrupt status data, refer to the bit description below
// 8 byte GPIO0-7 pin status, the bits per byte are defined as follows.
// Bit7:Current GPIO0 direction, 0:Input; 1:Output
// Bit6:Current GPIO0 level, 0:Low level;1:High level
// Bit5:Whether the current GPIO0 is set to interrupt; 0:Query mode; 1:Interrupt mode
// Bit4-3:Set the GPIO0 interrupt mode, 00:Falling edge trigger; 01:Rising edge trigger; 10:Double edge trigger;11: reserved;
// Bit2-0:reserved;

// Set GPIO interrupt service routine
BOOL WINAPI CH347SetIntRoutine(ULONG iIndex,                     // Specify the device serial number
                               UCHAR Int0PinN,                   // INT0 GPIO pin number greater than 7: disable this interrupt source; 0-7 corresponds to GPIO0-7
                               UCHAR Int0TripMode,               // INT0 type: 00:Falling edge trigger; 01:Rising edge trigger; 02:Double edge trigger; 03:reserve;
                               UCHAR Int1PinN,                   // INT1 GPIO pin number. If it is greater than 7, disable this interrupt source; 0-7 corresponds to GPIO0-7
                               UCHAR Int1TripMode,               // INT1 type: 00:Falling edge trigger; 01:Rising edge trigger; 02:Double edge trigger; 03:reserve;
                               mPCH347_INT_ROUTINE iIntRoutine); // Specify the interrupt service routine, if it is NULL, the interrupt service is canceled, otherwise, the program is called when interrupted.

// Read interrupt data
BOOL WINAPI CH347ReadInter(ULONG iIndex,    // Specify the device serial number
                           PUCHAR iStatus); // Point to the 8-byte unit, used to save read GPIO pin status data, refer to the following bit description

// Abandon interrupt data read operation
BOOL WINAPI CH347AbortInter(ULONG iIndex); // Specify the device serial number

// Enter IAP firmware upgrade mode
BOOL WINAPI CH347StartIapFwUpate(ULONG iIndex,
                                 ULONG FwSize); // Firmware length

/**************HID/VCP Serial Port*********************/
// Open serial port
HANDLE WINAPI CH347Uart_Open(ULONG iIndex);

// Close serial port
BOOL WINAPI CH347Uart_Close(ULONG iIndex);

// Set device event notification program
BOOL WINAPI CH347Uart_SetDeviceNotify(
    ULONG iIndex,                           // Specify the device serial number, 0 corresponds to the first device
    PCHAR iDeviceID,                        // Optional parameter, points to a string, specify the monitored device ID, end with \0
    mPCH347_NOTIFY_ROUTINE iNotifyRoutine); // Specifies device event callback program; if it is NULL then cancel event notification, otherwise the program is called when an event is detected.

// Obtain UART hardware configuration
BOOL WINAPI CH347Uart_GetCfg(ULONG iIndex,        // Specify the device serial number
                             PULONG BaudRate,     // Baud rate
                             PUCHAR ByteSize,     // Data bits (5,6,7,8,16)
                             PUCHAR Parity,       // Parity bits(0:None; 1:Odd; 2:Even; 3:Mark; 4:Space)
                             PUCHAR StopBits,     // Stop bits (0: 1 stop bits; 1: 1.5 stop bit; 2: 2 stop bit);
                             PUCHAR ByteTimeout); // Byte timeout

// Set UART configuration
BOOL WINAPI CH347Uart_Init(ULONG iIndex,       // Specify the device serial number
                           DWORD BaudRate,     // Baud rate
                           UCHAR ByteSize,     // Data bits (5,6,7,8,16)
                           UCHAR Parity,       // Parity bits (0:None; 1:Odd; 2:Even; 3:Mark; 4:Space)
                           UCHAR StopBits,     // Stop bits  (0: 1 Stop bit; 1: 1.5 stop bit; 2: 2 stop bit);
                           UCHAR ByteTimeout); // Byte timeout, in unit of 100uS

// Set USB data read/write timeout
BOOL WINAPI CH347Uart_SetTimeout(ULONG iIndex,        // Specify the device serial number
                                 ULONG iWriteTimeout, // Specify the timeout for USB to write data blocks, in mS,0xFFFFFFFF specifies no timeout (default)
                                 ULONG iReadTimeout); // Specify the timeout for USB to read data blocks, in mS,0xFFFFFFFF specifies no timeout (default)

// Read data block
BOOL WINAPI CH347Uart_Read(ULONG iIndex,     // Specify the device serial number
                           PVOID oBuffer,    // Points to a buffer large enough to place the read data
                           PULONG ioLength); // Refers to the length unit, the input is the length to be read, the return is the actual length to be read

// Write data blocks
BOOL WINAPI CH347Uart_Write(ULONG iIndex,     // Specify the device serial number
                            PVOID iBuffer,    // Points to a buffer to place data ready to be written out
                            PULONG ioLength); // Point to the length unit, the input is the intended length, the return is the actual length

// Query how many bytes are unfetched in read buffer
BOOL WINAPI CH347Uart_QueryBufUpload(ULONG iIndex, // Specify the device serial number
                                     LONGLONG *RemainBytes); // Read buffer unfetched bytes

// Obtain device information
BOOL WINAPI CH347Uart_GetDeviceInfor(ULONG iIndex, mDeviceInforS *DevInformation);

// Set USB data read/write timeout
BOOL WINAPI CH347Uart_SetTimeout(ULONG iIndex,        // Specify device serial number
                                 ULONG iWriteTimeout, // Specify timeout for USB to write data block, in mS, 0xFFFFFFFF specifies no timeout (default)
                                 ULONG iReadTimeout); // Specify timeout for USB to read data block, in mS, 0xFFFFFFFF specifies no timeout (default)
/********I2C***********/
// I2C settings
BOOL WINAPI CH347I2C_Set(ULONG iIndex, // Specify device serial number
                         ULONG iMode); // Specify mode, see next line
// bit1 - bit 0: I2C interface speed/SCL frequency, 00=low speed/20KHz, 01=standard/100KHz(default), 10= fast/400KHz, 11= high speed/750KHz
// Others are reserved, must be 0

// Set I2C clock stretch
BOOL WINAPI CH347I2C_SetStretch(ULONG iIndex,  // Specify device serial number
                                BOOL iEnable); // I2C Clock Stretch enable, 1:enable,0:disable

// Set hardware asynchronous delay, returns shortly after being called, and then delays for specified milliseconds before the next stream operation.
BOOL WINAPI CH347I2C_SetDelaymS(ULONG iIndex,  // Specify device serial number
                                ULONG iDelay); // Specify the delay in milliseconds

// Process I2C data stream, 2-wire interface, clock wire is SCL pin, data wire is SDA pin
BOOL WINAPI CH347StreamI2C(ULONG iIndex,       // Specify device serial number
                           ULONG iWriteLength, // Number of data bytes to be written
                           PVOID iWriteBuffer, // Points to a buffer to place data ready to be written out, first byte is usually the I2C device address and read/write direction bit
                           ULONG iReadLength,  // Number of bytes of data to be read
                           PVOID oReadBuffer); // Points to a buffer, returned data is the read-in data

// Process I2C data stream, 2-wire interface, clock wire is SCL pin, data wire is SDA pin (standard bidirectional I/O), speed about 56K bytes, and return the number of ACKs obtained by the host side
BOOL WINAPI CH347StreamI2C_RetACK(ULONG iIndex,       // Specify device serial number
                                  ULONG iWriteLength, // Number of data bytes to be written
                                  PVOID iWriteBuffer, // Points to a buffer to place data ready to be written out, first byte is usually the I2C device address and read/write direction bit
                                  ULONG iReadLength,  // Number of bytes of data to be read
                                  PVOID oReadBuffer,  // Points to a buffer, returned data is the read-in data
                                  PULONG rAckCount);  // Points to the ACK value returned by read/write

#ifndef _CH341_DLL_H
typedef enum _EEPROM_TYPE { // EEPROM type
    ID_24C01,
    ID_24C02,
    ID_24C04,
    ID_24C08,
    ID_24C16,
    ID_24C32,
    ID_24C64,
    ID_24C128,
    ID_24C256,
    ID_24C512,
    ID_24C1024,
    ID_24C2048,
    ID_24C4096
} EEPROM_TYPE;
#endif

// Read data blocks from EEPROM, speed about 56KB
BOOL WINAPI CH347ReadEEPROM(ULONG iIndex,          // Specify device serial number
                            EEPROM_TYPE iEepromID, // Specify EEPROM model
                            ULONG iAddr,           // Specify data unit address
                            ULONG iLength,         // Number of data bytes to be read
                            PUCHAR oBuffer);       // Points to a buffer, returned data is the read-in data

// Write data block to the EEPROM
BOOL WINAPI CH347WriteEEPROM(ULONG iIndex,          // Specify device serial number
                             EEPROM_TYPE iEepromID, // Specify EEPROM model
                             ULONG iAddr,           // Specify data unit address
                             ULONG iLength,         // Number of data bytes to be written out
                             PUCHAR iBuffer);       // Points to a buffer to place data ready to be written out

#ifdef __cplusplus
}
#endif

#endif // _CH347_DLL_H
