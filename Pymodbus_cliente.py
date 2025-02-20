from pyModbusTCP.client import ModbusClient
from time import sleep
import json
from collections import deque
from PyQt6.QtCore import QObject

class ModbusClientHandler(QObject):
    def __init__(self, host="localhost", port=8080):
        super().__init__()
        self.client = ModbusClient(host, port)
        self.historico_leituras = {
            "GHI": deque(maxlen=50),
            "POA 1": deque(maxlen=50),
            "Ref 30 Temp": deque(maxlen=50),
            "Temperatura": deque(maxlen=50),
            "Umidade": deque(maxlen=50),
            "Vel. vento": deque(maxlen=50),
            "Timestamp": deque(maxlen=50)
        }
        self.parametros = [
            [0, "GHI", "W/m²"], 
            [0, "POA 1", "W/m²"], 
            [0, "Ref 30 Temp", "°C"], 
            [0, "Temperatura", "°C"], 
            [0, "Umidade", "%"], 
            [0, "Vel. vento", "m/s"],
            [0, "Timestamp", "s"]
        ]

    def print_holding_registers(self, lista):
        """Converte e exibe os valores dos registradores lidos."""      
        for k in range(len(lista)):
            #print(f"{self.parametros[k][1]}: {lista[k]:.1f} {self.parametros[k][2]}")
            pass
        print(self.parametros)
        print()
            
        # Atualiza os valores para retornar na estrutura necessária para JSON
        for j in range(len(lista)):
            self.parametros[j][0] = lista[j]
        return self.parametros

    def armazenar_leitura(self, parametros):
        """Armazena cada nova leitura no histórico, mantendo apenas as últimas 50 leituras."""
        
        # Adicionar as novas leituras aos deques
        self.historico_leituras["GHI"].append(parametros[0][0])
        self.historico_leituras["POA 1"].append(parametros[1][0])
        self.historico_leituras["Ref 30 Temp"].append(parametros[2][0])
        self.historico_leituras["Temperatura"].append(parametros[3][0])
        self.historico_leituras["Umidade"].append(parametros[4][0])
        self.historico_leituras["Vel. vento"].append(parametros[5][0])
        
        # Converter Timestamp de segundos para hora:minuto:segundo
        timestamp_seconds = parametros[6][0]
        timestamp_hms = self.convert_seconds_to_hms(timestamp_seconds)
        self.historico_leituras["Timestamp"].append(timestamp_hms)

    def convert_seconds_to_hms(self, seconds):
        """Converte segundos para o formato hora:minuto:segundo."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def write_register(self, endereco=3, newvalue=0):
        try:
            self.client.write_single_register(endereco, newvalue)
            print(self.client.write_single_register(endereco, newvalue))
        except Exception as e:
            print(f"Erro ao tentar escrever no registrador: {e}")

    def read_registers(self):
        try:
            lista = self.client.read_holding_registers(0, 7)
            if lista:
                # Adquirir os valores dos registradores
                self.parametros = self.print_holding_registers(lista)
                # Dividir o valor de todos os parametros por 10
                for i in range(len(self.parametros)):
                    self.parametros[i][0] /= 10
                # Armazenar os valores dos registradores
                self.armazenar_leitura(self.parametros)
        except Exception as e:
            print(f"Erro ao tentar ler os registradores: {e}")

    def getdata(self):
        return self.parametros
    
    def gethistorico(self):
        return self.historico_leituras

    def start(self):
        try:
            print("Abrindo cliente...")
            self.client.open()
            print("Cliente aberto\n")

        except Exception as e:
            print(f"Unexpected error: {e}")
            print("Fechando cliente...")
            self.client.close()
            print("Cliente Fechado")
    
ModbusClientHandler().start()

