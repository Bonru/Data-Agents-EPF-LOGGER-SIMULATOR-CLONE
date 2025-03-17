import argparse
import requests
import time

token = "305e2132-4248-44c6-8abe-f60cb6515318"
sensorName = "datalogger"
url = "http://lab-lserf:8000"

ENDPOINT =  "/api/v1/monitor/data/"

ANALOG = 1
MODBUS = 2

fields = [
    {
        "name": "velocidade_vento",
        "type": "float"
    },
    {
        "name": "temperatura_modulo_1",
        "type": "float"
    },
    {
        "name": "umidade_ar",
        "type": "float"
    },
    {
        "name": "temperatura_modulo_2",
        "type": "float"
    },
    {
        "name": "temperatura_ar",
        "type": "float"
    },
    {
        "name": "radiacao_celula_40m",
        "type": "float"
    },
    {
        "name": "teste_celula_40m",
        "type": "float"
    },
    {
        "name": "radiacao_celula_30m",
        "type": "float"
    },
    {
        "name": "radiacao_celula_10m",
        "type": "float"
    },
    {
        "name": "temperatura_celula_40m",
        "type": "float"
    },
    
    {
        "name": "temperatura_celula_30m",
        "type": "float"
    },
    
    {
        "name": "temperatura_celula_10m",
        "type": "float"
    },
    {
        "name": "radiacao_sola_poa_ri2",
        "type": "float"
    },
    {
        "name": "radiacao_solar_poa2",
        "type": "float"
    },
    {
        "name": "radiacao_solar_poa_ri1",
        "type": "float"
    },
    {
        "name": "radiacao_solar_poa1",
        "type": "float"
    },
    {
        "name": "radiacao_solar_ghi",
        "type": "float"
    },
    
    #sem leituras
    {
        "name": "irradiacao_ghi_acumulada",
        "type": "float"
    },
    {
        "name": "irradiacao_poa1_acumulada",
        "type": "float"
    },
    {
        "name": "irradiacao_poa_ri1_acumulada",
        "type": "float"
    },
    {
        "name": "irradiacao_poa2_acumulada",
        "type": "float"
    },
    {
        "name": "irradiacao_poa_ri2_acumulada",
        "type": "float"
    }
]


def isValidField(field):
    for f in fields:
        if f['name'] == field:
            return True
    return False


def getFieldType(field):
    for f in fields:
        if f['name'] == field:
            return f['type']
    return None


def main():
    global token
    global sensorName
    global url

    parser = argparse.ArgumentParser(description='Send measures to the api')
    parser.add_argument('-H', '--host', type=str, help='The URL of the API')
    parser.add_argument('-n', '--name', type=str,
                        help='The name of the sensor')
    parser.add_argument('-t', '--token', type=str, help='The token of the user')
    parser.add_argument('-u', '--url', type=str, help='The URL of the API')
    parser.add_argument('field', type=str, help='measure field')
    parser.add_argument('value', type=str, help='measure value')
    args = parser.parse_args()

    if not isValidField(args.field):
        print('Invalid field')
        return

    type = getFieldType(args.field)
    if type == 'float':
        value = float(args.value)
    else:
        print('Invalid type')
        return

    if args.name:
        sensorName = args.name

    if args.token:
        token = args.token
    
    if args.url:
        url = args.url

    # Timestamp in the format YYYY-MM-DDThh:mm[:ss[.uuuuuu]][+HH:MM|-HH:MM|Z]."]}]
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")

    payload = [{
        "token": token,
        "timestamp": timestamp,
        "measureType": MODBUS,
        "sensorName": sensorName,
        "registerName": args.field,
        "value": value
    }]
    backendUrl = url + ENDPOINT

    try:
        r = requests.post(backendUrl, json=payload)
        if r.status_code != 201:
            print("Error during processing data", r.status_code)
            return
        else:
            print("Data sent successfully")
            return
    except Exception as e:
        print("Error sending data: %s" % e)
        return

if __name__ == '__main__':
    main()