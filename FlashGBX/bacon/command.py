# -*- coding: utf-8 -*-
# bacon
# Author: ChisBread (github.com/ChisBread)

# 命令结束后需要跟一个0bit

# -- | Command Value (5 bits) | Command Name | Description | Input Bits | Input Description | Output Bits | Output Description |
# -- |------------------------|--------------|-------------|------------|-------------------|-------------|--------------------|
# -- | 00001                 | CART_30BIT_WRITE  | 30位数据写入 | 30         | 30位数据 | -           | 无返回 |
# -- | 00010                 | CART_30BIT_READ   | 30位数据读取 | -          | 无输入 | 30          | 30位数据 |
# -- | 00011                 | MOD_WRITE    | 控制电源     | 2          | 10: 都不启用<br>00: 启用3.3v(GBA)<br>11: 启用5v(GB)<br>01: 无效 | -           | 无返回 |
# -- | 00100                 | MOD_READ     | 读取电源状态 | -          | 无输入 | 2           | 0: 都不启用<br>01: 启用3.3v(GBA)<br>10: 启用5v(GB)<br>11: 无效 |
# -- | 00101                 | GBA_WR/RD_WRITE | GBA 2bit寄存器操作，每次上升沿会使锁存的16bit地址自增1 | 2          | 0: 无效<br>01: 启用WR<br>10: 启用RD<br>11: 默认 | -           | 无返回 |
# -- | 00110                 | GBA_WR/RD_READ | 读取GBA 2bit寄存器状态 | -          | 无输入 | 2           | 0: 无效<br>01: 启用WR<br>10: 启用RD<br>11: 默认 |
# -- | 00111                 | GBA_ROM_EN_WRITE | GBA ROM使能 | 1         | 使能 | -           | 无返回 |
# -- | 01000                 | GBA_ROM_ADDR_READ | 读取GBA R高8位地址 | -          | 无输入 | 8          | 8位数据 |
# -- | 01001                 | GBA_ROM_DATA_WRITE | GBA ROM写16位数据 | 16         | 16位数据 | -           | 无返回 |
# -- | 01010                 | GBA_ROM_DATA_READ | 读取GBA ROM数据 | -          | 无输入 | 16          | 16位数据 |
# -- | 01011                 | GBA_ROM_DATA_READ_FLIP | 读取GBA ROM数据 | -          | 无输入 | 16          | 16位数据 |
# -- | 01100                 | GBA_ROM_DATA_WRITE_FLIP | GBA ROM写16位数据 | 16         | 16位数据 | -           | 无返回 |
# -- | 10000 - 11111         | RESERVED     | 预留命令     | -          | -                 | -           | -                  |
import traceback
from bitarray import bitarray

def command2bytes(command, endclk=True) -> bytes:
    if isinstance(command, str):
        command = bitarray(command)
    if endclk and len(command) % 8 == 0:
        # end clk cycle
        command += "0"
    if len(command) % 8:
        command += bitarray("0" * (8 - len(command) % 8))
    return command.tobytes()

def echo_all(data):
    return data

def bytes2command(data: bytes):
    ret = bitarray()
    ret.frombytes(data)
    return ret

def make_power_control_command(
    # 3.3v低电平有效, 5v高电平有效
    not_v3_3v: bool = True, v5v: bool = False, postfunc=command2bytes) -> bytes:
    # 不能两个都有效
    if not not_v3_3v and v5v:
        raise ValueError("v3_3v and v5v can't be both enabled")
    command = "00011"
    command += "1" if v5v else "0"
    command += "1" if not_v3_3v else "0"
    return postfunc(command)

def make_power_read_command(postfunc=command2bytes) -> bytes:
    command = "00100"
    return postfunc(command)

