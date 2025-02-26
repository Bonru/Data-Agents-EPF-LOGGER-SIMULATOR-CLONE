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
            "Vel. vento": deque(maxlen=50),         #1
            "Temperatura 1": deque(maxlen=50),      #2
            "Umidade H.": deque(maxlen=50),         #3
            "Temperatura 2": deque(maxlen=50),      #4
            "Temp H.": deque(maxlen=50),            #5
            "Ref Cel 40": deque(maxlen=50),         #6
            "Teste Cel 40": deque(maxlen=50),       #7
            "Ref Cel 30": deque(maxlen=50),         #8
            "Ref Cel 10": deque(maxlen=50),         #9
            "Ref 40 Temp": deque(maxlen=50),        #10
            "Ref 30 Temp": deque(maxlen=50),        #11
            "Ref 10 Temp": deque(maxlen=50),        #12
            "POA RI 2": deque(maxlen=50),           #13
            "POA 2": deque(maxlen=50),              #14
            "POA RI 1": deque(maxlen=50),           #15
            "POA 1": deque(maxlen=50),              #16
            "GHI": deque(maxlen=50),                #17
            "Timestamp": deque(maxlen=50)           #18
        }
        self.parametros = [
            [0, "Vel. vento", "m/s"],
            [0, "Temperatura 1", "°C"],
            [0, "Umidade H.", "%"],
            [0, "Temperatura 2", "°C"],
            [0, "Temp H.", "°C"],
            [0, "Ref Cel 40", "W/m²"],
            [0, "Teste Cel 40", "°C"],
            [0, "Ref Cel 30", "W/m²"],
            [0, "Ref Cel 10", "W/m²"],
            [0, "Ref 40 Temp", "°C"],
            [0, "Ref 30 Temp", "°C"],
            [0, "Ref 10 Temp", "°C"],
            [0, "POA RI 2", "W/m²"],
            [0, "POA 2", "W/m²"],
            [0, "POA RI 1", "W/m²"],
            [0, "POA 1", "W/m²"],
            [0, "GHI", "W/m²"],
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
        self.historico_leituras["Vel. vento"].append(parametros[0][0])   # Register 224
        self.historico_leituras["Temperatura 1"].append(parametros[1][0])# Register 226
        self.historico_leituras["Umidade H."].append(parametros[2][0])      # Register 228
        self.historico_leituras["Temperatura 2"].append(parametros[3][0]) # Register 230
        self.historico_leituras["Temp H."].append(parametros[4][0]) # Register 232
        self.historico_leituras["Ref Cel 40"].append(parametros[5][0]) # Register 276
        self.historico_leituras["Teste Cel 40"].append(parametros[6][0]) # Register 501
        self.historico_leituras["Ref Cel 30"].append(parametros[7][0]) # Register 280
        self.historico_leituras["Ref Cel 10"].append(parametros[8][0]) # Register 284
        self.historico_leituras["Ref 40 Temp"].append(parametros[9][0]) # Register 278
        self.historico_leituras["Ref 30 Temp"].append(parametros[10][0]) # Register 282
        self.historico_leituras["Ref 10 Temp"].append(parametros[11][0]) # Register 286
        self.historico_leituras["POA RI 2"].append(parametros[12][0]) # Register 392
        self.historico_leituras["POA 2"].append(parametros[13][0])    # Register 390
        self.historico_leituras["POA RI 1"].append(parametros[14][0]) # Register 388
        self.historico_leituras["POA 1"].append(parametros[15][0])    # Register 386
        self.historico_leituras["GHI"].append(parametros[16][0])      # Register 384
        
        # Converter Timestamp de segundos para hora:minuto:segundo
        timestamp_seconds = parametros[17][0] # Register 500
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
            # Lista de endereços dos registradores a serem lidos
            addresses = [224, 226, 228, 230, 232, 276, 501, 280, 284, 278, 282, 286, 392, 390, 388, 386, 384, 500]
            
            # Lista para armazenar os valores lidos
            lista = []
            
            for address in addresses:
                value = self.client.read_holding_registers(address, 1)
                if value:
                    lista.append(value[0])
                else:
                    lista.append(0) # Adiciona 0 se não conseguir ler o valor
                    print("Falha ao ler o registrador", address)  
            
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

