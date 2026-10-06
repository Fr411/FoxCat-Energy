# FoxCat Energy V1.7.1 — Validation status

## Automated checks

Run the standard-library unit tests with:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

The current focused suite covers:

- migration of the historical Dynamique mode to the Éco EMS behavior while preserving the Day-Ahead source;
- dispatch of Confort through the established Éco boiler strategy;
- Price Analyzer reactive versus predictive state;
- favorable-window selection and duration cap;
- peak and best-slot reporting.

Compile the integration without writing bytecode into the repository with:

```bash
PYTHONPYCACHEPREFIX=/tmp/foxcat-pycache python -m compileall -q custom_components/foxcat_energy tests
```

These checks do not constitute full V1.7.1 acceptance testing.

## Not validated here

- Home Assistant startup, Config Flow/Options Flow persistence, entity registry, and dashboard rendering;
- live Day-Ahead provider payloads, tariff contract values, stale/unavailable entities, and DST transitions;
- physical boiler commands and thermal protections;
- PRI/RRCR, InverterCore, EnergyBus ACK/NOK, and real machine switches;
- mobile/tablet/desktop dashboard behavior and dashboard replacement/rollback.

Those checks require a Home Assistant runtime, real provider data, or physical equipment. Do not treat this report as evidence that those acceptance criteria have passed.
