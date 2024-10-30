from pyModbusTCP.client import ModbusClient
from time import sleep
import json

client = ModbusClient("localhost", 8080)
lista = []

def print_holding_registers(lista):
    Temperatura, Umidade, Tensao, Potencia, Vento, Irradiancia = [0, "Temperatura", "°C"], [0, "Umidade", "%"], [0, "Tensão", "kV"], [0, "Potência", "kW"], [0, "Vel. vento", "m/s"], [0, "Irradiância", "W/m²"]
    parametros = [Temperatura, Umidade, Tensao, Potencia, Vento, Irradiancia]
    for k in range(len(lista)):
        print(f"{parametros[k][1]}: {lista[k]:.1f} {parametros[k][2]}")
    print("")
    for j in range(len(lista)):
        parametros[j][0] = lista[j]
    return parametros

def read_registers():
    try:
        lista = client.read_holding_registers(0, 6)
        if lista:
            parametros = print_holding_registers(lista)
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