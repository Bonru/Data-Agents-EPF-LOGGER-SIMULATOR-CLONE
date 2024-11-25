import pandas as pd

# Read the Excel file
df = pd.read_excel('medidas.xlsx')

def sheet_values(n_leitura, df):
    row = df.iloc[n_leitura].to_dict()
    return row

for leitura in range(0, 10):
    parametros = sheet_values(leitura, df)
    ghi = parametros['ghi'] #Register 0
    poa_1 = parametros['poa_1'] #Register 1
    ref_30_temp = parametros['ref_30_temp'] #Register 2
    temp_1 = parametros['temp_1'] #Register 3
    umidade_higromet = parametros['umidade_higromet'] #Register 4
    v_vento = parametros['v_vento'] #Register 5
    print(ghi, poa_1, ref_30_temp, temp_1, umidade_higromet, v_vento)