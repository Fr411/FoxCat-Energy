from __future__ import annotations

"""Catalogue matériel FoxCat Energy.

Ce catalogue est volontairement informatif. Aucune valeur sélectionnée ici
n'influence les algorithmes PRI, EMS, boiler, tarification ou délestage.

Les listes de modèles représentent des familles/modèles courants et ne
prétendent pas couvrir chaque référence commerciale ou révision matérielle.
"""

OTHER = "Autre / Non répertorié"

INVERTER_CATALOG: dict[str, list[str]] = {'SolarEdge': ['SE2200H',
               'SE3000H',
               'SE3500H',
               'SE3680H',
               'SE4000H',
               'SE4K',
               'SE5000H',
               'SE6000H',
               'SE8K',
               'SE10K',
               'SE12.5K',
               'SE15K',
               'SE16K',
               'SE17K',
               'SE25K',
               'SE27.6K',
               'SE30K',
               'SE33.3K',
               'Home Hub',
               'StorEdge'],
 'SMA': ['Sunny Boy 1.5/2.0/2.5',
         'Sunny Boy 3.0-6.0',
         'Sunny Tripower 3.0-10.0',
         'Sunny Tripower X',
         'Sunny Tripower CORE1',
         'Sunny Island'],
 'Fronius': ['Primo', 'Primo GEN24', 'Symo', 'Symo GEN24', 'Tauro', 'Verto'],
 'Huawei': ['SUN2000-L1', 'SUN2000-M1', 'SUN2000-MB0', 'SUN2000-KTL-M1', 'SUN2000-KTL-M2', 'SUN2000-KTL-M3'],
 'GoodWe': ['DNS', 'XS', 'MS', 'SDT G2', 'ET', 'EH', 'BT', 'ES'],
 'Growatt': ['MIC', 'MIN TL-X', 'MOD TL3-X', 'MID TL3-X', 'SPH', 'SPA', 'WIT'],
 'Sungrow': ['SG-RS', 'SG-RT', 'SH-RS', 'SH-RT', 'CX', 'CX-P2'],
 'Enphase': ['IQ7', 'IQ7A', 'IQ7+', 'IQ8', 'IQ8A', 'IQ8M', 'IQ8HC', 'IQ8P'],
 'Victron Energy': ['MultiPlus-II', 'Quattro', 'EasySolar-II GX', 'Phoenix Inverter', 'RS Smart Solar'],
 'FIMER / ABB': ['UNO-DM', 'UNO-DM-PLUS', 'PVS-10/12.5/15', 'PVS-20/30/33', 'PVS-50/60', 'PVS-100/120'],
 'Delta Electronics': ['RPI Home', 'RPI H3A/H4A/H5A', 'M15A/M20A/M30A', 'M50A', 'M70A'],
 'KOSTAL': ['PIKO MP plus', 'PIKO IQ', 'PLENTICORE plus', 'PLENTICORE G3'],
 'Solis': ['S6-GR1P', 'S6-GR3P', 'S6-EH1P', 'S6-EH3P', 'S5-GC'],
 'FoxESS': ['S Series', 'T Series', 'H1', 'H3', 'KH', 'K Series'],
 'Deye': ['SUN-xK-G', 'SUN-xK-SG01LP1', 'SUN-xK-SG04LP3', 'SUN-xK-SG01HP3'],
 'SOFAR': ['SOFAR KTLX-G3', 'SOFAR HYD', 'SOFAR ME 3000SP', 'SOFAR KTLX-G4'],
 'SolaX Power': ['X1-Boost', 'X1-Hybrid', 'X3-MIC', 'X3-Hybrid', 'X3-Ultra'],
 'APsystems': ['YC600', 'QS1', 'DS3', 'QT2', 'EZ1'],
 'Hoymiles': ['HM Series', 'HMS Series', 'HMT Series', 'HYS Series', 'HIT Series'],
 'KACO new energy': ['blueplanet 3.0-5.0 NX1', 'blueplanet 15-20 TL3', 'blueplanet 50.0 NX3 M3', 'blueplanet hybrid'],
 'Steca': ['StecaGrid coolcept', 'StecaGrid coolcept3', 'Solarix PLI'],
 'Schneider Electric': ['Conext XW Pro', 'Conext SW', 'CL Series'],
 'Ingeteam': ['INGECON SUN 1Play', 'INGECON SUN 3Play', 'INGECON SUN STORAGE 1Play', 'INGECON SUN STORAGE 3Play'],
 'SAJ': ['R5', 'R6', 'H1', 'H2', 'HS2'],
 'Solplanet': ['ASW LT-G2', 'ASW S-G2', 'ASW H-T2', 'ASW H-S2'],
 'Autarco': ['MX Series', 'LX Series', 'LH Series'],
 'AISWEI': ['ASW LT-G2', 'ASW S-G2', 'ASW H-T2'],
 'CPS / Chint': ['SCA Series', 'SCH Series', 'CPS 3-Phase String'],
 'Tigo Energy': ['EI Inverter', 'TS4 + EI System'],
 'Tesla': ['Solar Inverter', 'Powerwall 3 Integrated Inverter'],
 'Afore': ['HNS Series', 'BNT Series', 'AF Series', 'ATON Series'],
 'LuxPowerTek': ['SNA', 'LXP Hybrid', 'LXP-LB-EU', 'TriP'],
 'Voltronic Power': ['Axpert VM', 'Axpert King', 'InfiniSolar', 'Axpert MAX'],
 'MPP Solar': ['PIP-MS', 'PIP-MK', 'LVX', 'MPI Hybrid'],
 'MUST Power': ['PV1800', 'PV1900', 'PH1800', 'PH1600'],
 'RENAC': ['R1 Mini', 'R3 Note', 'N1 HL', 'N3 HV', 'N3 Plus'],
 'Kehua Tech': ['SPI-B', 'SPI-B2', 'SPI-T1', 'SPI-T2', 'BCS'],
 'Sineng Electric': ['SP Series', 'EP Series', 'SP-350K-H1'],
 'ZCS Azzurro': ['1PH', '3PH', 'HYD 1PH', 'HYD 3PH'],
 'Riello Solartech': ['RS Single Phase', 'RS Three Phase', 'Sentry Solar'],
 'Omnik': ['Omniksol-1k/2k-TL', 'Omniksol-3k/4k-TL', 'Omniksol-3P'],
 'Zeversolar': ['Evershine TL', 'Eversol TL', 'Zeverlution', 'Zeverlution Pro'],
 'SolarMax': ['P Series', 'TP Series', 'HT Series', 'MT Series'],
 'Mastervolt': ['Soladin', 'Sunmaster', 'Mass Sine', 'Mass Combi'],
 'Studer Innotec': ['Xtender XTM', 'Xtender XTH', 'Xtender XTS', 'next3'],
 'OutBack Power': ['Radian GS', 'FXR/VFXR', 'SkyBox'],
 'Ferroamp': ['EnergyHub Wall', 'EnergyHub XL'],
 'NEP': ['BDM Series', 'BDS Series', 'PVG Series'],
 'TSUN': ['TSOL-MS', 'TSOL-MP', 'TSOL-MX'],
 'Power-One': ['Aurora PVI', 'Aurora UNO', 'Aurora TRIO']}

