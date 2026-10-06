# FoxCat Energy V1.7.1 — Test report

## Automated checks executed
- Python compilation: PASS for all integration Python modules.
- Migration Dynamique → source Day-Ahead + Éco: PASS.
- Manual remains Manual: PASS.
- Final-price no-double-count: PASS.
- Impact PIC component: PASS.
- Price Analyzer 15-minute native granularity: PASS.
- J+1 predictive mode: PASS.
- Eco / Confort / Manuel planner decisions: PASS.

## Not claimed as passed
- Home Assistant runtime integration test: not executable in this build environment because the Home Assistant Python package/runtime is not installed.
- Physical PRI/RRCR, EnergyBus ACK/NOK, boiler sensors and real machine switches: require a real HA installation.
- Browser/frontend rendering on smartphone/tablet/desktop: requires HA frontend.
- Actual provider Day-Ahead payload validity and real contract prices: require connected entities.
