/*****************************************************************************
**                      Copyright  (C)  WCH  2001-2023                      **
**                      Web:  http://wch.cn                                 **
******************************************************************************/
// USB总线接口芯片CH341/7并口应用层接口库,CH347基于480Mbps高速USB总线扩展UART/SPI/I2C/JTAG/SWD
// CH347-DLL  V1.2
// 运行环境: Windows 98/ME, Windows 2000/XP, WIN7/8/10/11,and later.
// support USB chip: CH341, CH341A,CH347
// USB => Parallel, I2C, SPI, JTAG, SWD, UART ...
//Notes:
//Copyright (C) 2023 Nanjing Qinheng Microelectronics Co., Ltd.


//
#ifndef		_CH347_DLL_H
#define		_CH347_DLL_H

#ifdef __cplusplus
extern "C" {
#endif

#ifdef _WIN64
#define		mOFFSET( s, m )			( (ULONG_PTR) & ( ( ( s * ) 0 ) -> m ) )	// 定义获取结构成员相对偏移地址的宏
#else
#define		mOFFSET( s, m )			( (ULONG) & ( ( ( s * ) 0 ) -> m ) )	// 定义获取结构成员相对偏移地址的宏
#endif

#ifndef		max
#define		max( a, b )				( ( ( a ) > ( b ) ) ? ( a ) : ( b ) )	// 较大值
#endif

#ifndef		min
#define		min( a, b )				( ( ( a ) < ( b ) ) ? ( a ) : ( b ) )	// 较小值
#endif

#ifdef		ExAllocatePool
#undef		ExAllocatePool						// 删除带TAG的内存分配
#endif

#ifndef		NTSTATUS
typedef		LONG	NTSTATUS;					// 返回状态
#endif

//与CH31DLL合用CH341WDM驱动
#ifndef _CH341_DLL_H
typedef	struct	_USB_SETUP_PKT {				// USB控制传输的建立阶段的数据请求包结构
	UCHAR			mUspReqType;				// 00H 请求类型
	UCHAR			mUspRequest;				// 01H 请求代码
	union	{
		struct	{
			UCHAR	mUspValueLow;				// 02H 值参数低字节
			UCHAR	mUspValueHigh;				// 03H 值参数高字节
		};
		USHORT		mUspValue;					// 02H-03H 值参数
	};
	union	{
		struct	{
			UCHAR	mUspIndexLow;				// 04H 索引参数低字节
			UCHAR	mUspIndexHigh;				// 05H 索引参数高字节
		};
		USHORT		mUspIndex;					// 04H-05H 索引参数
	};
	USHORT			mLength;					// 06H-07H 数据阶段的数据长度
} mUSB_SETUP_PKT, *mPUSB_SETUP_PKT;


typedef	struct	_WIN32_COMMAND {				// 定义WIN32命令接口结构
	union	{
		ULONG		mFunction;					// 输入时指定功能代码或者管道号
		NTSTATUS	mStatus;					// 输出时返回操作状态
	};
	ULONG			mLength;					// 存取长度,返回后续数据的长度
	union	{
		mUSB_SETUP_PKT	mSetupPkt;				// USB控制传输的建立阶段的数据请求
		UCHAR			mBuffer[ 512];      	// 数据缓冲区,长度为0至255B
	};
} mWIN32_COMMAND, *mPWIN32_COMMAND;
// WIN32应用层接口命令
#define		IOCTL_CH341_COMMAND		( FILE_DEVICE_UNKNOWN << 16 | FILE_ANY_ACCESS << 14 | 0x0f34 << 2 | METHOD_BUFFERED )	// 专用接口

#define		mWIN32_COMMAND_HEAD		mOFFSET( mWIN32_COMMAND, mBuffer )	// WIN32命令接口的头长度

#define		mCH341_MAX_NUMBER		32			// 最多同时连接的CH341/7设备数量

#define		mMAX_BUFFER_LENGTH		0x1000		// 数据缓冲区最大长度4096

#define		mMAX_COMMAND_LENGTH		( mWIN32_COMMAND_HEAD + mMAX_BUFFER_LENGTH )	// 最大数据长度加上命令结构头的长度

#define		mDEFAULT_BUFFER_LEN		0x0400		// 数据缓冲区默认长度1024

#define		mDEFAULT_COMMAND_LEN	( mWIN32_COMMAND_HEAD + mDEFAULT_BUFFER_LEN )	// 默认数据长度加上命令结构头的长度

// CH341端点地址
#define		mCH347_ENDP_DATA_UP		0x86		// CH347的数据块上传端点的地址
#define		mCH347_ENDP_DATA_DOWN	0x06		// CH347的数据块下传端点的地址

// 设备层接口提供的管道操作命令
#define		mPipeDeviceCtrl			0x00000004	// CH347的综合控制管道
#define		mPipeDataUp				0x00000006	// CH347的数据块上传管道
#define		mPipeDataDown			0x00000007	// CH347的数据块下传管道

// 应用层接口的功能代码
#define		mFuncNoOperation		0x00000000	// 无操作
#define		mFuncGetVersion			0x00000001	// 获取驱动程序版本号
#define		mFuncGetConfig			0x00000002	// 获取USB设备配置描述符
#define		mFuncSetTimeout			0x00000009	// 设置USB通讯超时
#define		mFuncSetExclusive		0x0000000b	// 设置独占使用
#define		mFuncResetDevice		0x0000000c	// 复位USB设备
#define		mFuncResetPipe			0x0000000d	// 复位USB管道
#define		mFuncAbortPipe			0x0000000e	// 取消USB管道的数据请求
#define		mFuncBufferMode			0x00000020	// 设定缓冲上传模式及查询缓冲区中的数据长度
#define		mFuncBufferModeDn		0x00000021	// 设定缓冲下传模式及查询缓冲区中的数据长度
#define		mFuncGetVersionEx		0x00000022	// 获取驱动程序版本号及芯片型号
// USB设备标准请求代码
#define		mUSB_CLR_FEATURE		0x01
#define		mUSB_SET_FEATURE		0x03
#define		mUSB_GET_STATUS			0x00
#define		mUSB_SET_ADDRESS		0x05
#define		mUSB_GET_DESCR			0x06
#define		mUSB_SET_DESCR			0x07
#define		mUSB_GET_CONFIG			0x08
#define		mUSB_SET_CONFIG			0x09
#define		mUSB_GET_INTERF			0x0a
#define		mUSB_SET_INTERF			0x0b
#define		mUSB_SYNC_FRAME			0x0c

// CH341控制传输的厂商专用请求类型
#define		mCH341_VENDOR_READ		0xC0		// 通过控制传输实现的CH341厂商专用读操作
#define		mCH341_VENDOR_WRITE		0x40		// 通过控制传输实现的CH341厂商专用写操作

#define		mCH341A_CMD_I2C_STREAM	0xAA		// I2C接口的命令包,从次字节开始为I2C命令流
#define		mCH341A_CMD_UIO_STREAM	0xAB		// UIO接口的命令包,从次字节开始为命令流
#define		mCH341A_CMD_PIO_STREAM	0xAE		// PIO接口的命令包,从次字节开始为数据流
// CH341A控制传输的厂商专用请求代码
#define		mCH341A_BUF_CLEAR		0xB2		// 清除未完成的数据
#define		mCH341A_I2C_CMD_X		0x54		// 发出I2C接口的命令,立即执行
#define		mCH341A_DELAY_MS		0x5E		// 以亳秒为单位延时指定时间
#define		mCH341A_GET_VER			0x5F		// 获取芯片版本

#define		mCH341A_CMD_I2C_STM_STA	0x74		// I2C接口的命令流:产生起始位
#define		mCH341A_CMD_I2C_STM_STO	0x75		// I2C接口的命令流:产生停止位
#define		mCH341A_CMD_I2C_STM_OUT	0x80		// I2C接口的命令流:输出数据,位5-位0为长度,后续字节为数据,0长度则只发送一个字节并返回应答
#define		mCH341A_CMD_I2C_STM_IN	0xC0		// I2C接口的命令流:输入数据,位5-位0为长度,0长度则只接收一个字节并发送无应答
#define		mCH341A_CMD_I2C_STM_MAX	( min( 0x3F, mCH341_PACKET_LENGTH ) )	// I2C接口的命令流单个命令输入输出数据的最大长度
#define		mCH341A_CMD_I2C_STM_SET	0x60		// I2C接口的命令流:设置参数,位2=SPI的I/O数(0=单入单出,1=双入双出),位1位0=I2C速度(00=低速,01=标准,10=快速,11=高速)
#define		mCH341A_CMD_I2C_STM_US	0x40		// I2C接口的命令流:以微秒为单位延时,位3-位0为延时值
#define		mCH341A_CMD_I2C_STM_MS	0x50		// I2C接口的命令流:以亳秒为单位延时,位3-位0为延时值
#define		mCH341A_CMD_I2C_STM_DLY	0x0F		// I2C接口的命令流单个命令延时的最大值
#define		mCH341A_CMD_I2C_STM_END	0x00		// I2C接口的命令流:命令包提前结束

#define		mCH341A_CMD_UIO_STM_IN	0x00		// UIO接口的命令流:输入数据D7-D0
#define		mCH341A_CMD_UIO_STM_DIR	0x40		// UIO接口的命令流:设定I/O方向D5-D0,位5-位0为方向数据
#define		mCH341A_CMD_UIO_STM_OUT	0x80		// UIO接口的命令流:输出数据D5-D0,位5-位0为数据
#define		mCH341A_CMD_UIO_STM_US	0xC0		// UIO接口的命令流:以微秒为单位延时,位5-位0为延时值
#define		mCH341A_CMD_UIO_STM_END	0x20		// UIO接口的命令流:命令包提前结束

#define		MAX_DEVICE_PATH_SIZE	128			// 设备名称的最大字符数
#define		MAX_DEVICE_ID_SIZE		64			// 设备ID的最大字符数
#endif _CH341_DLL_H

//驱动接口
#define CH347_USB_VENDOR   0
#define CH347_USB_HID      2
#define CH347_USB_VCP      3

//CH347_USB_VENDOR支持CH341/7
#define CHIP_TYPE_CH341    0
#define CHIP_TYPE_CH347    1
#define CHIP_TYPE_CH347F   2
#define CHIP_TYPE_CH347T   CHIP_TYPE_CH347

//芯片功能接口类型
#define CH347_FUNC_UART          0
#define CH347_FUNC_SPI_IIC       1
#define CH347_FUNC_JTAG_IIC      2
#define CH347_FUNC_JTAG_IIC_SPI  3 //CH347F

#define DEFAULT_READ_TIMEOUT  500  //默认读超时毫秒数
#define DEFAULT_WRITE_TIMEOUT 500  //默认写超时毫秒数

#define		mCH347_PACKET_LENGTH	512		// CH347支持的数据包的长度

#pragma pack(1) 

//SPI控制器配置
typedef struct _SPI_CONFIG{
	UCHAR           iMode;                 // 0-3:SPI Mode0/1/2/3
	UCHAR           iClock;                // 0=60MHz, 1=30MHz, 2=15MHz, 3=7.5MHz, 4=3.75MHz, 5=1.875MHz, 6=937.5KHz，7=468.75KHz
	UCHAR			iByteOrder;            // 0=低位在前(LSB), 1=高位在前(MSB)
	USHORT          iSpiWriteReadInterval; // SPI接口常规读取写入数据命令，单位为uS
	UCHAR           iSpiOutDefaultData;    // SPI读数据时默认输出数据
	ULONG			iChipSelect;           // 片选控制, 位7为0则忽略片选控制, 位7为1则参数有效: 位1位0为00/01分别选择CS1/CS2引脚作为低电平有效片选
	UCHAR           CS1Polarity;           // 位0：片选CS1极性控制：0：低电平有效；1：高电平有效；
	UCHAR           CS2Polarity;           // 位0：片选CS2极性控制：0：低电平有效；1：高电平有效；
	USHORT          iIsAutoDeativeCS;      // 操作完成后是否自动撤消片选
	USHORT          iActiveDelay;          // 设置片选后执行读写操作的延时时间,单位us
	ULONG           iDelayDeactive;        // 撤消片选后执行读写操作的延时时间,单位us
}mSpiCfgS,*mPSpiCfgS;

//设备信息
typedef struct _DEV_INFOR{
	UCHAR    iIndex;                 // 当前打开序号
	UCHAR    DevicePath[MAX_PATH];   // 设备链接名,用于CreateFile
	UCHAR    UsbClass;               // 驱动类别 0:CH347_USB_CH341, 2:CH347_USB_HID,3:CH347_USB_VCP
	UCHAR    FuncType;               // 功能类别 0:CH347_FUNC_UART,1:CH347_FUNC_SPI_I2C,2:CH347_FUNC_JTAG_I2C
	CHAR     DeviceID[64];           // USB\VID_xxxx&PID_xxxx
	UCHAR    ChipMode;               // 芯片工作模式,0:Mode0(UART0/1); 1:Mode1(Uart1+SPI+I2C); 2:Mode2(HID Uart1+SPI+I2C) 3:Mode3(Uart1+Jtag+IIC) 4:CH347F(Uart*2+Jtag/SPI/IIC)
	HANDLE   DevHandle;              // 设备句柄
	USHORT   BulkOutEndpMaxSize;     // 批量上传端点大小
	USHORT   BulkInEndpMaxSize;      // 批量下传端点大小
	UCHAR    UsbSpeedType;           // USB速度类型，0:FS,1:HS,2:SS
	UCHAR    CH347IfNum;             // USB接口号: CH347T: IF0:UART;   IF1:SPI/IIC/JTAG/GPIO
									 //            CH347F: IF0:UART0;  IF1:UART1; IF 2:SPI/IIC/JTAG/GPIO
	UCHAR    DataUpEndp;             // 批量上传端点地址
	UCHAR    DataDnEndp;             // 批量下传端点地址
	CHAR     ProductString[64];      // USB产品字符串
	CHAR     ManufacturerString[64]; // USB厂商字符串
	ULONG    WriteTimeout;           // USB写超时
	ULONG    ReadTimeout;            // USB读超时
	CHAR     FuncDescStr[64];        // 接口功能描述符
	UCHAR    FirewareVer;            // 固件版本,十六进制值
}mDeviceInforS,*mPDeviceInforS;

#pragma pack() 

// CH347各模式公用函数,支持CH347所有模式下的打开、关闭、USB读、USB写，包含HID
//打开USB设备
HANDLE WINAPI CH347OpenDevice(ULONG DevI);

//关闭USB设备
BOOL WINAPI CH347CloseDevice(ULONG iIndex);

//获取设备信息
BOOL WINAPI CH347GetDeviceInfor(ULONG iIndex,mDeviceInforS *DevInformation);

// 获取CH347芯片类型:CHIP_TYPE_CH347T/CHIP_TYPE_CH347F
UCHAR	WINAPI	CH347GetChipType(ULONG			iIndex );  // 指定设备序号

// 获取驱动版本、库版本、设备版本、芯片类型(CH341(FS)/CH347HS)
BOOL	WINAPI	CH347GetVersion(ULONG 			 iIndex, 
							    PUCHAR           iDriverVer,
								PUCHAR           iDLLVer,
							    PUCHAR           ibcdDevice,
							    PUCHAR           iChipType);  //CHIP_TYPE_CH341/7

typedef		VOID	( CALLBACK	* mPCH347_NOTIFY_ROUTINE ) (								 // 设备插拔通知事件回调程序
															ULONG			iEventStatus );  // 设备插拔事件和当前状态(在下行定义): 0=设备拔出事件, 3=设备插入事件

#define		CH347_DEVICE_ARRIVAL		3		// 设备插入事件,已经插入
#define		CH347_DEVICE_REMOVE_PEND	1		// 设备将要拔出
#define		CH347_DEVICE_REMOVE			0		// 设备拔出事件,已经拔出

// 设定设备事件通知程序
BOOL	WINAPI	CH347SetDeviceNotify(ULONG					iIndex,				// 指定设备序号,0对应第一个设备
									 PCHAR					iDeviceID,			// 可选参数,指向字符串,指定被监控的设备的ID,字符串以\0终止
									 mPCH347_NOTIFY_ROUTINE	iNotifyRoutine );   // 指定设备事件回调程序,为NULL则取消事件通知,否则在检测到事件时调用该程序

// 读取USB数据块
BOOL	WINAPI	CH347ReadData( ULONG			iIndex,          // 指定设备序号
							   PVOID			oBuffer,         // 指向一个足够大的缓冲区,用于保存读取的数据
							   PULONG			ioLength );		 // 指向长度单元,输入时为准备读取的长度,返回后为实际读取的长度

// 写取USB数据块
BOOL	WINAPI	CH347WriteData(ULONG			iIndex,      // 指定设备序号
							   PVOID			iBuffer,     // 指向一个缓冲区,放置准备写出的数据
							   PULONG			ioLength );  // 指向长度单元,输入时为准备写出的长度,返回后为实际写出的长度

// 设置USB数据读写的超时
BOOL	WINAPI	CH347SetTimeout(ULONG			iIndex,         // 指定设备序号
							    ULONG			iWriteTimeout,  // 指定USB写出数据块的超时时间,以毫秒mS为单位,0xFFFFFFFF指定不超时(默认值)
								ULONG			iReadTimeout ); // 指定USB读取数据块的超时时间,以毫秒mS为单位,0xFFFFFFFF指定不超时(默认值)

/***************SPI********************/
// SPI控制器初始化
BOOL	WINAPI	CH347SPI_Init(ULONG iIndex,mSpiCfgS *SpiCfg);

//CH347F设置SPI时钟频率。iSpiSpeedHz= 0=60MHz,  1=30MHz,  2=15MHz,  3=7.5MHz,  4=3.75MHz,  5=1.875MHz,  6=937.5KHz， 7=468.75KHz
BOOL WINAPI CH347SPI_SetFrequency(ULONG iIndex, ULONG iSpiSpeedHz);

//CH347F设置SPI支持数据位数.
BOOL WINAPI CH347SPI_SetDataBits(ULONG iIndex,
								 UCHAR iDataBits); //iDataBits= 0:8bit, 1:16bit

//获取SPI控制器配置信息
BOOL    WINAPI  CH347SPI_GetCfg(ULONG iIndex,mSpiCfgS *SpiCfg);

//设置片选状态,使用前需先调用CH347SPI_Init对CS进行设置
BOOL	WINAPI	CH347SPI_ChangeCS(ULONG			iIndex,         // 指定设备序号	
								  UCHAR         iStatus);       // 0=撤消片选,1=设置片选

//设置SPI片选
BOOL	WINAPI	CH347SPI_SetChipSelect(ULONG			iIndex,            // 指定设备序号
									   USHORT           iEnableSelect,     // 低八位为CS1，高八位为CS2; 字节值为1=设置CS,为0=忽略此CS设置
									   USHORT           iChipSelect,       // 低八位为CS1，高八位为CS2;片选输出,0=撤消片选,1=设置片选
									   ULONG            iIsAutoDeativeCS,  // 低16位为CS1，高16位为CS2;操作完成后是否自动撤消片选
									   ULONG            iActiveDelay,      // 低16位为CS1，高16位为CS2;设置片选后执行读写操作的延时时间,单位us
									   ULONG            iDelayDeactive);   // 低16位为CS1，高16位为CS2;撤消片选后执行读写操作的延时时间,单位us

//SPI4写数据
BOOL	WINAPI	CH347SPI_Write(ULONG			iIndex,          // 指定设备序号	
							   ULONG			iChipSelect,     // 片选控制, 位7为0则忽略片选控制, 位7为1进行片选操作
							   ULONG			iLength,         // 准备传输的数据字节数	
							   ULONG			iWriteStep,      // 准备读取的单个块的长度
							   PVOID			ioBuffer);       // 指向一个缓冲区,放置准备从MOSI写出的数据

//SPI4读数据.无需先写数据，效率较CH347SPI_WriteRead高很多
BOOL	WINAPI	CH347SPI_Read(ULONG			iIndex,           // 指定设备序号	
							  ULONG			iChipSelect,      // 片选控制, 位7为0则忽略片选控制, 位7为1进行片选操作
							  ULONG         oLength,          // 准备发出的字节数
							  PULONG		iLength,          // 准备读入的数据字节数	
							  PVOID			ioBuffer);        // 指向一个缓冲区,放置准备从DOUT写出的数据,返回后是从DIN读入的数据

// 处理SPI数据流,4线接口
BOOL	WINAPI	CH347SPI_WriteRead(ULONG			iIndex,       // 指定设备序号
								   ULONG			iChipSelect,  // 片选控制, 位7为0则忽略片选控制, 位7为1则操作片选
								   ULONG			iLength,      // 准备传输的数据字节数
								   PVOID			ioBuffer );   // 指向一个缓冲区,放置准备从DOUT写出的数据,返回后是从DIN读入的数据

// 处理SPI数据流,4线接口
BOOL	WINAPI	CH347StreamSPI4(ULONG			iIndex,       // 指定设备序号
								ULONG			iChipSelect,  // 片选控制, 位7为0则忽略片选控制, 位7为1则参数有效
								ULONG			iLength,      // 准备传输的数据字节数
								PVOID			ioBuffer );   // 指向一个缓冲区,放置准备从DOUT写出的数据,返回后是从DIN读入的数据

/***************JTAG********************/
//JTAG接口初始化，设置模式及速度
BOOL	WINAPI	CH347Jtag_INIT(ULONG iIndex,
							   UCHAR iClockRate);   //通信速度；有效值为0-5，值越大通信速度越快

//获取Jtag速度设置
BOOL    WINAPI  CH347Jtag_GetCfg(ULONG iIndex,         // 指定设备序号
							     UCHAR *ClockRate);    //通信速度；有效值为0-5，值越大通信速度越快


//改变TMS的值来进行状态切换
BOOL	WINAPI CH347Jtag_TmsChange(ULONG  iIndex,   // 设备序号
								   PUCHAR tmsValue, // 进行切换的TMS位值,以字节为单位
								   ULONG  Step,     // tmsValue内存储的TMS有效位数
								   ULONG  Skip);    // 有效起始位

//在shift-dr/ir状态进行读写，执行完切至Exit DR/IR
//状态机:Shift-DR/IR.RW.->Exit DR/IR
BOOL   WINAPI  CH347Jtag_IoScan(ULONG   iIndex,    
							    PUCHAR  DataBits,   //需要进行传输的数据位
							    ULONG   DataBitsNb, //需要传输数据的位数
							    BOOL    IsRead);    //是否需要读取数据

//切至shift-dr/ir状态进行读写,执行完成后,如是最后一包，则切至Exit DR/IR;如果不是,则停在Shift-DR/IR
//状态机:Shift-DR/IR.RW..->[Exit DR/IR]
BOOL   WINAPI  CH347Jtag_IoScanT(ULONG  iIndex,       // 设备序号
								 PUCHAR DataBits,     // 需要进行传输的数据位
								 ULONG  DataBitsNb,   // 需要传输数据的位数
								 BOOL   IsRead,       // 是否需要读取数据
								 BOOL   IsLastPkt);   // 是否为最后一包

//CH347 复位Tap状态函数.连续六个以上TCK且TMS为高将可将状态机置为Test-Logic Reset状态
ULONG	WINAPI  CH347Jtag_Reset(ULONG iIndex);

//CH347 操作TRST完成硬件复位
BOOL WINAPI CH347Jtag_ResetTrst(ULONG iIndex, BOOL TRSTLevel);

//位带方式JTAG IR/DR数据读写.适用于少量数据的读写。如指令操作、状态机切换等控制类传输。如批量数据传输，建议使用CH347Jtag_WriteRead_Fast
//命令包以4096字节为单位批量读写
//状态机:Run-Test->Shift-IR/DR..->Exit IR/DR -> Run-Test
BOOL	WINAPI	CH347Jtag_WriteRead(ULONG			iIndex,           // 指定设备序号
									BOOL            IsDR,             // =TRUE: DR数据读写,=FALSE:IR数据读写
									ULONG			iWriteBitLength,  // 写长度,准备写出的长度
									PVOID			iWriteBitBuffer,  // 指向一个缓冲区,放置准备写出的数据	
									PULONG			oReadBitLength,   // 指向长度单元,返回后为实际读取的长度
									PVOID			oReadBitBuffer ); // 指向一个足够大的缓冲区,用于保存读取的数据

//JTAG IR/DR数据批量读写,用于多字节连续读写。如JTAG固件下载操作。因硬件有4K缓冲区，如先写后读，长度不超过4096字节。缓冲区大小可自行调整
//状态机:Run-Test->Shift-IR/DR..->Exit IR/DR -> Run-Test
BOOL	WINAPI	CH347Jtag_WriteRead_Fast(ULONG		iIndex,            // 指定设备序号
										 BOOL       IsDR,              // =TRUE: DR数据读写,=FALSE:IR数据读写
										 ULONG		iWriteBitLength,   // 写长度,准备写出的长度
										 PVOID		iWriteBitBuffer,   // 指向一个缓冲区,放置准备写出的数据	
										 PULONG		oReadBitLength,    // 指向长度单元,返回后为实际读取的长度
										 PVOID		oReadBitBuffer );  // 指向一个足够大的缓冲区,用于保存读取的数据

//位带方式JTAG IR/DR数据读写.适用于少量数据的读写。如指令操作、状态机切换等控制类传输。如批量数据传输，建议使用CH347Jtag_WriteRead_Fast
//命令包以4096字节为单位批量读写
//状态机:Run-Test-> Shift-IR/DR..->Exit IR/DR -> Run-Test
BOOL	WINAPI	CH347Jtag_WriteReadEx(ULONG			iIndex,           // 指定设备序号
									  BOOL			IsInDrOrIr,	      // =TRUE: 在SHIFT-DR/IR状态进行数据交互  ==FALSE: Run-Test->Shift-IR/DR.进行数据交互.->Exit IR/DR -> Run-Test
									  BOOL          IsDR,             // =TRUE: DR数据读写,=FALSE:IR数据读写
									  ULONG			iWriteBitLength,  // 写长度,准备写出的长度
									  PVOID			iWriteBitBuffer,  // 指向一个缓冲区,放置准备写出的数据	
									  PULONG		oReadBitLength,   // 指向长度单元,返回后为实际读取的长度
									  PVOID			oReadBitBuffer ); // 指向一个足够大的缓冲区,用于保存读取的数据

//JTAG IR/DR数据批量读写,用于多字节连续读写。如JTAG固件下载操作。因硬件有4K缓冲区，如先写后读，长度不超过4096字节。缓冲区大小可自行调整
//状态机:Run-Test->Shift-IR/DR..->Exit IR/DR -> Run-Test
BOOL	WINAPI	CH347Jtag_WriteRead_FastEx(ULONG		iIndex,            // 指定设备序号
										   BOOL		    IsInDrOrIr,	       // =TRUE: 在SHIFT-DR/IR状态进行数据交互  ==FALSE: Run-Test->Shift-IR/DR.进行数据交互.->Exit IR/DR -> Run-Test								
										   BOOL         IsDR,              // =TRUE: DR数据读写,=FALSE:IR数据读写
										   ULONG		iWriteBitLength,   // 写长度,准备写出的长度
										   PVOID		iWriteBitBuffer,   // 指向一个缓冲区,放置准备写出的数据	
										   PULONG		oReadBitLength,    // 指向长度单元,返回后为实际读取的长度
										   PVOID		oReadBitBuffer );  // 指向一个足够大的缓冲区,用于保存读取的数据

//切换JTAG状态机
BOOL WINAPI CH347Jtag_SwitchTapState(UCHAR TapState);

//JTAG DR写,以字节为单位,用于多字节连续读写。如JTAG固件下载操作。
//状态机:Run-Test->Shift-DR..->Exit DR -> Run-Test
BOOL	WINAPI	CH347Jtag_ByteWriteDR(ULONG			iIndex,        // 指定设备序号									
									  ULONG			iWriteLength,  // 写长度,准备写出的字节长度
									  PVOID			iWriteBuffer); // 指向一个缓冲区,放置准备写出的数据	

//JTAG DR读,以字节为单位,多字节连续读。
//状态机:Run-Test->Shift-DR..->Exit DR -> Run-Test
BOOL	WINAPI	CH347Jtag_ByteReadDR(ULONG			iIndex,        // 指定设备序号									
									 PULONG			oReadLength,   // 指向长度单元,返回后为实际读取的字节长度
									 PVOID			oReadBuffer ); // 指向一个足够大的缓冲区,用于保存读取的数据

//JTAG IR写,以字节为单位,多字节连续写。
//状态机:Run-Test->Shift-IR..->Exit IR -> Run-Test
BOOL	WINAPI	CH347Jtag_ByteWriteIR(ULONG			iIndex,        // 指定设备序号									
									  ULONG			iWriteLength,  // 写长度,准备写出的字节长度
									  PVOID			iWriteBuffer); // 指向一个缓冲区,放置准备写出的数据										

//JTAG IR读,以字节为单位,多字节连续读写。
//状态机:Run-Test->Shift-IR..->Exit IR -> Run-Test
BOOL	WINAPI	CH347Jtag_ByteReadIR(ULONG			iIndex,         // 指定设备序号									
									 PULONG			oReadLength,    // 指向长度单元,返回后为实际读取的字节长度
									 PVOID			oReadBuffer );  // 指向一个足够大的缓冲区,用于保存读取的数据

//位带方式JTAG DR数据写.适用于少量数据的读写。如指令操作、状态机切换等控制类传输。如批量数据传输，建议使用USB20Jtag_ByeWriteDR
//状态机:Run-Test->Shift-DR..->Exit DR -> Run-Test
BOOL	WINAPI	CH347Jtag_BitWriteDR(ULONG			iIndex,             // 指定设备序号									
									 ULONG    	    iWriteBitLength,    // 指向长度单元,返回后为实际读取的字节长度
									 PVOID			iWriteBitBuffer );  // 指向一个足够大的缓冲区,用于保存读取的数据

//位带方式JTAG IR数据写.适用于少量数据的读写。如指令操作、状态机切换等控制类传输。如批量数据传输，建议使用USB20Jtag_ByteWriteIR
//状态机:Run-Test->Shift-IR..->Exit IR -> Run-Test
BOOL	WINAPI	CH347Jtag_BitWriteIR(ULONG			iIndex,             // 指定设备序号									
									 ULONG    	    iWriteBitLength,    // 指向长度单元,返回后为实际读取的字节长度
									 PVOID			iWriteBitBuffer );  // 指向一个足够大的缓冲区,用于保存读取的数据

//位带方式JTAG IR数据读.适用于少量数据的读写。如指令操作、状态机切换等。如批量数据传输，建议使用USB20Jtag_ByteReadIR
//状态机:Run-Test->Shift-IR..->Exit IR -> Run-Test
BOOL	WINAPI	CH347Jtag_BitReadIR(ULONG			iIndex,				// 指定设备序号									
									PULONG    	oReadBitLength,			// 指向长度单元,返回后为实际读取的字节长度
									PVOID			oReadBitBuffer );	// 指向一个足够大的缓冲区,用于保存读取的数据

//位带方式JTAG DR数据读.适用于少量数据的读写。如批量和高速数据传输，建议使用USB20Jtag_ByteReadDR
//状态机:Run-Test->Shift-DR..->Exit DR -> Run-Test
BOOL	WINAPI	CH347Jtag_BitReadDR(ULONG			iIndex,				// 指定设备序号									
									PULONG    	    oReadBitLength,		// 指向长度单元,返回后为实际读取的字节长度
									PVOID			oReadBitBuffer );   // 指向一个足够大的缓冲区,用于保存读取的数据

/***************GPIO********************/
//获取CH347的GPIO方向和引脚电平值
BOOL WINAPI CH347GPIO_Get(ULONG iIndex,       // 指定设备序号
						  UCHAR *iDir,        // 引脚方向:GPIO0-7对应位0-7.0：输入；1：输出
						  UCHAR *iData);      // GPIO0电平:GPIO0-7对应位0-7,0：低电平；1：高电平)

//设置CH347的GPIO方向和引脚电平值 
BOOL WINAPI CH347GPIO_Set(ULONG iIndex,        // 指定设备序号
						  UCHAR iEnable,       // 数据有效标志:对应位0-7,对应GPIO0-7.
						  UCHAR iSetDirOut,    // 设置I/O方向,某位清0则对应引脚为输入,某位置1则对应引脚为输出.GPIO0-7对应位0-7.
						  UCHAR iSetDataOut);  // 输出数据,如果I/O方向为输出,那么某位清0时对应引脚输出低电平,某位置1时对应引脚输出高电平


typedef		VOID	( CALLBACK	* mPCH347_INT_ROUTINE ) (  // 中断服务程序
	                                                     PUCHAR			iStatus );  // 中断状态数据,参考下面的位说明
// 8个字节GPIO0-7引脚状态.每字节位定义如下:
// 位7：当前的GPIO0方向，0：输入；1：输出；
// 位6：当前的GPIO0电平，0：低电平；1：高电平；
// 位5：当前的GPIO0是否设置为中断，0：查询模式；1：中断模式；
// 位4-3：设置GPIO0的中断模式，00：下降沿触发；01：上升沿触发;10：双边沿触发；11: 保留;
// 位2-0：保留；

// 设定GPIO中断服务程序
BOOL	WINAPI	CH347SetIntRoutine(ULONG			iIndex,           // 指定设备序号
	                               UCHAR           Int0PinN,          // 中断0 GPIO引脚号,大于7:不启用此中断源; 为0-7对应gpio0-7
	                               UCHAR           Int0TripMode,      // 中断0类型: 00:下降沿触发; 01:上升沿触发; 02:双边沿触发; 03:保留;
	                               UCHAR           Int1PinN,          // 中断1 GPIO引脚号,大于7则不启用此中断源,为0-7对应gpio0-7
	                               UCHAR           Int1TripMode,      // 中断1类型: 00:下降沿触发; 01:上升沿触发; 02:双边沿触发; 03:保留;
	                               mPCH347_INT_ROUTINE	iIntRoutine );// 指定中断服务程序,为NULL则取消中断服务,否则在中断时调用该程序

// 读取中断数据
BOOL	WINAPI	CH347ReadInter(ULONG			iIndex,      // 指定设备序号
	                           PUCHAR			iStatus );   // 指向8字节单元,分别为GPIO0-7引脚状态,每个字节位说明参考中断服务程序iStatus位说明 

// 放弃中断数据读操作
BOOL	WINAPI	CH347AbortInter(ULONG			iIndex );  // 指定设备序号

//进入IAP固件升级模式
BOOL	WINAPI	CH347StartIapFwUpate(ULONG    iIndex,
									 ULONG	  FwSize); // 固件长度

/**************HID/VCP串口**********************/
//打开串口
HANDLE WINAPI CH347Uart_Open(ULONG iIndex);

//关闭串口
BOOL WINAPI CH347Uart_Close(ULONG iIndex);

BOOL	WINAPI	CH347Uart_SetDeviceNotify(												// 设定设备事件通知程序
										  ULONG					iIndex,					// 指定设备序号,0对应第一个设备
										  PCHAR					iDeviceID,				// 可选参数,指向字符串,指定被监控的设备的ID,字符串以\0终止
										  mPCH347_NOTIFY_ROUTINE	iNotifyRoutine );   // 指定设备事件回调程序,为NULL则取消事件通知,否则在检测到事件时调用该程序

//获取UART硬件配置
BOOL    WINAPI  CH347Uart_GetCfg(ULONG   iIndex,       // 指定设备序号
								 PULONG  BaudRate,     // 波特率
								 PUCHAR  ByteSize,     // 数据位数(5,6,7,8,16)
								 PUCHAR  Parity,       // 校验位(0：None; 1：Odd; 2：Even; 3：Mark; 4：Space)
								 PUCHAR  StopBits,     // 停止位数(0：1停止位; 1：1.5停止位; 2：2停止位)；
								 PUCHAR  ByteTimeout); // 字节超时

//设置UART配置								   
BOOL  WINAPI   CH347Uart_Init(ULONG  iIndex,      // 指定设备序号
							  DWORD  BaudRate,    // 波特率
							  UCHAR  ByteSize,    // 数据位数(5,6,7,8,16)
							  UCHAR  Parity,      // 校验位(0：None; 1：Odd; 2：Even; 3：Mark; 4：Space)
							  UCHAR  StopBits,    // 停止位数(0：1停止位; 1：1.5停止位; 2：2停止位)；
							  UCHAR  ByteTimeout);// 字节超时时间,单位100uS

// 设置USB数据读写的超时
BOOL	WINAPI	CH347Uart_SetTimeout(ULONG			iIndex,         // 指定设备序号
									 ULONG			iWriteTimeout,  // 指定USB写出数据块的超时时间,以毫秒mS为单位,0xFFFFFFFF指定不超时(默认值)
									 ULONG			iReadTimeout ); // 指定USB读取数据块的超时时间,以毫秒mS为单位,0xFFFFFFFF指定不超时(默认值)

// 读取数据块
BOOL  WINAPI   CH347Uart_Read(ULONG			    iIndex,    // 指定设备序号
								 PVOID			oBuffer,   // 指向一个足够大的缓冲区,用于保存读取的数据
								 PULONG			ioLength );// 指向长度单元,输入时为准备读取的长度,返回后为实际读取的长度
// 写出数据块
BOOL  WINAPI   CH347Uart_Write(ULONG			iIndex,    // 指定设备序号
								  PVOID			iBuffer,   // 指向一个缓冲区,放置准备写出的数据
								  PULONG		ioLength );// 指向长度单元,输入时为准备写出的长度,返回后为实际写出的长度

//查询读缓冲区有多少字节未取
BOOL WINAPI CH347Uart_QueryBufUpload(ULONG			iIndex,        // 指定设备序号
									 LONGLONG       *RemainBytes); // 读缓冲区未取字节数

//获取设备信息
BOOL WINAPI CH347Uart_GetDeviceInfor(ULONG iIndex,mDeviceInforS *DevInformation);

// 设置USB数据读写的超时
BOOL	WINAPI	CH347Uart_SetTimeout(ULONG			iIndex,         // 指定设备序号
									 ULONG			iWriteTimeout,  // 指定USB写出数据块的超时时间,以毫秒mS为单位,0xFFFFFFFF指定不超时(默认值)
									 ULONG			iReadTimeout ); // 指定USB读取数据块的超时时间,以毫秒mS为单位,0xFFFFFFFF指定不超时(默认值)

/********IIC***********/
// I2C设置
BOOL	WINAPI	CH347I2C_Set(ULONG			iIndex,   // 指定设备序号
							 ULONG			iMode );  // 指定模式,见下行
// 位1-位0: I2C接口速度/SCL频率, 00=低速/20KHz,01=标准/100KHz(默认值),10=快速/400KHz,11=高速/750KHz
// 其它保留,必须为0

//Set I2C Clock Stretch
BOOL	WINAPI	CH347I2C_SetStretch(ULONG iIndex, // 指定设备序号
									BOOL  iEnable); // I2C Clock Stretch enable, 1:enable,0:disable

// 设置硬件异步延时,调用后很快返回,而在下一个流操作之前延时指定毫秒数
BOOL	WINAPI	CH347I2C_SetDelaymS(ULONG			iIndex,       // 指定设备序号
									ULONG			iDelay ) ;    // 指定延时的毫秒数

 // 处理I2C数据流,2线接口,时钟线为SCL引脚,数据线为SDA引脚
BOOL	WINAPI	CH347StreamI2C( ULONG			iIndex,        // 指定设备序号
							    ULONG			iWriteLength,  // 准备写出的数据字节数
							    PVOID			iWriteBuffer,  // 指向一个缓冲区,放置准备写出的数据,首字节通常是I2C设备地址及读写方向位
							    ULONG			iReadLength,   // 准备读取的数据字节数
							    PVOID			oReadBuffer ); // 指向一个缓冲区,返回后是读入的数据

BOOL	WINAPI	CH347StreamI2C_RetACK(  // 处理I2C数据流,2线接口,时钟线为SCL引脚,数据线为SDA引脚(准双向I/O),速度约56K字节,并返回主机端获取到的ACK数量
									  ULONG			iIndex,  // 指定CH341设备序号
									  ULONG			iWriteLength,  // 准备写出的数据字节数
									  PVOID			iWriteBuffer,  // 指向一个缓冲区,放置准备写出的数据,首字节通常是I2C设备地址及读写方向位
									  ULONG			iReadLength,   // 准备读取的数据字节数
									  PVOID			oReadBuffer,   // 指向一个缓冲区,返回后是读入的数据
									  PULONG		rAckCount);     // 指向读写返回的ACK值

#ifndef _CH341_DLL_H
typedef	enum	_EEPROM_TYPE {// EEPROM型号
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

// 从EEPROM中读取数据块,速度约56K字节
BOOL	WINAPI	CH347ReadEEPROM(ULONG			iIndex,     // 指定设备序号
								EEPROM_TYPE		iEepromID,  // 指定EEPROM型号
								ULONG			iAddr,      // 指定数据单元的地址
								ULONG			iLength,    // 准备读取的数据字节数
								PUCHAR			oBuffer );  // 指向一个缓冲区,返回后是读入的数据
// 向EEPROM中写入数据块
BOOL	WINAPI	CH347WriteEEPROM(ULONG			iIndex,     // 指定设备序号
								 EEPROM_TYPE	iEepromID,  // 指定EEPROM型号
								 ULONG			iAddr,      // 指定数据单元的地址
								 ULONG			iLength,    // 准备写出的数据字节数
								 PUCHAR			iBuffer );  // 指向一个缓冲区,放置准备写出的数据

#ifdef __cplusplus
}
#endif

#endif		// _CH347_DLL_H
