# -*- coding: utf-8 -*-
# bacon
# Author: ChisBread (github.com/ChisBread)
import zlib
import time
from .bacon import BaconDevice
DEBUG = False
DEVICE_CMD = {}
CMD_TO_NAME = {}
DEVICE_VAR = {}
VARKEY_TO_NAME = {}

FLASH_TYPES = {
    "AMD": 0x01,
    "INTEL": 0x02,
    "SHARP": 0x02,
    "OTHERS":0x00,
}

FLASH_MODS = {
    "FLASH_METHOD_AGB_FLASH2ADVANCE": 0x05,
    "FLASH_METHOD_DMG_MMSA": 0x03,
    "FLASH_METHOD_DMG_DATEL_ORBITV2": 0x09,
    "FLASH_METHOD_DMG_E201264": 0x0A,
    "FLASH_METHOD_AGB_GBAMP": 0x0B,
    "FLASH_METHOD_DMG_BUNG_16M": 0x0C,
    "FLASH_METHOD_BUFFERED": 0x02,
    "FLASH_METHOD_PAGED": 0x08,
    "FLASH_METHOD_UNBUFFERED": 0x01,
}

def SetDebug(debug: bool):
    global DEBUG
    DEBUG = debug

def SetDeviceCMD(device_cmd: dict, device_var: dict):
    DEVICE_CMD = device_cmd
    for key in device_cmd.keys():
        CMD_TO_NAME[device_cmd[key]] = key
    for key in device_var.keys():
        VARKEY_TO_NAME[tuple(device_var[key])] = key

def ParseCommand(cmd: bytes):
    if len(cmd) == 0:
        return None
    return CMD_TO_NAME.get(cmd[0], "UNKNOWN")

def dprint(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)

# | 地址范围    | 功能       | 大小     | 说明 |
# |------------|-----------|---------|------|
# | 08000000-09FFFFFF | ROM/FlashROM | 32MB | ROM/FlashROM的地址空间(等待状态0) |
# | 0A000000-0BFFFFFF | ROM/FlashROM | 32MB | ROM/FlashROM的地址空间(等待状态1) |
# | 0C000000-0DFFFFFF | ROM/FlashROM | 32MB | ROM/FlashROM的地址空间(等待状态2) |
# | 0E000000-0E00FFFF | SRAM        | 64KB | SRAM的地址空间(8位总线) |

def MappingAddressToReal(addr):
    if addr >= 0x08000000 and addr <= 0x09FFFFFF:
        return addr - 0x08000000
    if addr >= 0x0A000000 and addr <= 0x0BFFFFFF:
        return addr - 0x0A000000
    if addr >= 0x0C000000 and addr <= 0x0DFFFFFF:
        return addr - 0x0C000000
    if addr >= 0x0E000000 and addr <= 0x0E00FFFF:
        return addr - 0x0E000000
    return addr

