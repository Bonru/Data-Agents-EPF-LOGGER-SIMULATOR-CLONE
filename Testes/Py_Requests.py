import requests
import time
import pandas as pd


"""~~~~~~~~~~~~CONSTANTES DO PROGRAMA~~~~~~~~~~~~~~"""
URL = "https://http-server-bf6a7-default-rtdb.firebaseio.com/.json"
FILE = 'Testes\Data.xlsx'
#Caso corrigir seja True os valores negativos serão corrigidos para 0 e as "," serão trocadas por "."
CORRIGIR = True
"""~~~~~~~~~~~~CONSTANTES DO PROGRAMA~~~~~~~~~~~~~~"""


class SolarPlatformMonitor:
    def __init__(self, url, excel_file):
        self.url = url
        self.key = "Monitoramento"
        self.leitura = 0
        self.df = pd.read_excel(excel_file)

    # Função para formatar os dados
    def treat_data(self, data):
        for key, value in data.items():
            if isinstance(value, str):
                try:
                    value = value.replace(',', '.')
                    value = float(value)
                    data[key] = value if value >= 0 else 0
                except ValueError:
                    pass
            elif isinstance(value, (int, float)):
                data[key] = value if value >= 0 else 0
        return data

    """
    def post_data(self, data):
        try:
            response = requests.post(self.url, json=data)
            if response.status_code in [200, 201]:
                print("Post feito com sucesso")
                return response.json()
            else:
                print(f"Falha: {response.status_code}")
                print("Response:", response.text)
        except requests.exceptions.RequestException as e:
            print(f"Erro: {e}")
    """

    # Função para atualizar os dados no servidor http
    def patch_data(self, key, data):
        try:
            patch_url = f"{self.url.rstrip('.json')}/{key}.json"
            response = requests.patch(patch_url, json=data)
            if response.status_code == 200:
                print("Patch feito com sucesso")
            else:
                print(f"Falha: {response.status_code}")
                print("Response:", response.text)
        except requests.exceptions.RequestException as e:
            print(f"Erro: {e}")

    def sheet_values(self, n_leitura):
        row = self.df.iloc[n_leitura].to_dict()
        return row

    # Função que retorna os novos parametros
    def new_values(self):
        parametros = self.sheet_values(self.leitura)
        if CORRIGIR:
            parametros = self.treat_data(parametros)
        print("PARAMETROS: ", parametros)
        self.leitura += 1
        return parametros

    def loop(self):
        while True:
            data = self.new_values()
            self.patch_data(self.key, data)
            time.sleep(0.5)
            print("Atualizando dados...")
            time.sleep(0.5)
            print()

if __name__ == "__main__":
    monitor = SolarPlatformMonitor(
        url = URL,
        excel_file= FILE
    )
    try:
        print("Ligando servidor...")
        monitor.loop()
    except:
        print("Desligando servidor...")
        print("Servidor desligado")