METER_CATALOG: dict[str, list[str]] = {'Smappee': ['Infinity', 'Genius', 'Connect', 'Energy', 'Pro'],
 'Shelly': ['EM', '3EM', 'Pro 3EM', 'Pro EM-50', 'PM Mini Gen3'],
 'Compteur numérique P1': ['Port P1 DSMR', 'P1 via ESPHome', 'P1 via MQTT', 'P1 USB / série'],
 'Compteur numérique P2': ['Port P2 / téléinformation', 'P2 via ESPHome', 'P2 via MQTT'],
 'HomeWizard': ['P1 Meter', 'Wi-Fi kWh Meter 1 phase', 'Wi-Fi kWh Meter 3 phases'],
 'Tibber': ['Pulse P1', 'Pulse HAN'],
 'Eastron': ['SDM120', 'SDM220', 'SDM230', 'SDM630', 'SDM72D-M'],
 'Carlo Gavazzi': ['EM24', 'EM340', 'ET112', 'ET340', 'EM530/540'],
 'Victron Energy': ['ET112', 'ET340', 'EM24 Ethernet', 'VM-3P75CT'],
 'Fronius': ['Smart Meter TS 65A-3', 'Smart Meter 63A-1', 'Smart Meter 63A-3', 'Smart Meter IP'],
 'SolarEdge': ['Modbus Meter', 'Inline Meter', 'Energy Meter with Modbus'],
 'Huawei': ['DTSU666-H', 'DTSU666-H 250A', 'DTSU71-B'],
 'GoodWe': ['GM1000', 'GM3000', 'GM3000C', 'HK3000'],
 'Sungrow': ['S100', 'DTSU666', 'Smart Energy Meter'],
 'Enphase': ['IQ Gateway Metered', 'Envoy-S Metered', 'Consumption CT'],
 'Schneider Electric': ['iEM3000', 'iEM3200', 'iEM3300', 'PowerTag'],
 'ABB': ['B21', 'B23', 'B24', 'M4M'],
 'Siemens': ['SENTRON PAC2200', 'PAC3200', 'PAC3220', 'PAC4200'],
 'Janitza': ['UMG 96RM', 'UMG 604', 'UMG 605', 'UMG 512'],
 'Socomec': ['DIRIS A-10', 'DIRIS A-20', 'DIRIS A-40', 'DIRIS Digiware'],
 'Hager': ['ECR180D', 'ECR380D', 'EC360', 'EC370'],
 'Finder': ['7M.24', '7M.38', '7E Series'],
 'Lovato Electric': ['DMG110', 'DMG210', 'DMG300', 'DME D'],
 'Legrand': ['EMDX3 monophasé', 'EMDX3 triphasé'],
 'Phoenix Contact': ['EMpro', 'EEM-MA600', 'EEM-EM357'],
 'ESPHome': ['CT Clamp ADC', 'ATM90E32', 'PZEM-004T', 'P1 DSMR', 'Pulse Counter'],
 'IoTaWatt': ['IoTaWatt 14-channel'],
 'Emporia': ['Vue Gen 2', 'Vue Gen 3'],
 'OpenEnergyMonitor': ['emonPi', 'emonTx4', 'emonVs'],
 'Aeotec': ['Home Energy Meter Gen5', 'Home Energy Meter 8'],
 'Qubino': ['3-Phase Smart Meter'],
 'Tuya': ['DIN Rail Energy Meter', '3-Phase CT Meter'],
 'Zemismart': ['DIN Rail Meter', '3-Phase Meter'],
 'PZEM / Peacefair': ['PZEM-004T', 'PZEM-016', 'PZEM-017'],
 'Modbus générique': ['Compteur Modbus TCP', 'Compteur Modbus RTU', 'Compteur triphasé Modbus'],
 'MQTT générique': ['Compteur MQTT', 'Bridge téléinfo MQTT', 'Capteur CT MQTT'],
 'Home Assistant calculé': ['PV + import - export', 'Réseau signé + PV', 'Template utilisateur']}

INVERTER_BRANDS = list(INVERTER_CATALOG)
METER_BRANDS = list(METER_CATALOG)


# FONCTION : models_for_inverter — Models for inverter
def models_for_inverter(brand: str | None) -> list[str]:
    models = list(INVERTER_CATALOG.get(str(brand or ""), []))
    if OTHER not in models:
        models.append(OTHER)
    return models


# FONCTION : models_for_meter — Models for meter
def models_for_meter(brand: str | None) -> list[str]:
    models = list(METER_CATALOG.get(str(brand or ""), []))
    if OTHER not in models:
        models.append(OTHER)
    return models
