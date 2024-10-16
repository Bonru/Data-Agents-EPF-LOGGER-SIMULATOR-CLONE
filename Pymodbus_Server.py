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
        umi = int(normalvariate(25, 2)) #Register 1
        ten = int(normalvariate(350, 10)) #Register 2
        pot = int(normalvariate(770, 12)) #Register 3
        return [tem, umi, ten, pot]

    def get_holding_registers(self, address, number=1, srv_info=None):
        try:
            new_values = MyDataBank.new_values()
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
        print("Servidor ligado\n")
    
    except:
        print("Desligando servidor...")
        server.stop()
        print("Servidor desligado")

"""
try:
    print("Ligando servidor...")
    server.start()
    print("Servidor ligado\n")
    #valor inicial do registrador
    Temperatura, Umidade, Tensao, Potencia = [0, "Temperatura", "°C"], [0, "Umidade", "%"], [0, "Tensão", "kV"], [0, "Potência", "kW"]
    
    while True:

        server.data_bank.set_holding_registers(0, [float(normalvariate(65, 2))])        #Temperatura
        server.data_bank.set_holding_registers(1, [float(normalvariate(25, 2))])        #Umidade
        server.data_bank.set_holding_registers(2, [float(normalvariate(350, 10))])      #Tensão
        server.data_bank.set_holding_registers(3, [float(normalvariate(770, 12))])      #Potência

        Temperatura[0] = server.data_bank.get_holding_registers(0)
        Umidade[0] = server.data_bank.get_holding_registers(1)
        Tensao[0] = server.data_bank.get_holding_registers(2)
        Potencia[0] = server.data_bank.get_holding_registers(3)

        lista = [Temperatura, Umidade, Tensao, Potencia]

        for i in lista:
            print(f"Valor de {i[1]} atualizado para: {i[0][0]:.1f} {i[2]}")
        
        print("")
        sleep(1.5)

except:
    print("Desligando servidor...")
    server.stop()
    print("Servidor desligado")
"""