# 模拟串口设备，兼容GBX协议
class BaconFakeSerialDevice:
    def __init__(self):
        self.timeout = 1

        self.in_buff = b"" * 0x4000
        self.in_buff_size = 0x4000
        self.out_buff = b"\x00" * 0x4000
        self.out_buff_offset = 0
        self.out_buff_size = 0x4000

        self.in_waiting = 0

        self.bacon_dev = BaconDevice()
        self.is_open = True
        
        self.FLASH_CMD_TYPE = 0x00
        self.FLASH_CMD_MOD = 0x00
        self.FLASH_CMD_WE = 0x00
        self.FLASH_CUSTOM_CMDS = [0x00]*6

        self.BAK_FLASH_TYPE = 0x00

        self.FW_VARS = {}
        self.MODE = "AGB" # or DMG
        self.POWER = 0
        self.AGB_SRAM_WRITING = False
        self.AGB_BAK_FLASH_WRITING = False
        self.CALC_CRC32_WAITING = False
        self.FLASH_PROGRAMMING = False
        self.SET_FLASH_CMD_WAITING = 0

        # ROM cache 32MB
        self.ROM_CACHE = [0x00]*0x2000000
        self.ROM_CACHED = [False]*0x2000000
    
    def cache_rom(self, addr, data):
        self.ROM_CACHE[addr:addr+len(data)] = data
        self.ROM_CACHED[addr:addr+len(data)] = [True]*len(data)
    def cache_rom_reset(self, addr=0, size=0x2000000):
        self.ROM_CACHED[addr:addr+size] = [False]*size
    def read_rom(self, addr, size):
        if self.ROM_CACHED[addr:addr+size].count(False) > 0:
            dprint("[BaconFakeSerialDevice] ReadROM:0x%08X Size:%s" % (addr, size))
            self.cache_rom(addr, self.bacon_dev.AGBReadROM(addr, size))
        else:
            dprint("[BaconFakeSerialDevice] ReadROMCached:0x%08X Size:%s" % (addr, size))
        return bytes(self.ROM_CACHE[addr:addr+size])

    def isOpen(self):
        return self.bacon_dev is not None

    def close(self):
        if self.bacon_dev is not None:
            self.bacon_dev.Close()
            self.bacon_dev = None
            self.reset_input_buffer()
            self.reset_output_buffer()
            self.is_open = False
    
    def open(self):
        self.bacon_dev = BaconDevice()
        self.is_open = True

    def reset_input_buffer(self):
        self.in_buff = b""
        self.in_waiting = 0
    
    def reset_output_buffer(self):
        self.out_buff_offset = 0

    def push_to_input_buffer(self, data):
        dprint("[BaconFakeSerialDevice] PushData:%s" % data.hex())
        self.in_buff = self.in_buff + data
        self.in_waiting = len(data)

    def _push_ack(self):
        self.push_to_input_buffer(b"\x01")
    
    def write(self, data):
        self._cmd_parse(data)
        return len(data)

    def _make_flash_cmds(self, addr, buffer_size):
        flash_prepare = []
        flash_commit = []
        for j in range(6):
            tcmd = (self.FLASH_CUSTOM_CMDS[j][0]<<1, self.FLASH_CUSTOM_CMDS[j][1])
            flash_prepare.append(tcmd)

            if flash_prepare[-1] == (0x00, 0x00): # write buffer size?
                flash_prepare[-1] = (addr, buffer_size//2-1)
                for k in range(j+1, 6):
                    # commit
                    if not (self.FLASH_CUSTOM_CMDS[k] == (0x00, 0x00)):
                        tcmd = (self.FLASH_CUSTOM_CMDS[k][0]<<1, self.FLASH_CUSTOM_CMDS[k][1])
                        flash_commit.append(tcmd)
                        if flash_commit[-1][0] == 0x00:
                            flash_commit[-1] = (addr, flash_commit[-1][1])
                break
            elif flash_prepare[-1][0] == 0x00:
                flash_prepare[-1] = (addr, flash_prepare[-1][1])
        return flash_prepare, flash_commit


    def _cmd_parse(self, cmd):
        if self.AGB_SRAM_WRITING:
            dprint("[BaconFakeSerialDevice] AGB_CART_WRITE_SRAM:0x%08X Value:%s" % (self.FW_VARS["ADDRESS"], cmd.hex()))
            addr = MappingAddressToReal(self.FW_VARS["ADDRESS"])
            self.bacon_dev.AGBWriteRAM(addr, cmd)
            self.FW_VARS["ADDRESS"] += self.FW_VARS["TRANSFER_SIZE"]
            self.AGB_SRAM_WRITING = False
            self._push_ack()
            return
        if self.AGB_BAK_FLASH_WRITING:
            dprint("[BaconFakeSerialDevice] AGB_CART_WRITE_FLASH_DATA:0x%08X" % (self.FW_VARS["ADDRESS"], ))
            addr = MappingAddressToReal(self.FW_VARS["ADDRESS"])
            # prepare unlock cmds and write
            # TODO: other flash type
            flash_cmds = [
                (0x5555, 0xAA),
                (0x2AAA, 0x55),
                (0x5555, 0xA0),
            ]
            flash_exit = (0, 0xF0)
            if self.BAK_FLASH_TYPE != FLASH_TYPES["AMD"]:
                raise Exception("Unsupported Backup Flash Type")
            for i, data in enumerate(cmd):
                self.bacon_dev.AGBWriteRAMWithAddress(commands = flash_cmds+[(addr+i, data), flash_exit], reset=False).Flush()
            self.FW_VARS["ADDRESS"] += self.FW_VARS["TRANSFER_SIZE"]
            self.AGB_BAK_FLASH_WRITING = False
            self._push_ack()
            return
        if self.CALC_CRC32_WAITING:
            chunk_size = int.from_bytes(cmd, byteorder='big')
            addr = MappingAddressToReal(self.FW_VARS["ADDRESS"]<<1)
            dprint("[BaconFakeSerialDevice] CALC_CRC32:0x%08X Size:0x%08X" % (self.FW_VARS["ADDRESS"], chunk_size))
            ret = self.read_rom(addr, chunk_size)
            crc32 = zlib.crc32(ret)
            # push crc32 4byte big-endian
            self.push_to_input_buffer(crc32.to_bytes(4, byteorder='big'))
            self.CALC_CRC32_WAITING = False
            return
        if self.FLASH_PROGRAMMING:
            #TODO: More AGB Flash Type, And DMG Flash
            raw_addr = MappingAddressToReal(self.FW_VARS["ADDRESS"]<<1)
            addr = raw_addr
            size = self.FW_VARS["TRANSFER_SIZE"]
            buffer_size = self.FW_VARS["BUFFER_SIZE"]
            dprint("[BaconFakeSerialDevice] FLASH_PROGRAMMING:0x%08X ValueSize:%s TransferSize:%s BufferSize:%s" % (self.FW_VARS["ADDRESS"], len(cmd), size, buffer_size))
            if self.FLASH_CMD_MOD == FLASH_MODS["FLASH_METHOD_BUFFERED"] and buffer_size > 0:
                # per buffer Seq
                start_time = time.time()
                self.cache_rom_reset(raw_addr, size)
                for i in range(0, size, buffer_size):
                    # make flash cmds
                    flash_prepare, flash_commit = self._make_flash_cmds(addr, buffer_size)
                    #dprint("[BaconFakeSerialDevice] FLASH_PROGRAMMING Prepare:%s Commit:%s" % ([(hex(i[0]), hex(i[1])) for i in flash_prepare], [(hex(i[0]), hex(i[1])) for i in flash_commit]))
                    self.bacon_dev.AGBWriteROMWithAddress(commands=flash_prepare)
                    self.bacon_dev.AGBWriteROMSequential(addr=addr, data=cmd[i:i+buffer_size], reset=False)
                    self.bacon_dev.AGBWriteROMWithAddress(commands=flash_commit).Flush()
                    # S29GL256:
                    # 2-byte[33] 125 750 µs
                    # 32-byte[33] 160 750
                    # 64-byte[33] 175 750
                    # 128-byte[33] 198 750
                    # 256-byte[33] 239 750
                    # 512-byte 340 750
                    # Don't need verify if time is enough
                    addr += buffer_size
                # retry
                ret = self.read_rom(raw_addr, size)
                dprint("[BaconFakeSerialDevice] FLASH_PROGRAMMING PerBufferTime:%s(us)" % ((time.time()-start_time)/(size//buffer_size)*1000000))
                addr = raw_addr
                for i in range(0, size, buffer_size):
                    j = 1
                    while ret[i:i+buffer_size] != cmd[i:i+buffer_size]:
                        if j > 10:
                            dprint("[BaconFakeSerialDevice] FLASH_PROGRAMMING Retry Failed!")
                            break
                        flash_prepare, flash_commit = self._make_flash_cmds(addr, buffer_size)
                        self.bacon_dev.AGBWriteROMWithAddress(commands=flash_prepare)
                        self.bacon_dev.AGBWriteROMSequential(addr=addr, data=cmd[i:i+buffer_size], reset=False)
                        self.bacon_dev.AGBWriteROMWithAddress(commands=flash_commit).Flush()
                        # 等待Nms
                        time.sleep(0.001*j)
                        dprint("[BaconFakeSerialDevice] FLASH_PROGRAMMING Retry:%s" % j)
                        ret = ret[:i] + self.read_rom(addr, buffer_size) + ret[i+buffer_size:]
                        j += 1
                    addr += buffer_size

            else:
                #TODO write with cmd
                pass
            self._push_ack()
            self.FLASH_PROGRAMMING = False
            self.FW_VARS["ADDRESS"] += size // 2
            return
        if self.SET_FLASH_CMD_WAITING > 0:
            if self.SET_FLASH_CMD_WAITING == 9:
                self.FLASH_CMD_TYPE = int.from_bytes(cmd, byteorder='big')
            elif self.SET_FLASH_CMD_WAITING == 8:
                self.FLASH_CMD_MOD = int.from_bytes(cmd, byteorder='big')
            elif self.SET_FLASH_CMD_WAITING == 7:
                self.FLASH_CMD_WE = int.from_bytes(cmd, byteorder='big')
            elif self.SET_FLASH_CMD_WAITING <= 6:
                # 0~3: addr
                # 4~5: cmd
                self.FLASH_CUSTOM_CMDS[6-self.SET_FLASH_CMD_WAITING] = (int.from_bytes(cmd[:4], byteorder='big'), int.from_bytes(cmd[4:], byteorder='big'))
            dprint("[BaconFakeSerialDevice] SET_FLASH_CMD: Type:%s Mod:%s WE:%s Cmds:%s" % (self.FLASH_CMD_TYPE, self.FLASH_CMD_MOD, self.FLASH_CMD_WE, self.FLASH_CUSTOM_CMDS))
            self.SET_FLASH_CMD_WAITING = self.SET_FLASH_CMD_WAITING - 1
            if self.SET_FLASH_CMD_WAITING == 0:
                self._push_ack()
            return

        cmdname = ParseCommand(cmd)
        
        if cmdname == 'SET_VARIABLE':
            # 0: cmd
            # 1: size
            # 2-5: key
            # 6-: value
            size = int(cmd[1])*8
            key = int.from_bytes(cmd[2:6], byteorder='big')
            value = int.from_bytes(cmd[6:], byteorder='big')
            # save
            self.FW_VARS[VARKEY_TO_NAME.get((size, key), "UNKNOWN")] = value
            self._push_ack()
            dprint("[BaconFakeSerialDevice] SetVariable:", VARKEY_TO_NAME.get((size, key), "UNKNOWN"), value)
        elif cmdname == "GET_VARIABLE":
            # 0: cmd
            # 1: size
            # 2-5: key
            size = int(cmd[1])
            key = int.from_bytes(cmd[2:6], byteorder='big')
            # get
            value = self.FW_VARS.get(VARKEY_TO_NAME.get((size, key), "UNKNOWN"), 0)
            self.push_to_input_buffer(bytes([(value >> (i*8)) & 0xFF for i in range(4)]))
        elif cmdname == "SET_MODE_AGB":
            self.MODE = "AGB"
            self._push_ack()
        elif cmdname == "SET_MODE_DMG":
            self.MODE = "DMG"
            self._push_ack()
        elif cmdname == "SET_VOLTAGE_3_3V":
            self.POWER = 3
            self._push_ack()
        elif cmdname == "SET_VOLTAGE_5V":
            self.POWER = 5
            self._push_ack()
        elif cmdname == "CART_PWR_ON":
            if self.POWER == 3:
                self.bacon_dev.PowerControl(v3_3v=True, v5v=False).Flush()
            elif self.POWER == 5:
                self.bacon_dev.PowerControl(v3_3v=False, v5v=True).Flush()
            self._push_ack()
        elif cmdname == "CART_PWR_OFF":
            self.bacon_dev.PowerControl(v3_3v=False, v5v=False).Flush()
            self._push_ack()
        elif cmdname == "QUERY_CART_PWR":
            self.push_to_input_buffer(bytes([self.bacon_dev.power]))
            dprint("[BaconFakeSerialDevice] QueryCartPower:", self.bacon_dev.power)
        elif cmdname == "AGB_CART_READ_SRAM":
            addr = MappingAddressToReal(self.FW_VARS["ADDRESS"])
            dprint("[BaconFakeSerialDevice] AGB_CART_READ_SRAM:0x%08X(0x%08X) Size:%d" % (self.FW_VARS["ADDRESS"], addr, self.FW_VARS["TRANSFER_SIZE"]))
            ret = self.bacon_dev.AGBReadRAM(addr, self.FW_VARS["TRANSFER_SIZE"])
            self.push_to_input_buffer(ret)
            self.FW_VARS["ADDRESS"] += self.FW_VARS["TRANSFER_SIZE"]
        elif cmdname == "AGB_CART_WRITE_SRAM":
            self.AGB_SRAM_WRITING = True
        elif cmdname == "AGB_CART_WRITE_FLASH_DATA":
            self.AGB_BAK_FLASH_WRITING = True
            self.BAK_FLASH_TYPE = int(cmd[1])
        elif cmdname == "CALC_CRC32": # 读取一段数据，计算CRC32
            # 0: cmd
            # 1~4: chunk_size
            self.CALC_CRC32_WAITING = True
        elif cmdname == "AGB_CART_READ":
            addr = MappingAddressToReal(self.FW_VARS["ADDRESS"]<<1)
            dprint("[BaconFakeSerialDevice] AGB_CART_READ:0x%08X(0x%08X) Size:%d" % (self.FW_VARS["ADDRESS"], addr, self.FW_VARS["TRANSFER_SIZE"]))
            ret = self.bacon_dev.AGBReadROM(addr, self.FW_VARS["TRANSFER_SIZE"], reset=False)
            if ret is not False:
                self.push_to_input_buffer(ret)
            if self.MODE == "AGB":
                self.FW_VARS["ADDRESS"] += self.FW_VARS["TRANSFER_SIZE"]//2
            else:
                self.FW_VARS["ADDRESS"] += self.FW_VARS["TRANSFER_SIZE"]
        elif cmdname == "AGB_FLASH_WRITE_SHORT":
            # 0: cmd
            # 1~4: addr
            # 5~6: short
            dprint("[BaconFakeSerialDevice] AGB_FLASH_WRITE_SHORT:0x%08X Value:%s" % (int.from_bytes(cmd[1:5], byteorder='big'), hex(int.from_bytes(cmd[5:7], byteorder='big'))))
            addr = int.from_bytes(cmd[1:5], byteorder='big')
            addr = MappingAddressToReal(addr<<1)
            self.bacon_dev.AGBWriteROMWithAddress(commands=[(addr, int.from_bytes(cmd[5:7], byteorder='big'))]).Flush()
            self._push_ack()
        elif cmdname == "CART_WRITE_FLASH_CMD":
            # 0: cmd
            # 1: flashcart
            # 2: num
            # 6byte * num: cmds(4byte addr, 2byte cmd)
            flashcart = int(cmd[1])
            num = int(cmd[2])
            cmds = []
            for i in range(num):
                addr = int.from_bytes(cmd[3+i*6:7+i*6], byteorder='big')
                if self.MODE == "AGB" and flashcart:
                    addr = MappingAddressToReal(addr<<1)
                data = int.from_bytes(cmd[7+i*6:9+i*6], byteorder='big')
                dprint("[BaconFakeSerialDevice] CART_WRITE_FLASH_CMD:0x%08X Value:%s" % (addr, hex(data)))
                cmds.append((addr, data))
            if self.MODE == "AGB" and flashcart:
                self.bacon_dev.AGBWriteROMWithAddress(commands=cmds).Flush()
            else:
                self.bacon_dev.AGBWriteRAMWithAddress(commands=cmds).Flush()
            self._push_ack()
        elif cmdname == "FLASH_PROGRAM":
            self.FLASH_PROGRAMMING = True
            # self._push_ack() 0x03?
        elif cmdname == "SET_FLASH_CMD":
            self.SET_FLASH_CMD_WAITING = 9
        elif cmdname == "AGB_CART_WRITE":
            # 0: cmd
            # 1~4: addr
            # 5~6: short
            addr = int.from_bytes(cmd[1:5], byteorder='big')
            addr = MappingAddressToReal(addr<<1)
            dprint("[BaconFakeSerialDevice] AGB_CART_WRITE:0x%08X Value:%s" % (addr, hex(int.from_bytes(cmd[5:7], byteorder='big'))))
            self.bacon_dev.AGBWriteROMWithAddress(commands=[(addr, int.from_bytes(cmd[5:7], byteorder='big'))]).Flush()
            self._push_ack()
        elif cmdname == "AGB_READ_GPIO_RTC":
            dprint("[BaconFakeSerialDevice] !!!! AGB_READ_GPIO_RTC is not implemented !!!!")
            self.push_to_input_buffer(b"\x00"*8)
        elif cmdname == "ENABLE_PULLUPS":
            # TODO
            dprint("[BaconFakeSerialDevice] !!!! DISABLE_PULLUPS is not implemented !!!!")
            self._push_ack()
        elif cmdname == "DISABLE_PULLUPS":
            # TODO
            dprint("[BaconFakeSerialDevice] !!!! DISABLE_PULLUPS is not implemented !!!!")
            self._push_ack()
        elif cmdname == "AGB_BOOTUP_SEQUENCE":
            # TODO
            dprint("[BaconFakeSerialDevice] !!!! AGB_BOOTUP_SEQUENCE is not implemented !!!!")
            self._push_ack()
        ###### DMG CMDS ######
        elif cmdname == "DMG_MBC_RESET":
            self._push_ack()
        elif cmd[0] == 0:
            self._push_ack()
        else:
            dprint("[BaconFakeSerialDevice] UnsupportedCommand:%s Value:%s" % (cmdname, cmd.hex()))

    
    def read(self, size: int):
        dprint("[BaconFakeSerialDevice] ReadSize:%s, Left:%s" % (size, self.in_waiting))
        if size == 0:
            return b""
        if size > self.in_waiting:
            size = self.in_waiting
        data = self.in_buff[:size]
        self.in_buff = self.in_buff[size:]
        self.in_waiting = len(self.in_buff)
        dprint("[BaconFakeSerialDevice] ReadData:%s size:%s" % ([ hex(i) for i in data[:64] ], size))
        return data
    
    def flush(self):
        # TODO: Parse the command
        self.reset_output_buffer()
