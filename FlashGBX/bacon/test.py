# -*- coding: utf-8 -*-
# bacon
# Author: ChisBread (github.com/ChisBread)

import time
import os
import sys
# append path
from .bacon import BaconDevice
from .command import *

bacon_dev = BaconDevice()

def open_current_dif(filename, mode):
    return open(os.path.join(os.path.dirname(__file__), filename), mode)

def bacon_write_test():
    # 11: 5v
    # 00: 3.3v
    print("[SPI] write power control command")
    powercmd = make_power_control_command(not_v3_3v=False, v5v=False)
    print("[SPI] write bytes %s" % bytes2command(powercmd))
    ret = bacon_dev.Write(powercmd)
    #True if successful, False otherwise.
    print("[SPI] write result %s" % ret)
    print("[SPI] write cart 30bit write command")
    pintestcmd = make_cart_30bit_write_command(
        phi=False, req=False, 
        wr=False, rd=True, 
        cs1=False, cs2=True, 
        v16bit=b"\xFF\xFF", v8bit=b"\xFF"
    )
    print("[SPI] write bytes %s" % bytes2command(pintestcmd))
    bacon_dev.Write(pintestcmd)
    print("[SPI] write test done")
    
def bacon_read_test_30bit():
    power_read_cmd = make_power_read_command()
    cart_read_cmd = make_cart_30bit_read_command()
    # 测试3.3v
    print("[SPI] write power control command")
    bacon_dev.Write(make_power_control_command(not_v3_3v=False, v5v=False))
    ret = bacon_dev.WriteRead(power_read_cmd)
    print("[SPI] read bytes %s, expected %s" % (bytes2command(ret)[::-1], "00"))
    ###### 测试读取卡带数据 ######
    bacon_dev.Write(make_cart_30bit_write_command(
        phi=False, req=False, 
        wr=True, rd=True, 
        cs1=True, cs2=True, 
        v16bit=b"\x00\x00", v8bit=b"\x00"
    ))
    ## CS1上升沿，写入低位地址0x0000
    bacon_dev.Write(make_gba_rom_cs_write(cs=False))
    ret = bacon_dev.WriteRead(cart_read_cmd)
    print(extract_cart_30bit_read_data(ret))
    readbytes = []
    avg_start = time.time()
    start = time.time()
    # 每0x10000，需要对v8bit+1
    # 所以0x10000需要能被BULK_SIZE整除
    high_addr = 0x00
    BULK_SIZE = 512
    TOTAL_SIZE = 0x800000 # 16MB
    if TOTAL_SIZE % BULK_SIZE != 0:
        raise ValueError("TOTAL_SIZE must be a multiple of BULK_SIZE")
    if 0x10000 % BULK_SIZE != 0:
        raise ValueError("BULK_SIZE must be a factor of 0x10000")
    readcyclecmd = make_rom_read_cycle_command(times=BULK_SIZE)
    for i in range(TOTAL_SIZE//BULK_SIZE):
        ret = bacon_dev.WriteRead(readcyclecmd)
        exteds = extract_read_cycle_data(ret, times=BULK_SIZE)
        for idx, exted in enumerate(exteds):
            num = i * BULK_SIZE + idx
            readbytes.append(exted["v16bit"] >> 8)
            readbytes.append(exted["v16bit"] & 0xFF)
            if num < 2:
                print(f"header bytes: {hex(readbytes[-2])[2:].rjust(2, '0')}, {hex(readbytes[-1])[2:].rjust(2, '0')}")
            if num % 0x10000 == 0x10000 - 1:
                high_addr += 1
                bacon_dev.Write(make_cart_30bit_write_command(
                    phi=False, req=False, 
                    wr=True, rd=True, 
                    cs1=False, cs2=True, 
                    v16bit=b"\x00\x00", v8bit=bytes([high_addr])
                ))
            if num % 0x1000 == 0x1000 - 1:
                # print(f"[SPI] high address: 0x{hex(high_addr)[2:].rjust(2, '0')}")
                # print(f"[SPI] read 0x2000 bytes in {time.time() - start}s speed(KB/s): {0x2000 / (time.time() - start) / 1024}")
                print(f"\rAddress:0x{num+1:06X} Speed(KB/s):{(0x2000 / (time.time() - start) / 1024):.2f}", end="")
                start = time.time()
    print(f"\n[SPI] read {hex(TOTAL_SIZE*2)} bytes in {time.time() - avg_start}s speed(KB/s): {TOTAL_SIZE*2 / (time.time() - avg_start) / 1024}")
    ch347.spi_change_cs(0x00)
    with open_current_dif("gba_rom.bin", "wb") as f:
        f.write(bytes(readbytes))
   
def bacon_read_test_16bit():
    power_read_cmd = make_power_read_command()
    cart_read_cmd = make_cart_30bit_read_command()
    # 测试3.3v
    print("[SPI] write power control command")
    bacon_dev.Write(make_power_control_command(not_v3_3v=False, v5v=False))
    ret = bacon_dev.WriteRead(power_read_cmd)
    print("[SPI] read bytes %s, expected %s" % (bytes2command(ret)[::-1], "00"))
    ###### 测试读取卡带数据 ######
    bacon_dev.Write(make_cart_30bit_write_command(
        phi=False, req=False, 
        wr=True, rd=True, 
        cs1=True, cs2=True, 
        v16bit=b"\x00\x00", v8bit=b"\x00"
    ))
    ## CS1上升沿，写入低位地址0x0000
    bacon_dev.Write(make_gba_rom_cs_write(cs=False))
    ret = bacon_dev.WriteRead(cart_read_cmd)
    print(extract_cart_30bit_read_data(ret))
    readbytes = []
    avg_start = time.time()
    start = time.time()
    # 每0x10000，需要对v8bit+1
    # 所以0x10000需要能被BULK_SIZE整除
    high_addr = 0x00
    MAX_BULK_SIZE = 0x1000//(len(make_rom_read_cycle_command(times=1))) # buffer不能超过0x1000，但尽量大一点
    bulk_list = [MAX_BULK_SIZE]*(0x10000//MAX_BULK_SIZE) + [0x10000%MAX_BULK_SIZE]
    # print(f"[SPI] bulk list: {bulk_list}")
    TOTAL_SIZE = 0x800000 # 16MB
    for i in range(TOTAL_SIZE//0x10000):
        # readcyclecmd = make_rom_read_cycle_command(times=MAX_BULK_SIZE)
        # ret = bacon_dev.WriteRead(readcyclecmd)
        # exteds = extract_read_cycle_data(ret, times=dynamic_bulk_size)
        for j in range(len(bulk_list)):
            readcyclecmd = make_rom_read_cycle_command(times=bulk_list[j])
            ret = bacon_dev.WriteRead(readcyclecmd)
            exteds = extract_read_cycle_data(ret, times=bulk_list[j])
            for idx, exted in enumerate(exteds):
                readbytes.append(exted >> 8)
                readbytes.append(exted & 0xFF)
                if num < 2:
                    print(f"header bytes: {hex(readbytes[-2])[2:].rjust(2, '0')}, {hex(readbytes[-1])[2:].rjust(2, '0')}")
                if num % 0x10000 == 0x10000 - 1:
                    high_addr += 1
                    bacon_dev.Write(make_cart_30bit_write_command(
                        phi=False, req=False, 
                        wr=True, rd=True, 
                        cs1=False, cs2=True, 
                        v16bit=b"\x00\x00", v8bit=bytes([high_addr])
                    ))
                if num % 0x1000 == 0x1000 - 1:
                    # print(f"[SPI] high address: 0x{hex(high_addr)[2:].rjust(2, '0')}")
                    # print(f"[SPI] read 0x2000 bytes in {time.time() - start}s speed(KB/s): {0x2000 / (time.time() - start) / 1024}")
                    print(f"\rAddress:0x{num+1:06X} Speed(KB/s):{(0x2000 / (time.time() - start) / 1024):.2f}", end="")
                    start = time.time()
                num += 1
    print(f"\n[SPI] read {hex(TOTAL_SIZE*2)} bytes in {time.time() - avg_start}s speed(KB/s): {TOTAL_SIZE*2 / (time.time() - avg_start) / 1024}")
    with open_current_dif("gba_rom.bin", "wb") as f:
        f.write(bytes(readbytes))

def bacon_test_api():
    bacon_dev.PowerControl(v3_3v=True, v5v=False).Flush()
    bacon_dev.AGBWriteRAM(addr=0, data=open_current_dif("gba_bak_ram.bin", "rb").read())
    TOTAL_BYTE_SIZE = 0x800000*2 # 16MB
    start = time.time()
    avg_start = time.time()
    first = True
    last_addr = 0
    def callback(addr, data):
        nonlocal first, start, avg_start, last_addr
        if addr == 0 or (addr % 0x1000 != 0 and addr != TOTAL_BYTE_SIZE):
            return
        if first:
            print(f"header bytes: {hex(data[0])[2:].rjust(2, '0')}, {hex(data[1])[2:].rjust(2, '0')}")
            first = False
            last_addr = 0
        if addr == TOTAL_BYTE_SIZE:
            print(f"\n[SPI] read {hex(TOTAL_BYTE_SIZE)} bytes in {time.time() - avg_start}s speed(KB/s): {TOTAL_BYTE_SIZE / (time.time() - avg_start) / 1024}")
        else:
            delta = addr - last_addr
            print(f"\rAddress:0x{addr:06X} Speed(KB/s):{(delta / (time.time() - start) / 1024):.2f}", end="")
            start = time.time()
            last_addr = addr
    ## 读取卡带存档
    TOTAL_BYTE_SIZE = 0x8000 # 32KB
    start = time.time()
    avg_start = time.time()
    first = True
    ram = bacon_dev.AGBReadRAM(addr=0, size=TOTAL_BYTE_SIZE, callback=callback)
    with open_current_dif("gba_ram.bin", "wb") as f:
        f.write(ram)
    ## 写入卡带存档
    new_ram = bytes([0xFF]*TOTAL_BYTE_SIZE)
    start = time.time()
    avg_start = time.time()
    first = True
    ret = bacon_dev.AGBWriteRAM(addr=0, data=new_ram, callback=callback)
    TOTAL_BYTE_SIZE = 0x8000 # 32KB
    start = time.time()
    avg_start = time.time()
    first = True
    new_ram_ret = bacon_dev.AGBReadRAM(addr=0, size=TOTAL_BYTE_SIZE, callback=callback)
    #### 判断是否写入成功
    if new_ram_ret == new_ram and new_ram_ret != ram:
        print("[SPI] write and read ram success")
    else:
        print("[SPI] write and read ram failed head 10 bytes: %s, %s" % (new_ram[:10], new_ram_ret[:10]))
    ## 恢复卡带存档
    bacon_dev.AGBWriteRAM(addr=0, data=ram)
    ## 读取卡带ROM
    TOTAL_BYTE_SIZE = 0x800000*2 # 16MB
    start = time.time()
    avg_start = time.time()
    first = True
    rom = bacon_dev.AGBReadROM(addr=0, size=TOTAL_BYTE_SIZE, callback=callback)
    with open_current_dif("gba_rom.bin", "wb") as f:
        f.write(rom)
if __name__ == "__main__":
    # print(ch347.get_version())
    # bacon_read_test_30bit()
    # bacon_read_test_16bit()
    bacon_test_api()
    bacon_dev.Close()