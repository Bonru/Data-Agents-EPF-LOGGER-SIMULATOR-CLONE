#!/bin/python

import logging
import pandas as pd
from pyModbusTCP.server import ModbusServer, DataBank
import threading
import time

logging.basicConfig()
logging.getLogger('pyModbusTCP.server').setLevel(logging.DEBUG)
df = pd.read_excel('Datalogger_28_11_2024.xlsx')

class MyDataBank(DataBank):
    def __init__(self):
        super().__init__()
        self.leitura = 0
        self.lista = []
        self.start(0)
        self.update_thread = threading.Thread(target=self.update_values_periodically)
        self.update_thread.daemon = True
        self.update_thread.start()

    def sheet_values(self, n_leitura, df):
        row = df.iloc[n_leitura].to_dict()
        return row
    
    # Função para formatar os dados
    def treat_data(self, value):
        """Converte uma string com vírgula para um inteiro."""
        if isinstance(value, str):
            value = value.replace(',', '.')
        if int(float(value) *10) < 0:
            return 0
        else:
            return int(float(value) *10)
        
    # Função para formatar o timestamp para segundos
    def treat_timestamp(self, value):
        """Converte uma string no modelo XX:XX:XX para um inteiro."""
        hora = value.split(':')
        return int(hora[0])*3600 + int(hora[1])*60 + int(hora[2])
        
    # Função para retornar os novos valores da proxima consulta na planilha
    def new_values(self):
        parametros = self.sheet_values(self.leitura, df)

        ghi = abs(self.treat_data(parametros['ghi'])) # Register 0
        poa_1 = self.treat_data(parametros['poa_1']) # Register 1
        ref_30_temp = self.treat_data(parametros['ref_30_temp']) # Register 2
        temp_1 = self.treat_data(parametros['temp_1']) # Register 3
        umidade_higromet = self.treat_data(parametros['umidade_higromet']) # Register 4
        v_vento = self.treat_data(parametros['v_vento']) # Register 5
        timestamp = self.treat_timestamp(parametros['TIME']) # Register 6

        print(ghi, poa_1, ref_30_temp, temp_1, umidade_higromet, v_vento, timestamp)
        self.leitura += 1  #atualiza numero da leitura
        
        return [ghi, poa_1, ref_30_temp, temp_1, umidade_higromet, v_vento, timestamp]

    def update_values(self):
        self.lista = self.new_values()
        for i in range(len(self.lista)):
            self._h_regs[i] = self.lista[i]
        return self.lista

    def update_values_periodically(self):
        while True:
            self.update_values()
            time.sleep(1.5)

    # Função para retornar os valores dos registradores
    def get_holding_registers(self, address, number=1, srv_info=None):
        try:
            return [self._h_regs[i] for i in range(address, address + number)]

        except KeyError:
            return

    def start(self, address, number=1, srv_info=None):
        self.lista = self.new_values()
        for i in range(len(self.lista)):
            self._h_regs[i] = self.lista[i]
        self.clone = self._h_regs.copy()
        return [self._h_regs[i] for i in range(address, address + number)]


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
