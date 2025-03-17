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

        v_vento = self.treat_data(parametros['v_vento']) # i = 0
        temp_1 = self.treat_data(parametros['temp_1']) # i = 1
        umidade_higromet = self.treat_data(parametros['umidade_higromet']) # i = 2
        temp_2 = self.treat_data(parametros['temp_2']) # i = 3
        temp_higrometro = self.treat_data(parametros['temp_higrometro']) # i = 4
        ref_cel_40 = self.treat_data(parametros['ref_cel_40']) # i = 5
        testecel40 = self.treat_data(parametros['testecel40']) # i = 6
        ref_cel_30 = self.treat_data(parametros['ref_cel_30']) # i = 7
        ref_cel_10 = self.treat_data(parametros['ref_cel_10']) # i = 8
        ref_40_temp = self.treat_data(parametros['ref_40_temp']) # i = 9
        ref_30_temp = self.treat_data(parametros['ref_30_temp']) # i = 10
        ref_10_temp = self.treat_data(parametros['ref_10_temp']) # i = 11
        poa_ri_2 = self.treat_data(parametros['poa_ri_2']) # i = 12
        poa_2 = self.treat_data(parametros['poa_2']) # i = 13
        poa_ri_1 = self.treat_data(parametros['poa_ri_1']) # i = 14
        poa_1 = self.treat_data(parametros['poa_1']) # i = 15
        ghi = abs(self.treat_data(parametros['ghi'])) # i = 16
        timestamp = self.treat_timestamp(parametros['TIME']) # i = 17

        self.leitura += 1  # atualiza numero da leitura
        print(v_vento, temp_1, umidade_higromet, temp_2, temp_higrometro, ref_cel_40, testecel40, ref_cel_30, ref_cel_10, ref_40_temp, ref_30_temp, ref_10_temp, poa_ri_2, poa_2, poa_ri_1, poa_1, ghi, timestamp)
        
        return [v_vento, temp_1, umidade_higromet, temp_2, temp_higrometro, ref_cel_40, testecel40, ref_cel_30, ref_cel_10, ref_40_temp, ref_30_temp, ref_10_temp, poa_ri_2, poa_2, poa_ri_1, poa_1, ghi, timestamp]

    def update_values(self):
        self.lista = self.new_values()
        print("Tamanho da lista:", len(self.lista))
        # Mapeamento dos parâmetros para os registradores correspondentes
        self._h_regs[224] = self.lista[0]  # vel. vento
        self._h_regs[226] = self.lista[1]  # temperatura do ar
        self._h_regs[228] = self.lista[2]  # umidade do ar
        self._h_regs[230] = self.lista[3]  # Temperatura do modulo 1
        self._h_regs[232] = self.lista[4]  # Temperatura do modulo 2
        self._h_regs[276] = self.lista[5]  # radiação celula 40m
        self._h_regs[501] = self.lista[6]  # Teste celula 40m
        self._h_regs[278] = self.lista[9]  # Temperatura celula 40m
        self._h_regs[280] = self.lista[7]  # radiação celula 30m
        self._h_regs[282] = self.lista[10]  # Temperatura celula 30m
        self._h_regs[284] = self.lista[8]  # radiação celula 10m
        self._h_regs[286] = self.lista[11]  # Temperatura celula 10m
        self._h_regs[384] = self.lista[16]  # Radiação solar GHI
        self._h_regs[386] = self.lista[15]  # Radiação solar POA 1
        self._h_regs[388] = self.lista[14]  # Radiação solar POA RI 1
        self._h_regs[390] = self.lista[13]  # Radiação solar POA 2
        self._h_regs[392] = self.lista[12]  # Radiação solar POA RI 2
        self._h_regs[500] = self.lista[17]  # Timestamp
        
        return self.lista

    def update_values_periodically(self):
        while True:
            self.update_values()
            time.sleep(20)

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
