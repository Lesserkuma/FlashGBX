import ctypes
from typing import List


class DeviceInfo(ctypes.Structure):
    MAX_PATH = 260
    _fields_ = [
        ("DeviceIndex", ctypes.c_ubyte),  # 当前打开序号
        ("DevicePath", ctypes.c_char * MAX_PATH),  # 设备路径
        (
            "UsbClass",
            ctypes.c_ubyte,
        ),  # USB设备类别: 0=CH341 Vendor; 1=CH347 Vendor; 2=HID
        ("FuncType", ctypes.c_ubyte),  # 设备功能类型: 0=UART1; 1=SPI+I2C; 2=JTAG+I2C
        ("DeviceID", ctypes.c_char * 64),  # USB设备ID: USB\VID_xxxx&PID_xxxx
        (
            "ChipMode",
            ctypes.c_ubyte,
        ),  # 芯片模式: 0=Mode0(UART*2); 1=Mode1(Uart1+SPI+I2C); 2=Mode2(HID Uart1+SPI+I2C); 3=Mode3(Uart1+Jtag+I2C)
        ("DevHandle", ctypes.c_void_p),  # 设备句柄
        ("BulkOutEndpMaxSize", ctypes.c_ushort),  # 上传端点大小
        ("BulkInEndpMaxSize", ctypes.c_ushort),  # 下传端点大小
        ("UsbSpeedType", ctypes.c_ubyte),  # USB速度类型: 0=FS; 1=HS; 2=SS
        ("CH347IfNum", ctypes.c_ubyte),  # USB接口号
        ("DataUpEndp", ctypes.c_ubyte),  # 端点地址
        ("DataDnEndp", ctypes.c_ubyte),  # 端点地址
        ("ProductString", ctypes.c_char * 64),  # USB产品字符串
        ("ManufacturerString", ctypes.c_char * 64),  # USB厂商字符串
        ("WriteTimeout", ctypes.c_ulong),  # USB写超时
        ("ReadTimeout", ctypes.c_ulong),  # USB读超时
        ("FuncDescStr", ctypes.c_char * 64),  # 接口功能描述符
        ("FirmwareVer", ctypes.c_ubyte),  # 固件版本
    ]


class SPIConfig(ctypes.Structure):
    _fields_ = [
        ("Mode", ctypes.c_ubyte),  # 0-3: SPI Mode0/1/2/3
        (
            "Clock",
            ctypes.c_ubyte,
        ),  # 0=60MHz, 1=30MHz, 2=15MHz, 3=7.5MHz, 4=3.75MHz, 5=1.875MHz, 6=937.5KHz, 7=468.75KHz
        ("ByteOrder", ctypes.c_ubyte),  # 0=LSB first(LSB), 1=MSB first(MSB)
        (
            "SPIWriteReadInterval",
            ctypes.c_ushort,
        ),  # Regular interval for SPI read/write commands, in microseconds
        (
            "SPIOutDefaultData",
            ctypes.c_ubyte,
        ),  # Default output data when reading from SPI
        (
            "ChipSelect",
            ctypes.c_ulong,
        ),  # Chip select control. Bit 7 as 0 ignores chip select control,
        # Bit 7 as 1 makes the parameters valid:
        # Bit 1 and Bit 0 as 00/01 selects CS1/CS2 pin as the active low chip select.
        (
            "CS1Polarity",
            ctypes.c_ubyte,
        ),  # Bit 0: CS1 polarity control, 0: active low, 1: active high
        (
            "CS2Polarity",
            ctypes.c_ubyte,
        ),  # Bit 0: CS2 polarity control, 0: active low, 1: active high
        (
            "IsAutoDeativeCS",
            ctypes.c_ushort,
        ),  # Automatically de-assert chip select after the operation is completed
        (
            "ActiveDelay",
            ctypes.c_ushort,
        ),  # Delay time for executing read/write operations after chip select is set, in microseconds
        (
            "DelayDeactive",
            ctypes.c_ulong,
        ),  # Delay time for executing read/write operations after chip select is de-asserted, in microseconds
    ]


