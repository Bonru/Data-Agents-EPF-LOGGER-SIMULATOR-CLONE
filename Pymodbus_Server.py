#!/bin/python

import logging
import pandas as pd
from pyModbusTCP.server import ModbusServer, DataBank
import threading
import time
import traceback

logging.basicConfig()
logging.getLogger('pyModbusTCP.server').setLevel(logging.DEBUG)
df = pd.read_excel('Datalogger_28_11_2024.xlsx')

# Um registrador Modbus tem 16 bits sem sinal (máx. 65535), mas os segundos do dia chegam a 86399.
# O registrador 500 (Timestamp) guarda os segundos do dia divididos por 2, arredondados para baixo
# (0 a 43199; erro máximo de 1 s, dentro do tick de 2 s do Simulador). O Cliente multiplica por 2.
TIMESTAMP_SECONDS_PER_REGISTER = 2

class MyDataBank(DataBank):
    def __init__(self, dataset=None, tick_seconds=2):
        """dataset: DataFrame com as linhas a servir (padrão: a planilha carregada acima).
        tick_seconds: segundos entre uma linha e a próxima (padrão: 2)."""
        super().__init__()
        self.dataset = df if dataset is None else dataset
        self.timer = tick_seconds
        self.leitura = 0  # número da próxima linha a ler
        self.lista = []
        self.start(0)
        self.update_thread = threading.Thread(target=self.update_values_periodically)
        self.update_thread.daemon = True
        self.update_thread.start()

    def sheet_values(self, n_leitura, df):
        row = df.iloc[n_leitura].to_dict()
        return row

    # Função que escolhe a próxima linha; depois da última, volta para a primeira
    def next_row_number(self):
        """Número da próxima linha a ler. O contador avança já aqui, então uma linha que falhar
        não é lida de novo no tick seguinte."""
        if self.leitura >= len(self.dataset):
            print("End of dataset reached; restarting from the first row.")
            self.leitura = 0
        row_number = self.leitura
        self.leitura += 1
        return row_number
    
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

    # Função para codificar os segundos do dia no valor do registrador 500
    def encode_timestamp(self, seconds_of_day):
        """Segundos do dia -> valor do registrador 500 (cabe em 16 bits o dia inteiro)."""
        return seconds_of_day // TIMESTAMP_SECONDS_PER_REGISTER

        
    # Função para retornar os novos valores da proxima consulta na planilha
    def new_values(self):
        parametros = self.sheet_values(self.next_row_number(), self.dataset)

        #Leituras
        self.v_vento = self.treat_data(parametros['v_vento']) # i = 0
        self.temp_1 = self.treat_data(parametros['temp_1']) # i = 1
        self.umidade_higromet = self.treat_data(parametros['umidade_higromet']) # i = 2
        self.temp_2 = self.treat_data(parametros['temp_2']) # i = 3
        self.temp_higrometro = self.treat_data(parametros['temp_higrometro']) # i = 4
        self.ref_cel_40 = self.treat_data(parametros['ref_cel_40']) # i = 5
        self.testecel40 = self.treat_data(parametros['testecel40']) # i = 6
        self.ref_cel_30 = self.treat_data(parametros['ref_cel_30']) # i = 7
        self.ref_cel_10 = self.treat_data(parametros['ref_cel_10']) # i = 8
        self.ref_40_temp = self.treat_data(parametros['ref_40_temp']) # i = 9
        self.ref_30_temp = self.treat_data(parametros['ref_30_temp']) # i = 10
        self.ref_10_temp = self.treat_data(parametros['ref_10_temp']) # i = 11
        self.poa_ri_2 = self.treat_data(parametros['poa_ri_2']) # i = 12
        self.poa_2 = self.treat_data(parametros['poa_2']) # i = 13
        self.poa_ri_1 = self.treat_data(parametros['poa_ri_1']) # i = 14
        self.poa_1 = self.treat_data(parametros['poa_1']) # i = 15
        self.ghi = abs(self.treat_data(parametros['ghi'])) # i = 16
        self.irradiance = abs(self.treat_data(parametros['Irradiance'])) # i = 17
        self.aparent_power = abs(self.treat_data(parametros['Apparent Power'])) # i = 18
        self.timestamp = self.encode_timestamp(self.treat_timestamp(parametros['TIME'])) # i = 19 (valor do registrador 500)

        #Device Fault Code
        self.Fault_c1 = 0

        
        return [self.v_vento, self.temp_1, self.umidade_higromet, self.temp_2, self.temp_higrometro, self.ref_cel_40,
                self.testecel40, self.ref_cel_30, self.ref_cel_10, self.ref_40_temp, self.ref_30_temp, self.ref_10_temp,
                self.poa_ri_2, self.poa_2, self.poa_ri_1, self.poa_1, self.ghi, self.timestamp, self.Fault_c1, self.irradiance, self.aparent_power]

    def update_values(self):
        self.lista = self.new_values()
        print(self.lista)
        print("Tamanho da lista:", len(self.lista))
        # Mapeamento dos parâmetros para os registradores correspondentes
        self._h_regs[224] = self.v_vento  # vel. vento
        self._h_regs[226] = self.temp_1  # temperatura do ar
        self._h_regs[228] = self.umidade_higromet  # umidade do ar
        self._h_regs[230] = self.temp_2  # Temperatura do modulo 1
        self._h_regs[232] = self.temp_higrometro  # Temperatura do modulo 2
        self._h_regs[276] = self.ref_cel_40  # radiação celula 40m
        self._h_regs[501] = self.testecel40  # Teste celula 40m
        self._h_regs[278] = self.ref_40_temp  # Temperatura celula 40m
        self._h_regs[280] = self.ref_cel_30  # radiação celula 30m
        self._h_regs[282] = self.ref_30_temp  # Temperatura celula 30m
        self._h_regs[284] = self.ref_cel_10  # radiação celula 10m
        self._h_regs[286] = self.ref_10_temp  # Temperatura celula 10m
        self._h_regs[384] = self.ghi  # Radiação solar GHI
        self._h_regs[386] = self.poa_1  # Radiação solar POA 1
        self._h_regs[388] = self.poa_ri_1  # Radiação solar POA RI 1
        self._h_regs[390] = self.poa_2  # Radiação solar POA 2
        self._h_regs[392] = self.poa_ri_2  # Radiação solar POA RI 2
        self._h_regs[500] = self.timestamp # Timestamp
        self._h_regs[1] = self.irradiance # Irradiance
        self._h_regs[2] = self.aparent_power # Apparent Power

        self._h_regs[5054] = self.Fault_c1  # Argumento de falha
        
        return self.lista

    def update_values_periodically(self):
        while True:
            try:
                self.update_values()
            except Exception:
                # Uma atualização que falha não pode matar a thread: mostra o erro e segue no próximo tick
                print("Update failed; continuing on the next tick:")
                print(traceback.format_exc())
            time.sleep(self.timer)

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