def make_cart_30bit_write_command(
    phi: bool = False, req: bool = False,
    # 低电平有效
    wr: bool = True, rd: bool = True,
    cs1: bool = True, cs2: bool = True, 
    # 小端模式
    v16bit: bytes = b"\00\00", v8bit: bytes = b"\00", postfunc=command2bytes) -> bytes:
    command = "00001"
    command += "1" if req else "0"
    command += "1" if cs2 else "0"
    if len(v16bit) != 2:
        raise ValueError("v16bit must be 2 bytes")
    if len(v8bit) != 1:
        raise ValueError("v8bit must be 1 byte")
    command += bin(v8bit[0])[2:].rjust(8, "0")
    command += bin(v16bit[1])[2:].rjust(8, "0")
    command += bin(v16bit[0])[2:].rjust(8, "0")
    command += "1" if cs1 else "0"
    command += "1" if rd else "0"
    command += "1" if wr else "0"
    command += "1" if phi else "0"
    return postfunc(command)

def make_cart_30bit_read_command(postfunc=command2bytes) -> bytes:
    command = "00010"
    command += "0" * 30
    return postfunc(command)

def make_gba_wr_rd_write_command(
    wr: bool = False, rd: bool = False, postfunc=command2bytes) -> bytes:
    command = "00101"
    command += "1" if wr else "0"
    command += "1" if rd else "0"
    return postfunc(command)

def extract_cart_30bit_read_data(data: bytes) -> dict:
    if len(data) != 5:
        raise ValueError("data must be 5 bytes, but got %d" % len(data))
    ret = {}
    # 输出和输出是反的，且有6bit无效数据，所以
    # 000000 00 | 10 010101 | 011010101001010101100010
    ret["phi"] = bool(data[0] >> 1 & 1)
    ret["wr"] = bool(data[0] & 1)
    ret["rd"] = bool(data[1] >> 7)
    ret["cs1"] = bool(data[1] >> 6 & 1)
    # 16bit数据, 其中6bit在data[1]的低位, 2bit在data[2]的高位
    v16bitB0 = ((data[1] & 0b00111111) << 2) | (data[2] >> 6)
    # 16bit数据, 其中6bit在data[2]的低位, 2bit在data[3]的高位
    v16bitB1 = ((data[2] & 0b00111111) << 2) | (data[3] >> 6)
    # 8bit数据, 其中6bit在data[3]的低位, 2bit在data[4]的高位
    v8bit = ((data[3] & 0b00111111) << 2) | (data[4] >> 6)
    # 3byte都需要按位翻转
    # v16bitB0 = reverse_bits(v16bitB0)
    # v16bitB1 = reverse_bits(v16bitB1)
    v8bit = reverse_bits(v8bit)
    # ret["v16bit"] = (v16bitB0 << 8) | v16bitB1
    ret["v16bit"] = reverse_bits_16bit((v16bitB1 << 8) | v16bitB0)
    ret["v8bit"] = v8bit
    ret["cs2"] = bool(data[4] >> 5 & 1)
    ret["req"] = bool(data[4] >> 4 & 1)
    return ret


def make_v16bit_data_write_command(data: int, flip=False, postfunc=command2bytes) -> bytes:
    if data > 0xFFFF:
        raise ValueError("data must be less than 0xFFFF")
    command = ("01100" if flip else "01001") + bin(data)[2:].rjust(16, "0")
    return postfunc(command)

def make_gba_rom_data_write_command(data: int, flip=False, postfunc=command2bytes) -> bytes:
    return make_v16bit_data_write_command(data, flip, postfunc)

__readcyclecmd_30bit = "0".join([
    make_gba_wr_rd_write_command(wr=True, rd=False, postfunc=echo_all),
    make_cart_30bit_read_command(postfunc=echo_all),
    make_gba_wr_rd_write_command(wr=True, rd=True, postfunc=echo_all)])
def make_rom_read_cycle_command_30bit(times=1, postfunc=command2bytes) -> bytes:
    # 1. pull down RD
    # 2. read data
    # 3. pull up RD
    return postfunc("0".join([__readcyclecmd_30bit for i in range(times)]))

