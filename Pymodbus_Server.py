#!/bin/python

from pyModbusTCP.server import ModbusServer, DataBank
from time import sleep
from random import normalvariate
import logging

logging.basicConfig()
logging.getLogger('pyModbusTCP.server').setLevel(logging.DEBUG)

class MyDataBank(DataBank):
    def __init__(self):
        super().__init__()

    def new_values():
        tem = int(normalvariate(65, 2)) #Register 0
        umi = int(normalvariate(45, 5)) #Register 1
        ten = int(normalvariate(350, 3)) #Register 2
        pot = int(normalvariate(770, 4)) #Register 3
        vent = int(normalvariate(4, .5)) #Register 4
        irrad = int(normalvariate(1100, 10)) #Register 5
        return [tem, umi, ten, pot, vent, irrad]

    def get_holding_registers(self, address, number=1, srv_info=None):
        try:
            new_values = MyDataBank.new_values()
            print(new_values)
            for i in range(len(new_values)):
                self._h_regs[i] = new_values[i]
            return[self._h_regs[i] for i in range(address, address + number)]
        
        except KeyError:
            return
     
if __name__ == "__main__":
    server = ModbusServer("localhost", 8080, data_bank=MyDataBank())

    try:
        print("Ligando servidor...")
        server.start()
        print("Desligando servidor...\n")
    
    except:
        print("Desligando servidor...")
        server.stop()
        print("Servidor desligado")
