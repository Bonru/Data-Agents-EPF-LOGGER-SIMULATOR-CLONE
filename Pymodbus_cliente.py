from pyModbusTCP.client import ModbusClient
from time import sleep
import json
from collections import deque

client = ModbusClient("localhost", 8080)
lista = []

# Armazenar as últimas 50 leituras para cada parâmetro usando deques (FIFO)
historico_leituras = {
    "Temperatura": deque(maxlen=50),
    "Umidade": deque(maxlen=50),
    "Tensão": deque(maxlen=50),
    "Potência": deque(maxlen=50),
    "Vel. vento": deque(maxlen=50),
    "Irradiância": deque(maxlen=50)
}

def print_holding_registers(lista):
    """Converte e exibe os valores dos registradores lidos."""
    Temperatura, Umidade, Tensao, Potencia, Vento, Irradiancia = [
        [0, "Temperatura", "°C"], 
        [0, "Umidade", "%"], 
        [0, "Tensão", "kV"], 
        [0, "Potência", "kW"], 
        [0, "Vel. vento", "m/s"], 
        [0, "Irradiância", "W/m²"]
    ]
    parametros = [Temperatura, Umidade, Tensao, Potencia, Vento, Irradiancia]
    
    for k in range(len(lista)):
        print(f"{parametros[k][1]}: {lista[k]:.1f} {parametros[k][2]}")
    print()
        
    # Atualiza os valores para retornar na estrutura necessária para JSON
    for j in range(len(lista)):
        parametros[j][0] = lista[j]
    return parametros

def armazenar_leitura(parametros):
    """Armazena cada nova leitura no histórico, mantendo apenas as últimas 50 leituras."""
    historico_leituras["Temperatura"].append(parametros[0][0])
    historico_leituras["Umidade"].append(parametros[1][0])
    historico_leituras["Tensão"].append(parametros[2][0])
    historico_leituras["Potência"].append(parametros[3][0])
    historico_leituras["Vel. vento"].append(parametros[4][0])
    historico_leituras["Irradiância"].append(parametros[5][0])
    
    # Salva o histórico em um arquivo JSON
    with open("historico_leituras.json", "w") as file:
        json.dump({chave: list(valores) for chave, valores in historico_leituras.items()}, file)


def read_registers():
    try:
        lista = client.read_holding_registers(0, 6)
        if lista:
            #adquirir os valores dos registradores
            parametros = print_holding_registers(lista)
            #armazenar os valores dos registradores
            armazenar_leitura(parametros)
            with open("lista.json", "w") as file:
                json.dump(parametros, file)
        else:
            print("Erro ao ler registradores")
    except Exception as e:
        print(f"Error reading registers or writing to file: {e}")

    sleep(1.5)

if __name__ == "__main__":
    
    try:
        print("Abrindo cliente...")
        client.open()
        print("Cliente aberto\n")
        while True:
            read_registers()

    except Exception as e:
        print(f"Unexpected error: {e}")
        print("Fechando cliente...")
        client.close()
        print("Cliente Fechado")