def extract_read_cycle_data_30bit(data: bytes, times=1):
    ret = []
    if len(data)*8 < (len(__readcyclecmd_30bit)+1) * times:
        raise ValueError("data must be %d bytes, but got %d" % ((len(__readcyclecmd_30bit)+1) * times, len(data)*8))
    bytesstr = bytes2command(data)
    # 每隔len(__readcyclecmd_30bit)+1bit取一次数据
    for i in range(0, len(bytesstr), len(__readcyclecmd_30bit) + 1):
        one = command2bytes( bytesstr[i + 8: i + len(__readcyclecmd_30bit) + 1], endclk=False)
        ret.append(extract_cart_30bit_read_data(one[:len(one)-1]))
        if len(ret) >= times:
            break
    return ret

def make_gba_rom_data_read_command(flip=False, postfunc=command2bytes) -> bytes:
    command = "0101" + ("1" if flip else "0") + "0" * 16
    return postfunc(command)
    
def extract_gba_rom_read_data(data: bytes) -> int:
    if len(data) < 3:
        raise ValueError("data must be 3 bytes, but got %d" % len(data))
    # 6bit无效数据
    #ret = (reverse_bits(data[0] << 6 | data[1] >> 2) << 8) | reverse_bits(data[1] << 6 | data[2] >> 2)
    ret = reverse_bits_16bit(((data[1] << 6 | data[2] >> 2) << 8) | (data[0] << 6 | data[1] >> 2))
    return ret

__readcyclecmd = "0".join([
    make_gba_wr_rd_write_command(wr=True, rd=False, postfunc=echo_all),
    make_gba_rom_data_read_command(flip=True, postfunc=echo_all),
    #make_gba_wr_rd_write_command(wr=True, rd=True, postfunc=echo_all),
    ])
def make_rom_read_cycle_command(times=1, postfunc=command2bytes) -> bytes:
    # 1. pull down RD
    # 2. read data
    # 3. pull up RD
    return postfunc("0".join([__readcyclecmd for i in range(times)]))

def extract_read_cycle_data(data: bytes, times=1):
    ret = []
    if len(data)*8 < (len(__readcyclecmd)+1) * times:
        raise ValueError("data must be %d bits, but got %d" % ((len(__readcyclecmd)+1) * times, len(data)*8))
    bytesstr = bytes2command(data)
    # 每隔len(__readcyclecmd)+1bit取一次数据
    for i in range(0, len(bytesstr), len(__readcyclecmd) + 1):
        one = command2bytes(bytesstr[i + 8: i + len(__readcyclecmd) + 1], endclk=False)
        ret.append(extract_gba_rom_read_data(one[:len(one)]))
        if len(ret) >= times:
            break
    return ret

def make_rom_write_cycle_command_with_addr(addrdatalist: list, flip=True, postfunc=command2bytes) -> bytes:
    readram = "0".join(["0".join([
        # 1. write addr, reset cs1 and wr
        make_cart_30bit_write_command(
                phi=False, req=False, 
                wr=True, rd=True, 
                cs1=True, cs2=True,
                v16bit=bytes([addr & 0xFF, (addr >> 8) & 0xFF]), v8bit=bytes([(addr >> 16) & 0xFF]), postfunc=echo_all),
        # 2. pull down cs1
        make_gba_rom_cs_write(cs=False, postfunc=echo_all),
        # 3. write data
        make_gba_rom_data_write_command(data, flip=flip, postfunc=echo_all),
        # 4. pull down wr
        # make_gba_wr_rd_write_command(wr=False, rd=True, postfunc=echo_all),
    ]) + ("0"+make_gba_wr_rd_write_command(wr=False, rd=True, postfunc=echo_all) if not flip else "") for addr, data in addrdatalist])
    return postfunc(readram)

