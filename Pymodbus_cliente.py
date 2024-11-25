from pyModbusTCP.client import ModbusClient
from time import sleep
import json
from collections import deque

class ModbusClientHandler:
    def __init__(self, host="localhost", port=552):
        self.client = ModbusClient(host, port)
        self.historico_leituras = {
            "GHI": deque(maxlen=50),
            "POA 1": deque(maxlen=50),
            "Ref 30 Temp": deque(maxlen=50),
            "Temperatura": deque(maxlen=50),
            "Umidade": deque(maxlen=50),
            "Vel. vento": deque(maxlen=50)
        }

    def print_holding_registers(self, lista):
        """Converte e exibe os valores dos registradores lidos."""
        parametros = [
            [0, "GHI", "W/m²"], 
            [0, "POA 1", "W/m²"], 
            [0, "Ref 30 Temp", "°C"], 
            [0, "Temperatura", "°C"], 
            [0, "Umidade", "%"], 
            [0, "Vel. vento", "m/s"]
        ]
        
        for k in range(len(lista)):
            print(f"{parametros[k][1]}: {lista[k]:.1f} {parametros[k][2]}")
        print()
            
        # Atualiza os valores para retornar na estrutura necessária para JSON
        for j in range(len(lista)):
            parametros[j][0] = lista[j]
        return parametros

    def armazenar_leitura(self, parametros):
        """Armazena cada nova leitura no histórico, mantendo apenas as últimas 50 leituras."""
        # Carregar os dados do arquivo historico_leituras.json
        try:
            with open("historico_leituras.json", "r") as file:
                historico = json.load(file)
                for key in self.historico_leituras:
                    self.historico_leituras[key] = deque(historico[key], maxlen=50)
        except FileNotFoundError:
            pass  # Se o arquivo não existir, continue com os deques vazios

        # Adicionar as novas leituras aos deques
        self.historico_leituras["GHI"].append(parametros[0][0])
        self.historico_leituras["POA 1"].append(parametros[1][0])
        self.historico_leituras["Ref 30 Temp"].append(parametros[2][0])
        self.historico_leituras["Temperatura"].append(parametros[3][0])
        self.historico_leituras["Umidade"].append(parametros[4][0])
        self.historico_leituras["Vel. vento"].append(parametros[5][0])
    
        # Salvar os deques atualizados no arquivo historico_leituras.json
        with open("historico_leituras.json", "w") as file:
            json.dump({chave: list(valores) for chave, valores in self.historico_leituras.items()}, file)

    def read_registers(self):
        try:
            lista = self.client.read_holding_registers(0, 6)
            if lista:
                #adquirir os valores dos registradores
                parametros = self.print_holding_registers(lista)
                #dividir o valor de todos os parametros por 10
                for i in range(len(parametros)):
                    parametros[i][0] /= 10
                #armazenar os valores dos registradores
                self.armazenar_leitura(parametros)
                with open("lista.json", "w") as file:
                    json.dump(parametros, file)
            else:
                print("Erro ao ler registradores")
        except Exception as e:
            print(f"Error reading registers or writing to file: {e}")

        sleep(1.5)

    def start(self):
        try:
            print("Abrindo cliente...")
            self.client.open()
            print("Cliente aberto\n")
            while True:
                self.read_registers()
        except Exception as e:
            print(f"Unexpected error: {e}")
            print("Fechando cliente...")
            self.client.close()
            print("Cliente Fechado")

if __name__ == "__main__":
    handler = ModbusClientHandler()
    handler.start()