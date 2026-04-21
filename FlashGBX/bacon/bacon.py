# -*- coding: utf-8 -*-
# bacon
# Author: ChisBread (github.com/ChisBread)

import platform
import random
import time
import os

from .command import *


ROM_MAX_SIZE = 0x2000000 # 32MB
RAM_MAX_SIZE = 0x20000 # 128KB (with bank)

class BaconWritePipeline:
    def __init__(self, dev, flush_func):
        self.cmds = ""
        self.dev = dev
        self.flush_func = flush_func
        self.MAX_LEN = 0x1000

    def WillFlush(self, cmd: str):
        if (len(self.cmds) + 1 + len(cmd))//8 >= self.MAX_LEN:
            return True
        return False

    def Write(self, cmd: str):
        if (len(self.cmds) + 1 + len(cmd))//8 >= self.MAX_LEN:
            self.flush_func(command2bytes(self.cmds))
            self.cmds = ""
        if self.cmds:
            self.cmds += "0"
        self.cmds += cmd
        return self
    
    def IsEmpty(self):
        return len(self.cmds) == 0
    
    def Flush(self):
        if self.cmds:
            self.flush_func(command2bytes(self.cmds))
            self.cmds = ""
        return self
    



class BaconDevice:
    GPIO_REG_DAT = 0xC4 # Data low 4bit
    GPIO_REG_CNT = 0xC6 # IO Select 1:Write to GPIO Device 0:Read from GPIO Device
    GPIO_REG_RE  = 0xC8 # Read Enable Flag Register 1:Enable 0:Disable
    
    def __init__(self, hid_device=None, ch347_device=None, gpio_device=None):
        self.hid_device = hid_device
        self.ch347_device = ch347_device
        self.gpio_device = gpio_device
        self.power = 0
        self.MAX_LEN = 0x1000
        # if all device is None, find a device
        ## check if windows
        if self.ch347_device is None and self.hid_device is None and self.gpio_device is None:
            if platform.system() == "Windows":
                if self.ch347_device is None:
                    #WCHAPI
                    from .ch347 import SPIConfig, CH347
                    ch347 = CH347(device_index=0, dll_path=os.path.join(os.path.dirname(__file__), "lib/CH347DLLA64.DLL"))
                    ch347.close_device()
                    ch347.open_device()
                    spi_config = SPIConfig(
                        Mode=3,
                        Clock=0,
                        ByteOrder=1,
                        SpiWriteReadInterval=0,
                        SpiOutDefaultData=0xFF,
                        ChipSelect=0x80,
                        CS1Polarity=0,
                        CS2Polarity=0,
                        IsAutoDeative=1,
                        ActiveDelay=0,
                        DelayDeactive=0,
                    )
                    if ch347.spi_init(spi_config): # True if successful, False otherwise.
                        self.ch347_device = ch347
                # cannot find wch device, try hid device
                if self.ch347_device is None:
                    try:
                        #HIDAPI
                        from ch347api import SPIDevice, SPIClockFreq
                        self.hid_device = SPIDevice(clock_freq_level=SPIClockFreq.f_60M, is_16bits=False, mode=3, is_MSB=True)
                    except Exception as e:
                        print(e)
            elif platform.system() == "Linux" and os.path.exists("/dev/spidev3.0"):
                try:
                    import spidev
                    spi = spidev.SpiDev()
                    spi.open(3, 0) # bus 3, device 0
                    spi.max_speed_hz = 60000000
                    spi.mode = 0b11
                    spi.bits_per_word = 8
                    spi.lsbfirst = False
                    spi.cshigh = False
                    self.gpio_device = spi
                except Exception as e:
                    print(e)

                
        if self.ch347_device is None and self.hid_device is None and self.gpio_device is None:
            raise ValueError("No device found")
        self.pipeline = BaconWritePipeline(self, self.WriteRead)
        self.pipeline.MAX_LEN = self.MAX_LEN

