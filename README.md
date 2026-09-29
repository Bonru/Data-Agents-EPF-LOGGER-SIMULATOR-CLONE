# Logger_simulator

## 04/02/2025
+ (+) Feitas algumas atualizações solicitadas na reunião do dia 04/02/2025
+ (+) Renomeação das planilhas de script do simulador
+ (+) Outras atualizações

## 24/02/2025
+ (+) Servidor disponibiliza todos os dados da planilha. Mapeamento semelhante ao datalogger da FEEC
+ (+) Interface gráfica corrigida para comportar os novos parametros

## 10/03/2025
- (+) Corrigir função Sobrescrever dados no servidor
- (+) Corrigir exibição de timestamp no gráfico

## 17/03/2025
- (+) Adição de requests HTTP
- (+) Primeiros testes de interações com o sistema do Flávio

## 31/03/2025
- (+) Melhorias nos requests HTTP (Timeout)
- (+) Testes de uso de SQLite

## Arquitetura

O cliente Modbus roda em uma thread própria (worker) e a interface PyQt só recebe Frames imutáveis por sinais. A decisão está registrada em [docs/adr/0001-worker-thread-and-immutable-frames.md](docs/adr/0001-worker-thread-and-immutable-frames.md); o glossário do domínio está em [CONTEXT.md](CONTEXT.md).