def make_rom_write_cycle_command_sequential(datalist: list, flip=True, postfunc=command2bytes) -> bytes:
    readram = "0".join(["0".join([
        # 1. reset wr
        make_gba_wr_rd_write_command(wr=True, rd=True, postfunc=echo_all),
        # 2. write data
        make_gba_rom_data_write_command(data, flip=flip, postfunc=echo_all),
        # 3. pull down wr
        # make_gba_wr_rd_write_command(wr=False, rd=True, postfunc=echo_all),
    ]) + ("0"+make_gba_wr_rd_write_command(wr=False, rd=True, postfunc=echo_all) if not flip else "") for data in datalist])
    return postfunc(readram)

def make_gba_rom_cs_write(cs: bool = True, postfunc=command2bytes) -> bytes:
    command = "00111"
    command += "1" if cs else "0"
    return postfunc(command)

def make_gba_rom_addr_read_command(postfunc=command2bytes) -> bytes:
    command = "01000" + "0" * 8
    return postfunc(command)

def extract_gba_rom_addr_read_data(data: bytes) -> int:
    if len(data) != 2:
        raise ValueError("data must be 2 byte, but got %d" % len(data))
    return reverse_bits((data[0] << 6 ) | (data[1] >> 2))

def make_ram_write_cycle_with_addr(addrdatalist: list, postfunc=command2bytes) -> bytes:
    writeram = "0".join(["0".join(
            [make_cart_30bit_write_command(
                phi=False, req=False, 
                wr=True, rd=True, 
                cs1=True, cs2=False,
                v16bit=bytes([addr & 0xFF, (addr >> 8) & 0xFF]), v8bit=bytes([data]), postfunc=echo_all),
            make_gba_wr_rd_write_command(wr=False, rd=True, postfunc=echo_all)])
        for addr, data in addrdatalist])
    return postfunc(writeram)

def make_ram_write_cycle_command(addr, data, postfunc=command2bytes) -> bytes:
    cmd = "0".join(["0".join(
            [make_cart_30bit_write_command(
                phi=False, req=False, 
                wr=True, rd=True, 
                cs1=True, cs2=False,
                v16bit=bytes([(addr+i) & 0xFF, ((addr+i) >> 8) & 0xFF]), v8bit=bytes([data[i]]), postfunc=echo_all),
            make_gba_wr_rd_write_command(wr=False, rd=True, postfunc=echo_all)])
        for i in range(len(data))])
    return postfunc(cmd)

def make_ram_read_cycle_command(addr=0, times=1, postfunc=command2bytes) -> bytes:
    cmd = "0".join(["0".join([
        make_v16bit_data_write_command(addr+i, postfunc=echo_all),
        make_gba_rom_addr_read_command(postfunc=echo_all)
    ]) for i in range(times)])
    return postfunc(cmd)

__len_of_v16bit_write = len(make_v16bit_data_write_command(data=0, postfunc=echo_all))
__len_of_v8bit_write = len(make_gba_rom_addr_read_command(postfunc=echo_all))
def extract_ram_read_cycle_data(data: bytes, times=1):
    command = bytes2command(data)
    ret = []
    for i in range(0, len(command), __len_of_v16bit_write + __len_of_v8bit_write + 2):
        one = command[i + __len_of_v16bit_write + 1: i + __len_of_v16bit_write + 1 + __len_of_v8bit_write + 1]
        ret.append(extract_gba_rom_addr_read_data(command2bytes(one, endclk=False)))
        if len(ret) >= times:
            break
    return ret

def _reverse_bits(byte):
    byte = ((byte & 0xF0) >> 4) | ((byte & 0x0F) << 4)
    byte = ((byte & 0xCC) >> 2) | ((byte & 0x33) << 2)
    byte = ((byte & 0xAA) >> 1) | ((byte & 0x55) << 1)
    return byte

lookup_rev = [_reverse_bits(i) for i in range(256)]

def reverse_bits(byte):
    return lookup_rev[byte & 0xFF]

def _reverse_bits_16bit(data):
    return (reverse_bits(data & 0xFF) << 8) | reverse_bits(data >> 8)

lookup_rev_16bit = [_reverse_bits_16bit(i) for i in range(0x10000)]

def reverse_bits_16bit(data):
    return lookup_rev_16bit[data & 0xFFFF]


    