######## Low Level API ########
    def Close(self):
        if self.gpio_device is not None:
            self.gpio_device.close()
        if self.ch347_device is not None:
            self.ch347_device.close_device()
        if self.hid_device is not None:
            self.hid_device.dev.close()
        self.ch347_device = None
        self.hid_device = None
        self.gpio_device = None

    def Write(self, data: bytes) -> bool:
        if len(data) > self.MAX_LEN:
            raise ValueError("Data length must be less than 0x%04X" % self.MAX_LEN)
        if self.gpio_device is not None:
            self.gpio_device.xfer(data)
            return True
        if self.ch347_device is not None:
            return self.ch347_device.spi_write(0x80, data)
        if self.hid_device is not None:
            return self.hid_device.write_CS1(data) > 0
        raise ValueError("No device found")

    def WriteRead(self, data: bytes) -> bytes:
        if len(data) > self.MAX_LEN:
            raise ValueError("Data length must be less than 0x%04X" % self.MAX_LEN)
        if self.gpio_device is not None:
            return bytes(self.gpio_device.xfer(data))
        if self.ch347_device is not None:
            return bytes(self.ch347_device.spi_write_read(0x80, data))
        if self.hid_device is not None:
            return bytes(self.hid_device.writeRead_CS1(data))
        raise ValueError("No device found")
    
    def PiplelineFlush(self):
        return self.pipeline.Flush()

    def ResetAndDelayNS(self, ns: int, v16bit=b"\x00\x00", v8bit=b"\x00", phi=False, req=False, wr=True, rd=True, cs1=True, cs2=True) -> BaconWritePipeline:
        # 1clk=16.67ns
        # 1reset=35clk
        for i in range(ns//int(16.6*35)+1):
            if self.pipeline.Write(make_cart_30bit_write_command(
                phi=phi, req=req, wr=wr, rd=rd, cs1=cs1, cs2=cs2,
                v16bit=v16bit, v8bit=v8bit, postfunc=echo_all
            )).IsEmpty():
                return self.pipeline
        return self.pipeline

    def PowerControl(self, v3_3v: bool, v5v: bool) -> BaconWritePipeline:
        if v3_3v and v5v:
            raise ValueError("v3_3v and v5v can't be both enabled")
        if v3_3v:
            self.power = 3
        elif v5v:
            self.power = 5
        else:
            self.power = 0
        # return self.WriteRead(make_power_control_command(not v3_3v, v5v))
        return self.pipeline.Write(make_power_control_command(not v3_3v, v5v, postfunc=echo_all))

######## High Level API ########

    def AGBReadROM(self, addr: int, size: int, reset=True, callback=None) -> bytes:
        if size % 2 != 0:
            raise ValueError("Size must be a multiple of 2")
        if addr % 2 != 0:
            raise ValueError("Address must be a multiple of 2")
        if addr + size > ROM_MAX_SIZE:
            #raise ValueError("Address + Size must be less than 0x2000000 address:0x%08X size:0x%08X" % (addr, size))
            pass
        if self.power != 3:
            raise ValueError("Power must be 3.3v")
        # prepare chip
        ## to halfword
        addr = addr // 2
        size = size // 2
        self.pipeline.Write(make_cart_30bit_write_command(
            phi=False, req=False, 
            wr=True, rd=True, 
            cs1=True, cs2=True, 
            v16bit=bytes([addr & 0xFF, (addr >> 8) & 0xFF]), v8bit=bytes([(addr >> 16) & 0xFF]), postfunc=echo_all
        ))
        self.pipeline.Write(make_gba_rom_cs_write(cs=False, postfunc=echo_all)).Flush()
        lowaddr = addr & 0xFFFF
        highaddr = (addr >> 16) & 0xFF
        # if lowaddr+1 == 0x10000, highaddr+1, and reset lowaddr
        # prepare WriteRead stream
        readbytes = []
        cycle_times = 0
        MAX_TIMES = self.MAX_LEN//(len(make_rom_read_cycle_command(times=1))+1)
        cnt = 0
        for i in range(size):
            cycle_times += 1
            lowaddr += 1
            cnt += 2
            if callback is not None and cnt != size*2:
                callback(cnt, readbytes)
            if lowaddr == 0x10000:
                if cycle_times > 0:
                    ret = self.WriteRead(make_rom_read_cycle_command(times=cycle_times))
                    exteds = extract_read_cycle_data(ret, times=cycle_times)
                    for exted in exteds:
                        readbytes.append(exted >> 8)
                        readbytes.append(exted & 0xFF)
                    cycle_times = 0
                highaddr += 1
                lowaddr = 0
                if highaddr <= 0xFF:
                    # cs1 re-falling?
                    self.WriteRead(make_cart_30bit_write_command(
                        phi=False, req=False, 
                        wr=True, rd=True, 
                        cs1=False, cs2=True, 
                        v16bit=b"\x00\x00", v8bit=bytes([highaddr])
                    ))
            if cycle_times == MAX_TIMES or i == size - 1 and cycle_times > 0:
                ret = self.WriteRead(make_rom_read_cycle_command(times=cycle_times))
                exteds = extract_read_cycle_data(ret, times=cycle_times)
                for exted in exteds:
                    readbytes.append(exted >> 8)
                    readbytes.append(exted & 0xFF)
                cycle_times = 0
        if callback is not None:
            callback(cnt, readbytes)
        # reset chip
        if reset:
            self.WriteRead(make_cart_30bit_write_command(
                phi=False, req=False, 
                wr=True, rd=True, 
                cs1=True, cs2=True, 
                v16bit=b"\x00\x00", v8bit=b"\x00"
            ))
        return bytes(readbytes)

    def ResetChip(self) -> BaconWritePipeline:
        if self.power != 3:
            raise ValueError("Power must be 3.3v")
        return self.pipeline.Write(make_cart_30bit_write_command(
            phi=False, req=False, 
            wr=True, rd=True, 
            cs1=True, cs2=True, 
            v16bit=b"\x00\x00", v8bit=b"\x00", postfunc=echo_all
        ))
    
    def AGBWriteROMSequential(self, addr, data: bytes, reset=True, callback=None) -> BaconWritePipeline:
        if addr % 2 != 0:
            raise ValueError("Address must be a multiple of 2")
        if len(data) % 2 != 0:
            raise ValueError("Data length must be a multiple of 2")
        if self.power != 3:
            raise ValueError("Power must be 3.3v")
        addr = addr // 2
        # prepare chip
        self.pipeline.Write(
            make_cart_30bit_write_command(
                phi=False, req=False, 
                wr=True, rd=True, 
                cs1=True, cs2=True, 
                v16bit=bytes([addr & 0xFF, (addr >> 8) & 0xFF]), v8bit=bytes([(addr >> 16) & 0xFF]),
                postfunc=echo_all
            )
        )
        self.pipeline.Write(make_gba_rom_cs_write(cs=False, postfunc=echo_all))
        lowaddr = addr & 0xFFFF
        highaddr = (addr >> 16) & 0xFF
        cnt = 0
        for i in range(0, len(data), 2):
            self.pipeline.Write(make_rom_write_cycle_command_sequential(datalist=[int.from_bytes(data[i:i+2], byteorder='little')], postfunc=echo_all))
            lowaddr += 1
            cnt += 2
            if callback is not None and cnt != len(data):
                callback(cnt, None)
            if lowaddr == 0x10000:
                highaddr += 1
                lowaddr = 0
                if highaddr <= 0xFF:
                    # cs1 re-falling?
                    self.pipeline.Write(make_cart_30bit_write_command(
                        phi=False, req=False, 
                        wr=True, rd=True, 
                        cs1=False, cs2=True, 
                        v16bit=b"\x00\x00", v8bit=bytes([highaddr]), postfunc=echo_all
                    ))
        if callback is not None:
            callback(cnt, None)
        # reset chip.
        if reset:
            self.pipeline.Write(make_cart_30bit_write_command(
                phi=False, req=False, 
                wr=True, rd=True, 
                cs1=True, cs2=True, 
                v16bit=b"\x00\x00", v8bit=b"\x00", postfunc=echo_all
            ))
        return self.pipeline

    def AGBWriteROMWithAddress(self, commands: list, callback=None) -> BaconWritePipeline:
        if self.power != 3:
            raise ValueError("Power must be 3.3v")
        cnt = 0
        # addr这里使用绝对地址，需要//2
        # 如果commands中的data为bytes，需要转换为int（小端）
        for i in range(len(commands)):
            if type(commands[i][1]) == bytes:
                commands[i] = (commands[i][0]//2, int.from_bytes(commands[i][1], byteorder='little'))
            else:
                commands[i] = (commands[i][0]//2, commands[i][1])
        for i in range(len(commands)):
            self.pipeline.Write(make_rom_write_cycle_command_with_addr(addrdatalist=[commands[i]], postfunc=echo_all))
            cnt += 1
            if callback is not None and cnt != len(commands):
                callback(cnt, None)
        if callback is not None:
            callback(cnt, None)
        # reset chip
        self.pipeline.Write(make_cart_30bit_write_command(
            phi=False, req=False, 
            wr=True, rd=True, 
            cs1=True, cs2=True, 
            v16bit=b"\x00\x00", v8bit=b"\x00", postfunc=echo_all
        ))
        return self.pipeline

    def AGBReadRAM(self, addr: int, size: int, bankswitch=None, callback=None) -> bytes:
        if addr + size > RAM_MAX_SIZE:
            raise ValueError("Address + Size must be less than 0x20000")
        if addr + size > RAM_MAX_SIZE/2 and bankswitch is None:
            raise ValueError("Address + Size must be less than 0x10000 or bankswitch must be provided address:0x%08X size:0x%08X" % (addr, size))
        if self.power != 3:
            raise ValueError("Power must be 3.3v")
        # prepare chip
        self.pipeline.Write(make_cart_30bit_write_command(
            phi=False, req=False, 
            wr=True, rd=False, 
            cs1=True, cs2=False,
            v16bit=bytes([addr & 0xFF, (addr >> 8) & 0xFF]), v8bit=b"\x00", postfunc=echo_all
        )).Flush()
        readbytes = []
        cycle_times = 0
        MAX_TIMES = self.MAX_LEN//(len(make_ram_read_cycle_command(addr=0, times=1))+1)
        cnt = 0
        start_addr = addr
        for i in range(size):
            cycle_times += 1
            cnt += 1
            if callback is not None and cnt != size:
                callback(cnt, readbytes)
            if cycle_times == MAX_TIMES or i == size - 1 and cycle_times > 0:
                ret = self.WriteRead(make_ram_read_cycle_command(addr=start_addr, times=cycle_times))
                exteds = extract_ram_read_cycle_data(ret, times=cycle_times)
                for exted in exteds:
                    readbytes.append(exted)
                start_addr += cycle_times
                cycle_times = 0
        if callback is not None:
            callback(cnt, readbytes)
        # reset chip
        self.WriteRead(make_cart_30bit_write_command(
            phi=False, req=False, 
            wr=True, rd=True, 
            cs1=True, cs2=True, 
            v16bit=b"\x00\x00", v8bit=b"\x00"
        ))
        return bytes(readbytes)

    def AGBWriteRAM(self, addr: int, data: bytes, bankswitch=None, callback=None) -> bool:
        size = len(data)
        if addr + size > RAM_MAX_SIZE:
            raise ValueError("Address + Size must be less than 0x20000")
        if addr + size > RAM_MAX_SIZE/2 and bankswitch is None:
            raise ValueError("Address + Size must be less than 0x10000 or bankswitch must be provided address:0x%08X size:0x%08X" % (addr, size))
        if self.power != 3:
            raise ValueError("Power must be 3.3v")
        readbytes = []
        cycle_times = 0
        MAX_TIMES = self.MAX_LEN//(len(make_ram_write_cycle_command(addr=0, data=b"\00"))+1)
        cnt = 0
        start_addr = addr
        for i in range(size):
            cycle_times += 1
            cnt += 1
            if callback is not None and cnt != size:
                callback(cnt, readbytes)
            if cycle_times == MAX_TIMES or i == size - 1 and cycle_times > 0:
                ret = self.WriteRead(make_ram_write_cycle_command(addr=start_addr, data=data[start_addr-addr:start_addr-addr+cycle_times]))
                readbytes = readbytes + ([0]*cycle_times)
                start_addr += cycle_times
                cycle_times = 0
        if callback is not None:
            callback(cnt, readbytes)
        # reset chip
        self.WriteRead(make_cart_30bit_write_command(
            phi=False, req=False, 
            wr=True, rd=True, 
            cs1=True, cs2=True, 
            v16bit=b"\x00\x00", v8bit=b"\x00"
        ))
        return bytes(readbytes)

    def AGBWriteRAMWithAddress(self, commands: list, reset=True, callback=None) -> BaconWritePipeline:
        if self.power != 3:
            raise ValueError("Power must be 3.3v")
        cnt = 0
        for i in range(len(commands)):
            self.pipeline.Write(make_ram_write_cycle_with_addr(addrdatalist=[commands[i]], postfunc=echo_all))
            cnt += 1
            if callback is not None and cnt != len(commands):
                callback(cnt, None)
        if callback is not None:
            callback(cnt, None)
        # reset chip
        if reset:
            self.pipeline.Write(make_cart_30bit_write_command(
                phi=False, req=False, 
                wr=True, rd=True, 
                cs1=True, cs2=True, 
                v16bit=b"\x00\x00", v8bit=b"\x00", postfunc=echo_all
            ))
        return self.pipeline
    
    def AGBCustomWriteCommands(self, commands: list, callback=None) -> bool:
        pass

    def AGBGPIOEnable(self) -> BaconWritePipeline:
        if self.power != 3:
            raise ValueError("Power must be 3.3v")
        return self.AGBWriteROMSequential(self.GPIO_REG_RE, b"\x01")
    
    def AGBGPIOSetDirection(self, direction: int) -> BaconWritePipeline:
        if self.power != 3:
            raise ValueError("Power must be 3.3v")
        return self.AGBWriteROMSequential(self.GPIO_REG_CNT, bytes([direction]))
    
    def AGBGPIORead(self) -> int:
        if self.power != 3:
            raise ValueError("Power must be 3.3v")
        return self.AGBReadROM(self.GPIO_REG_DAT, 1)[0]

    def DMGReadROM(self, addr: int, size: int, reset=True, callback=None) -> bytes:
        pass