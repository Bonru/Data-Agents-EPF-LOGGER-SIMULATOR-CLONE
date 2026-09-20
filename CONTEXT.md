# Datalogger Simulator

Domain glossary for the software that simulates a solarimetric station's datalogger over Modbus, feeding a monitoring pipeline (PyQt UI, Firebase, and a web viewer).

## Equipment & Site

**Datalogger**:
The real physical device installed at the solarimetric station (e.g. the EMS4-GDB2), whose Modbus register map this repository imitates.
_Avoid_: Simulator (that's this repo's own server, not the hardware)

**Simulator**:
This repository's Modbus TCP server (`Pymodbus_Server.py`), which mimics the Datalogger's register responses for testing, advancing one Frame per tick from the source spreadsheet.
_Avoid_: Datalogger, Server

**Station**:
The physical site as a whole: every Sensor plus the real Datalogger, and — tentatively, pending confirmation against the manual — electrical-side equipment feeding the Apparent Power Channel.

## Sensors & Channels

**Sensor**:
An individual physical instrument mounted at the Station (Anemometer, Hygrometer, Cell, PV Module temperature probe). A Sensor may expose more than one Channel. Not the whole Station/Datalogger as one unit — that broader meaning appears only in `measure.py`'s legacy HTTP API (`sensorName="datalogger"`) and isn't canonical here.

**Cell**:
A reference-cell (pyranometer-type) Sensor mounted at a specific height (10m, 30m, or 40m). Each Cell exposes two Channels: solar radiation and its own temperature.

**Hygrometer**:
The Sensor reporting ambient air conditions. Exposes two Channels: air humidity and air temperature.

**Anemometer**:
The Sensor reporting wind speed. Exposes one Channel.

**PV Module temperature probe**:
A single-Channel Sensor reporting one photovoltaic module's temperature. There are two: Module 1 and Module 2.
_Avoid_: conflating with the Hygrometer's air-temperature Channel — the client's labels ("Temperatura 1"/"Temperatura 2") don't distinguish them.

**Channel**:
One named measurement produced by a Sensor (e.g. solar radiation at the 40m Cell). Canonical names follow `measure.py`'s field list; see the alias table below for the spreadsheet and client-label equivalents.
_Avoid_: spreadsheet column names (`ref_cel_40`), client display labels (`"Ref Cel 40"`) as canonical — they're aliases, not the source of truth.

## Data model

**Frame**:
One full sample across every Channel, captured at a single instant — equivalent to one row of the source spreadsheet. The Simulator advances one Frame per tick.
_Avoid_: "leitura" / "reading" for this — reserved for a single Channel's value (see Reading). Code still uses `leitura`/`n_leitura` for this internally; known naming drift, not yet renamed.

**Reading**:
The value of one Channel within a Frame.
_Avoid_: using "reading" for a full multi-Channel sample — that's a Frame. Code still uses `historico_leituras` for the client's per-Channel history; known naming drift, not yet renamed.
A Channel value that could not be obtained from the Simulator is not a Reading: it is never recorded as `0`, in history or in any downstream sink.

**Manual override**:
A value the user types for a Channel in the PyQt UI ("Inserção manual") that replaces what the Simulator reports for that Channel. Every Channel can be overridden; the Frame's Timestamp cannot. It is held — re-asserted on every poll — until the user clears it, and the UI shows which Channels are overridden.
_Avoid_: "one-shot write" — an override is not applied once and forgotten.

**Fault code**:
A protocol value (register 5054) from the Datalogger's fault-reporting scheme: `0` means no fault, other values represent specific device faults per the Datalogger's manual. The Simulator always reports `0`; simulating real fault conditions is a known future gap, not yet implemented.

## Client & connection

**Client**:
This repository's Modbus TCP client (`Pymodbus_cliente.py`): it polls the Simulator for Frames, holds Manual overrides, and forwards Frames to Firebase. Distinct from the PyQt UI, which only displays the Frames the Client emits and collects the user's overrides.
_Avoid_: calling the UI "the client".

