import subprocess
import sys

# Arquivos Python a serem executados simultaneamente
script1 = "Pymodbus_cliente.py"
script2 = "Pymodbus_Server.py"

try:
    # Iniciar os dois scripts simultaneamente
    process1 = subprocess.Popen([sys.executable, script1])
    process2 = subprocess.Popen([sys.executable, script2])

    # Aguardar a conclusão dos dois processos
    process1.wait()
    process2.wait()

except KeyboardInterrupt:
    print("\nInterrompendo a execução...")
    process1.terminate()
    process2.terminate()

except Exception as e:
    print(f"Erro ao executar os scripts: {e}")
    if process1:
        process1.terminate()
    if process2:
        process2.terminate()

print("Execução finalizada.")