class CH347:

    # MAX devices number
    MAX_DEVICE_NUMBER = 8

    # Define the callback function type
    NOTIFY_ROUTINE = ctypes.CFUNCTYPE(None, ctypes.c_ulong)

    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    def __init__(self, device_index=0, dll_path="ch347/lib/CH347DLLA64.DLL"):
        self.ch347dll = ctypes.WinDLL(dll_path)
        self.device_index = device_index

        # 创建回调函数对象并绑定到实例属性
        self.callback_func = self.NOTIFY_ROUTINE(self.event_callback)

        # Set the function argument types and return type for CH347OpenDevice
        self.ch347dll.CH347OpenDevice.argtypes = [ctypes.c_ulong]
        self.ch347dll.CH347OpenDevice.restype = ctypes.c_void_p

        # Set the function argument types and return type for CH347CloseDevice
        self.ch347dll.CH347CloseDevice.argtypes = [ctypes.c_ulong]
        self.ch347dll.CH347CloseDevice.restype = ctypes.c_bool

        # Set the function argument types and return type for CH347GetDeviceInfor
        self.ch347dll.CH347GetDeviceInfor.argtypes = [
            ctypes.c_ulong,
            ctypes.POINTER(DeviceInfo),
        ]
        self.ch347dll.CH347GetDeviceInfor.restype = ctypes.c_bool

        # Set the function argument types and return type for CH347GetVersion
        self.ch347dll.CH347GetVersion.argtypes = [
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(ctypes.c_ubyte),
        ]
        self.ch347dll.CH347GetVersion.restype = ctypes.c_bool

        # Set the function argument types and return type for CH347SetDeviceNotify
        self.ch347dll.CH347SetDeviceNotify.argtypes = [
            ctypes.c_ulong,
            ctypes.c_char_p,
            ctypes.CFUNCTYPE(None, ctypes.c_ulong),
        ]
        self.ch347dll.CH347SetDeviceNotify.restype = ctypes.c_bool

        # Set the function argument types and return type for CH347ReadData
        self.ch347dll.CH347ReadData.argtypes = [
            ctypes.c_ulong,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ulong),
        ]
        self.ch347dll.CH347ReadData.restype = ctypes.c_bool

        # Set the function argument types and return type for CH347WriteData
        self.ch347dll.CH347WriteData.argtypes = [
            ctypes.c_ulong,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ulong),
        ]
        self.ch347dll.CH347WriteData.restype = ctypes.c_bool

        # Set the function argument types and return type for CH347SetTimeout
        self.ch347dll.CH347SetTimeout.argtypes = [
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        self.ch347dll.CH347SetTimeout.restype = ctypes.c_bool

        # Set the function argument types and return type for CH347SPI_Init
        self.ch347dll.CH347SPI_Init.argtypes = [
            ctypes.c_ulong,
            ctypes.POINTER(SPIConfig),
        ]
        self.ch347dll.CH347SPI_Init.restype = ctypes.c_bool

        # Set the function argument types and return type for CH347SPI_GetCfg
        self.ch347dll.CH347SPI_GetCfg.argtypes = [
            ctypes.c_ulong,
            ctypes.POINTER(SPIConfig),
        ]
        self.ch347dll.CH347SPI_GetCfg.restype = ctypes.c_bool

        # Set the function argument types and return type for CH347SPI_ChangeCS
        self.ch347dll.CH347SPI_ChangeCS.argtypes = [ctypes.c_ulong, ctypes.c_ubyte]
        self.ch347dll.CH347SPI_ChangeCS.restype = ctypes.c_bool

        # Set the function argument types and return type for CH347SPI_SetChipSelect
        self.ch347dll.CH347SPI_SetChipSelect.argtypes = [
            ctypes.c_ulong,
            ctypes.c_ushort,
            ctypes.c_ushort,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        self.ch347dll.CH347SPI_SetChipSelect.restype = ctypes.c_bool

        # Set the function argument types and return type for CH347SPI_Write
        self.ch347dll.CH347SPI_Write.argtypes = [
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_void_p,
        ]
        self.ch347dll.CH347SPI_Write.restype = ctypes.c_bool

        # Set the function argument types and return type for CH347SPI_Read
        self.ch347dll.CH347SPI_Read.argtypes = [
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.c_void_p,
        ]
        self.ch347dll.CH347SPI_Read.restype = ctypes.c_bool

        # Set the function argument types and return type for CH347SPI_WriteRead
        self.ch347dll.CH347SPI_WriteRead.argtypes = [
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_void_p,
        ]
        self.ch347dll.CH347SPI_WriteRead.restype = ctypes.c_bool

        # Set the function argument types and return type for CH347StreamSPI4
        self.ch347dll.CH347StreamSPI4.argtypes = [
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_void_p,
        ]
        self.ch347dll.CH347StreamSPI4.restype = ctypes.c_bool

        # Set the function argument types and return type for CH347I2C_Set
        self.ch347dll.CH347I2C_Set.argtypes = [ctypes.c_ulong, ctypes.c_ulong]
        self.ch347dll.CH347I2C_Set.restype = ctypes.c_bool

        # Set the function argument types and return type for CH347I2C_SetDelaymS
        self.ch347dll.CH347I2C_SetDelaymS.argtypes = [ctypes.c_ulong, ctypes.c_ulong]
        self.ch347dll.CH347I2C_SetDelaymS.restype = ctypes.c_bool

        # Set the function argument types and return type for CH347StreamI2C
        self.ch347dll.CH347StreamI2C.argtypes = [
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_void_p,
        ]
        self.ch347dll.CH347StreamI2C.restype = ctypes.c_bool

    def list_devices(self):
        # List all devices
        num_devices = 0
        dev_info = DeviceInfo()
        for i in range(self.MAX_DEVICE_NUMBER):
            if self.ch347dll.CH347OpenDevice(i) == self.INVALID_HANDLE_VALUE:
                break
            num_devices += 1
            if self.ch347dll.CH347GetDeviceInfor(i, ctypes.byref(dev_info)):
                for field_name, _ in dev_info._fields_:
                    value = getattr(dev_info, field_name)
                    print(f"{field_name}: {value}")
            print("-" * 40)
            self.ch347dll.CH347CloseDevice(i)
        print(f"Number of devices: {num_devices}")
        return num_devices

    @staticmethod
    def event_callback(self, event_status):
        # Callback function implementation
        print("Callback event status:", event_status)
        if event_status == 0:
            # Device unplug event
            print("Device unplugged")
        elif event_status == 3:
            # Device insertion event
            print("Device inserted")

    def open_device(self):
        """
        Open USB device.

        Returns:
            int: Handle to the opened device if successful, None otherwise.
        """
        handle = self.ch347dll.CH347OpenDevice(self.device_index)
        if handle != self.INVALID_HANDLE_VALUE:
            return handle
        else:
            return None

    def close_device(self):
        """
        Close USB device.

        Returns:
            bool: True if successful, False otherwise.
        """
        result = self.ch347dll.CH347CloseDevice(self.device_index)
        return result

    def get_device_info(self):
        """
        Get device information.

        Returns:
            bool: True if successful, False otherwise.
            DeviceInfo: Device information.
        """
        dev_info = DeviceInfo()
        result = self.ch347dll.CH347GetDeviceInfor(
            self.device_index, ctypes.byref(dev_info)
        )
        if result:
            return dev_info
        else:
            return None

    def get_version(self):
        """
        Obtain driver version, library version, device version, and chip type.

        This method retrieves various versions related to the CH347 device and returns them as a tuple.

        Returns:
            tuple or None: A tuple containing the following information if successful:
                - driver_ver (int): The driver version.
                - dll_ver (int): The library version.
                - device_ver (int): The device version.
                - chip_type (int): The chip type.
            Returns None if the retrieval fails.
        """
        # Create variables to store the version information
        driver_ver = ctypes.c_ubyte()
        dll_ver = ctypes.c_ubyte()
        device_ver = ctypes.c_ubyte()
        chip_type = ctypes.c_ubyte()

        # Call the CH347GetVersion function
        result = self.ch347dll.CH347GetVersion(
            self.device_index,
            ctypes.byref(driver_ver),
            ctypes.byref(dll_ver),
            ctypes.byref(device_ver),
            ctypes.byref(chip_type),
        )
        if result:
            return driver_ver.value, dll_ver.value, device_ver.value, chip_type.value
        else:
            return None

    def set_device_notify(self, device_id, notify_routine=event_callback):
        """
        Configure device event notifier.

        Args:
            device_id (str): Optional parameter specifying the ID of the monitored device.
            notify_routine (callable): Callback function to handle device events.

        Returns:
            bool: True if successful, False otherwise.
        """
        callback = self.NOTIFY_ROUTINE(notify_routine)
        result = self.ch347dll.CH347SetDeviceNotify(
            self.device_index, device_id, callback
        )
        return result

    def read_data(self, buffer, length):
        """
        Read USB data block.

        Args:
            buffer (ctypes.c_void_p): Pointer to a buffer to store the read data.
            length (ctypes.POINTER(ctypes.c_ulong)): Pointer to the length unit. Contains the length to be read as input and the actual read length after return.

        Returns:
            bool: True if successful, False otherwise.
        """
        result = self.ch347dll.CH347ReadData(self.device_index, buffer, length)
        return result

    def write_data(self, buffer, length):
        """
        Write USB data block.

        Args:
            buffer (ctypes.c_void_p): Pointer to a buffer containing the data to be written.
            length (ctypes.POINTER(ctypes.c_ulong)): Pointer to the length unit. Input length is the intended length, and the return length is the actual length.

        Returns:
            bool: True if successful, False otherwise.
        """
        result = self.ch347dll.CH347WriteData(self.device_index, buffer, length)
        return result

    def set_timeout(self, write_timeout, read_timeout):
        """
        Set the timeout of USB data read and write.

        Args:
            write_timeout (int): Timeout for USB to write data blocks, in milliseconds. Use 0xFFFFFFFF to specify no timeout (default).
            read_timeout (int): Timeout for USB to read data blocks, in milliseconds. Use 0xFFFFFFFF to specify no timeout (default).

        Returns:
            bool: True if successful, False otherwise.
        """
        result = self.ch347dll.CH347SetTimeout(
            self.device_index, write_timeout, read_timeout
        )
        return result

    def spi_init(self, spi_config: SPIConfig) -> bool:
        """
        Initialize the SPI Controller.

        Args:
            spi_config (SPIConfig): The configuration for the SPI controller.

        Returns:
            bool: True if initialization is successful, False otherwise.
        """
        result = self.ch347dll.CH347SPI_Init(
            self.device_index, ctypes.byref(spi_config)
        )
        return result

    def spi_get_config(self):
        """
        Get SPI controller configuration information.

        Returns:
            tuple: A tuple containing a boolean value indicating if the operation was successful
            and the SPI configuration structure.

            The first element (bool) represents whether the operation was successful or not.
            - True: The operation was successful.
            - False: The operation failed.

            The second element (SPIConfig): An instance of the SPIConfig class, representing the
            SPI configuration structure. If the operation was successful, this object will contain
            the configuration information retrieved from the SPI controller. Otherwise, it will be
            an empty object with default values.
        """
        spi_config = SPIConfig()
        result = self.ch347dll.CH347SPI_GetCfg(
            self.device_index, ctypes.byref(spi_config)
        )
        if result:
            return spi_config
        else:
            return None

    def spi_change_cs(self, status):
        """
        Change the chip selection status.

        Args:
            status (int): Chip selection status. 0 = Cancel the piece to choose, 1 = Set piece selected.

        Returns:
            bool: True if successful, False otherwise.
        """
        result = self.ch347dll.CH347SPI_ChangeCS(self.device_index, status)
        return result

    def spi_set_chip_select(
        self,
        enable_select,
        chip_select,
        is_auto_deactive_cs,
        active_delay,
        delay_deactive,
    ):
        """
        Set SPI chip selection.

        Args:
            enable_select (int): Enable selection status. The lower octet is CS1 and the higher octet is CS2.
                                A byte value of 1 sets CS, 0 ignores this CS setting.
            chip_select (int): Chip selection status. The lower octet is CS1 and the higher octet is CS2.
                               A byte value of 1 sets CS, 0 ignores this CS setting.
            is_auto_deactive_cs (int): Auto deactivation status. The lower 16 bits are CS1 and the higher 16 bits are CS2.
                                       Whether to undo slice selection automatically after the operation is complete.
            active_delay (int): Latency of read/write operations after chip selection, in microseconds.
                                The lower 16 bits are CS1 and the higher 16 bits are CS2.
            delay_deactive (int): Delay time for read and write operations after slice selection, in microseconds.
                                  The lower 16 bits are CS1 and the higher 16 bits are CS2.

        Returns:
            bool: True if successful, False otherwise.
        """
        result = self.ch347dll.CH347SPI_SetChipSelect(
            self.device_index,
            enable_select,
            chip_select,
            is_auto_deactive_cs,
            active_delay,
            delay_deactive,
        )
        return result

    def spi_write(
        self, chip_select: int, write_data: List[int], write_step: int = 512
    ) -> bool:
        result = self.spi_write(chip_select, bytes(write_data), write_step)
    def spi_write(
        self, chip_select: int, write_data: bytes, write_step: int = 512
    ) -> bool:
        """
        SPI write data.

        Args:
            chip_select (int): Chip selection control. When bit 7 is 0, chip selection control is ignored.
                                When bit 7 is 1, chip selection operation is performed.
            write_data (List[int]): List of integers to write.
            write_step (int, optional): The length of a single block to be read. Default is 512.

        Returns:
            bool: True if successful, False otherwise.
        """
        write_length = len(write_data)
        write_buffer = ctypes.create_string_buffer(write_data)
        result = self.ch347dll.CH347SPI_Write(
            self.device_index, chip_select, write_length, write_step, write_buffer
        )
        return result

    def spi_read(
        self, chip_select: int, write_data: List[int], read_length: int
    ) -> List[int]:
        """
        SPI read data.

        Args:
            chip_select (int): Chip selection control. When bit 7 is 0, chip selection control is ignored.
                            When bit 7 is 1, chip selection operation is performed.
            write_data (List[int]): List of integers to write.
            read_length (int): Number of bytes to read.

        Returns:
            List[int]: Data read in from the SPI stream if successful, None otherwise.
        """
        write_length = len(write_data)

        # Create ctypes buffer for write data
        write_buffer = ctypes.create_string_buffer(bytes(write_data))

        # Create ctypes buffer for read data
        read_buffer = ctypes.create_string_buffer(read_length)

        # Create combined buffer for read and write data
        combined_buffer = ctypes.create_string_buffer(
            write_buffer.raw[:write_length] + read_buffer.raw
        )

        result = self.ch347dll.CH347SPI_Read(
            self.device_index,
            chip_select,
            write_length,
            ctypes.byref(ctypes.c_ulong(read_length)),
            combined_buffer,
        )

        if result:
            # Extract the read data from the combined buffer
            read_data = list(combined_buffer[:read_length])
            return read_data
        else:
            return None

    def spi_write_read(self, chip_select: int, write_data: bytes) -> bytes:
        io_buffer = ctypes.create_string_buffer(write_data)
        result = self.ch347dll.CH347SPI_WriteRead(
            self.device_index, chip_select, len(write_data), io_buffer
        )
        # transform the ctypes buffer to bytes
        io_data = io_buffer.raw[: len(write_data)]
        return io_data

    def _spi_write_read(self, chip_select: int, length: int, io_buffer: ctypes.c_void_p) -> bool:
        """
        Handle SPI data stream 4-wire interface.

        Args:
            chip_select (int): Selection control. If the film selection control bit 7 is 0, ignore the film selection control.
                               If bit 7 is 1, perform the film selection.
            length (int): Number of bytes of data to be transferred.
            io_buffer (ctypes.c_void_p): Points to a buffer that places the data to be written out from DOUT.
                                        Returns the data read in from DIN.

        Returns:
            bool: True if successful, False otherwise.
        """
        result = self.ch347dll.CH347SPI_WriteRead(
            self.device_index, chip_select, length, io_buffer
        )
        return result

    def stream_spi4(self, chip_select, length, io_buffer):
        """
        Handle SPI data stream 4-wire interface.

        Args:
            chip_select (int): Film selection control. If bit 7 is 0, slice selection control is ignored.
                               If bit 7 is 1, the parameter is valid: Bit 1 bit 0 is 00/01/10.
                               Select D0/D1/D2 pins as low-level active chip options, respectively.
            length (int): Number of bytes of data to be transferred.
            io_buffer (ctypes.c_void_p): Points to a buffer that places data to be written out from DOUT.
                                        Returns data to be read in from DIN.

        Returns:
            bool: True if successful, False otherwise.
        """
        result = self.ch347dll.CH347StreamSPI4(
            self.device_index, chip_select, length, io_buffer
        )
        return result

    def i2c_set(self, interface_speed):
        """
        Set the serial port flow mode.

        Args:
            interface_speed (int): I2C interface speed / SCL frequency. Bit 1-bit 0:
                                0 = low speed / 20KHz
                                1 = standard / 100KHz (default)
                                2 = fast / 400KHz
                                3 = high speed / 750KHz

        Returns:
            bool: True if successful, False otherwise.
        """
        result = self.ch347dll.CH347I2C_Set(self.device_index, interface_speed)
        return result

    def i2c_set_delay_ms(self, delay_ms):
        """
        Set the hardware asynchronous delay to a specified number of milliseconds before the next stream operation.

        Args:
            delay_ms (int): Delay duration in milliseconds (ms).

        Returns:
            bool: True if successful, False otherwise.
        """
        result = self.ch347dll.CH347I2C_SetDelaymS(self.device_index, delay_ms)
        return result

    def stream_i2c(self, write_data, read_length):
        """
        Process I2C data stream.

        Args:
            write_data (bytes): Data to write. The first byte is usually the I2C device address and read/write direction bit.
            read_length (int): Number of bytes of data to read.

        Returns:
            bytes: Data read from the I2C stream.
        """
        write_length = len(write_data)

        # Convert write_data to ctypes buffer
        write_buffer = ctypes.create_string_buffer(bytes(write_data))

        # Create ctypes buffer for read data
        read_buffer = ctypes.create_string_buffer(read_length)

        result = self.ch347dll.CH347StreamI2C(
            self.device_index, write_length, write_buffer, read_length, read_buffer
        )

        if result:
            return read_buffer[:read_length]
        else:
            return None