**PyQt UI**:
The desktop window titled "Interface Datalogger" (`main.py`). It monitors whichever Modbus source the Client is pointed at — the Simulator or a real Datalogger — which is why its title says "Datalogger" rather than "Simulator".

**Poll**:
One attempt by the Client to read a Frame from the Simulator. A Poll that finds nothing new yields no new Frame downstream.

**Partial Frame**:
A Frame in which one or more Channels could not be read. Those Channels have no Reading in it; the others are valid and the Frame is still used.

**Connection state**:
Health of the Client's link to the Simulator, one of three: **Connected** (Polls get answers and new Frames keep arriving), **Stale** (Polls get answers but no new Frame has arrived for longer than a few Simulator ticks — the Simulator is up but not advancing), **Disconnected** (Polls get no usable response). Firebase upload health is reported separately and is not part of this state.

## Legacy API path

**`measure.py` / `post_measure()`**:
A standalone, manual CLI tool that pushes one Channel's value to an older HTTP API (`lab-lserf`). Disconnected from the live pipeline (Simulator → Firebase → PyQt UI / web_view) — `Pymodbus_cliente.py` defines `post_measure()` but never calls it.

## Testes/ SQLite scripts

Throwaway historical spikes exploring an alternative persistence backend (`Teste_Database_SQLite.py`, `XML-SQLite_test.py`, `DB.db`). Firebase remains the canonical backend; no SQLite migration is planned.

## Channel name aliases

| Canonical (`measure.py`) | Spreadsheet column | Client label |
|---|---|---|
| velocidade_vento | v_vento | Vel. vento |
| temperatura_modulo_1 | temp_1 | Temperatura 1 |
| umidade_ar | umidade_higromet | Umidade H. |
| temperatura_modulo_2 | temp_2 | Temperatura 2 |
| temperatura_ar | temp_higrometro | Temp H. |
| radiacao_celula_40m | ref_cel_40 | Ref Cel 40 |
| teste_celula_40m | testecel40 | Teste Cel 40 |
| radiacao_celula_30m | ref_cel_30 | Ref Cel 30 |
| radiacao_celula_10m | ref_cel_10 | Ref Cel 10 |
| temperatura_celula_40m | ref_40_temp | Ref 40 Temp |
| temperatura_celula_30m | ref_30_temp | Ref 30 Temp |
| temperatura_celula_10m | ref_10_temp | Ref 10 Temp |
| radiacao_solar_poa_ri2 | poa_ri_2 | POA RI 2 |
| radiacao_solar_poa2 | poa_2 | POA 2 |
| radiacao_solar_poa_ri1 | poa_ri_1 | POA RI 1 |
| radiacao_solar_poa1 | poa_1 | POA 1 |
| radiacao_solar_ghi | ghi | GHI |
| Irradiance | Irradiance | Irradiance |
| Apparent Power | Apparent Power | Apparent Power |
| fault_code | Fault_c1 | Fault_code |

_(Timestamp isn't a measured Channel — it's the Frame's own timestamp field.)_

## Open questions

- **Fault code scale** (unverified): the Client treats every register as ×10-scaled, including Fault code (register 5054), but Fault code is a protocol value and the Simulator writes it unscaled (`0`). A non-zero code would display wrongly (e.g. `3` reads as `0.3`). Check against the Datalogger's manual.

- **Irradiance / Apparent Power source** (unconfirmed): tentatively assumed to come from separate equipment beyond the core weather Sensors — a reference pyranometer for Irradiance, an inverter or power meter for Apparent Power — which would extend Station to include electrical-side equipment. Not verified against the Datalogger's manual: the manual PDF couldn't be read in this environment (poppler-utils/`pdftoppm` isn't installed). Re-check when that's possible.
