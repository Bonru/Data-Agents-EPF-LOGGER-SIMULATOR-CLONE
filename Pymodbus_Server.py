#!/bin/python

import logging
import pandas as pd
from pyModbusTCP.server import ModbusServer, DataBank

logging.basicConfig()
logging.getLogger('pyModbusTCP.server').setLevel(logging.DEBUG)
df = pd.read_excel('Datalogger_data_28_11_2024_1.xlsx')

class MyDataBank(DataBank):
    def __init__(self):
        super().__init__()
        self.leitura = 0

    def sheet_values(self, n_leitura, df):
        row = df.iloc[n_leitura].to_dict()
        return row
    
    def treat_data(self, value):
        """Converte uma string com vírgula para um inteiro."""
        if isinstance(value, str):
            value = value.replace(',', '.')
        if int(float(value) *10) < 0:
            return 0
        else:
            return int(float(value) *10)

    def new_values(self):
        parametros = self.sheet_values(self.leitura, df)
        ghi = abs(self.treat_data(parametros['ghi'])) # Register 0
        poa_1 = self.treat_data(parametros['poa_1']) # Register 1
        ref_30_temp = self.treat_data(parametros['ref_30_temp']) # Register 2
        temp_1 = self.treat_data(parametros['temp_1']) # Register 3
        umidade_higromet = self.treat_data(parametros['umidade_higromet']) # Register 4
        v_vento = self.treat_data(parametros['v_vento']) # Register 5
        print(ghi, poa_1, ref_30_temp, temp_1, umidade_higromet, v_vento)
        self.leitura += 1  #atualiza numero da leitura
        return [ghi, poa_1, ref_30_temp, temp_1, umidade_higromet, v_vento]

    def get_holding_registers(self, address, number=1, srv_info=None):
        try:
            new_values = self.new_values()
            
            print(new_values)
            for i in range(len(new_values)):
                self._h_regs[i] = new_values[i]
            return [self._h_regs[i] for i in range(address, address + number)]
        
        except KeyError:
            return

if __name__ == "__main__":
    server = ModbusServer("localhost", 552, data_bank=MyDataBank())

    try:
        print("Ligando servidor...")
        server.start()
        print("Desligando servidor...\n")
    
    except:
        print("Desligando servidor...")
        server.stop()
        print("Servidor desligado")
