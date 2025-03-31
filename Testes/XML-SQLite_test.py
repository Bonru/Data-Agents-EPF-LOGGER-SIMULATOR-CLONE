import pandas as pd

class DataProcessor:
    def __init__(self, file_path):
        self.df = pd.read_excel(file_path)
        self.leitura = 0  # Inicializa o índice de leitura

    def sheet_values(self, n_leitura):
        """Retorna os valores de uma linha específica como um dicionário."""
        row = self.df.iloc[n_leitura].to_dict()
        return row

    def treat_data(self, value):
        """Método para tratar os dados (placeholder para lógica específica)."""
        # Implementar lógica de tratamento de dados aqui
        return value

    def treat_timestamp(self, timestamp):
        """Método para tratar timestamps (placeholder para lógica específica)."""
        # Implementar lógica de tratamento de timestamp aqui
        return timestamp

    def new_values(self):
        """Processa os valores da linha atual e retorna os dados tratados."""
        parametros = self.sheet_values(self.leitura)

        v_vento = parametros['v_vento']
        temp_1 = parametros['temp_1']
        umidade_higromet = parametros['umidade_higromet']
        temp_2 = parametros['temp_2']
        temp_higrometro = parametros['temp_higrometro']
        ref_cel_40 = parametros['ref_cel_40']
        testecel40 = parametros['testecel40']
        ref_cel_30 = parametros['ref_cel_30']
        ref_cel_10 = parametros['ref_cel_10']
        ref_40_temp = parametros['ref_40_temp']
        ref_30_temp = parametros['ref_30_temp']
        ref_10_temp = parametros['ref_10_temp']
        poa_ri_2 = parametros['poa_ri_2']
        poa_2 = parametros['poa_2']
        poa_ri_1 = parametros['poa_ri_1']
        poa_1 = parametros['poa_1']
        ghi = parametros['ghi']
        timestamp = parametros['TIME']

        return [
            {"NAME": "v_vento", "VALUE": v_vento},
            {"NAME": "temp_1", "VALUE": temp_1},
            {"NAME": "umidade_higromet", "VALUE": umidade_higromet},
            {"NAME": "temp_2", "VALUE": temp_2},
            {"NAME": "temp_higrometro", "VALUE": temp_higrometro},
            {"NAME": "ref_cel_40", "VALUE": ref_cel_40},
            {"NAME": "testecel40", "VALUE": testecel40},
            {"NAME": "ref_cel_30", "VALUE": ref_cel_30},
            {"NAME": "ref_cel_10", "VALUE": ref_cel_10},
            {"NAME": "ref_40_temp", "VALUE": ref_40_temp},
            {"NAME": "ref_30_temp", "VALUE": ref_30_temp},
            {"NAME": "ref_10_temp", "VALUE": ref_10_temp},
            {"NAME": "poa_ri_2", "VALUE": poa_ri_2},
            {"NAME": "poa_2", "VALUE": poa_2},
            {"NAME": "poa_ri_1", "VALUE": poa_ri_1},
            {"NAME": "poa_1", "VALUE": poa_1},
            {"NAME": "ghi", "VALUE": ghi},
            {"NAME": "timestamp", "VALUE": timestamp}
        ]

# Exemplo de uso
if __name__ == "__main__":
    processor = DataProcessor('Datalogger_28_11_2024.xlsx')
    param = processor.sheet_values(0)  # Exemplo de leitura de uma linha
    print(param)
    for value in param:
        processed_value = processor.treat_data(value)
    print(processor.new_values())    # Exemplo de processamento de valores