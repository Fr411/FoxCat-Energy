from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import FoxCatEnergyCoordinator
from .dashboard import async_regenerate_dashboard
from .entity import FoxCatEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: FoxCatEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            FoxCatActionButton(
                coordinator,
                "analyser_solaire",
                "Analyser la prévision solaire",
                "mdi:weather-sunny-alert",
                "solar",
                "solar",
            ),
            FoxCatActionButton(
                coordinator,
                "diagnostic",
                "Lancer un diagnostic EMS",
                "mdi:stethoscope",
                "diagnostic",
                "diagnostic",
            ),
            FoxCatActionButton(
                coordinator,
                "liberer_onduleur",
                "Libérer l'onduleur à 100 %",
                "mdi:solar-power",
                "pri",
                "release_pri",
            ),
            FoxCatActionButton(
                coordinator,
                "reinitialiser_cycle",
                "Réinitialiser le cycle EMS",
                "mdi:restart",
                "ems",
                "reset",
            ),
            FoxCatActionButton(
                coordinator,
                "reconcilier_machines",
                "Réconcilier les prises machines",
                "mdi:power-socket-eu",
                "machines",
                "machines",
            ),
            FoxCatActionButton(
                coordinator,
                "boiler_demarrage_utilisateur",
                "Démarrage utilisateur Boiler",
                "mdi:water-boiler",
                "user_functions",
                "boiler_user_on",
            ),
            FoxCatActionButton(
                coordinator,
                "boiler_arret_utilisateur",
                "Arrêt utilisateur Boiler",
                "mdi:water-boiler-off",
                "user_functions",
                "boiler_user_off",
            ),
            FoxCatActionButton(
                coordinator,
                "boiler_retour_automatique",
                "Boiler retour automatique EMS",
                "mdi:autorenew",
                "user_functions",
                "boiler_user_auto",
            ),
            # Nouveau : permet de remettre le dashboard officiel du dépôt.
            FoxCatActionButton(
                coordinator,
                "regenerer_dashboard",
                "Régénérer le dashboard FoxCat",
                "mdi:view-dashboard-edit-outline",
                "diagnostic",
                "dashboard",
            ),
        ]
    )

    machine_buttons: list[FoxCatActionButton] = []
    for machine in coordinator.machines:
        safe_key = machine.machine_id.replace(" ", "_").lower()
        machine_buttons.extend([
            FoxCatActionButton(
                coordinator,
                f"machine_{safe_key}_demarrage_utilisateur",
                f"Démarrage utilisateur {machine.name}",
                "mdi:play-circle-outline",
                "user_functions",
                "machine_user_on",
                machine_id=machine.machine_id,
            ),
            FoxCatActionButton(
                coordinator,
                f"machine_{safe_key}_arret_utilisateur",
                f"Arrêt utilisateur {machine.name}",
                "mdi:stop-circle-outline",
                "user_functions",
                "machine_user_off",
                machine_id=machine.machine_id,
            ),
        ])
    if machine_buttons:
        async_add_entities(machine_buttons)


class FoxCatActionButton(FoxCatEntity, ButtonEntity):
    def __init__(
        self,
        coordinator: FoxCatEnergyCoordinator,
        key: str,
        name: str,
        icon: str,
        device: str,
        action: str,
        machine_id: str | None = None,
    ) -> None:
        super().__init__(
            coordinator,
            key,
            name,
            icon,
            device,
        )
        self._action = action
        self._machine_id = machine_id

    async def async_press(self) -> None:
        if self._action == "solar":
            await self.coordinator.async_analyze_solar(
                "RÉÉVALUATION MANUELLE"
            )

        elif self._action == "diagnostic":
            await self.coordinator.async_diagnostic()

        elif self._action == "release_pri":
            if (
                self.coordinator._pri_task
                and not self.coordinator._pri_task.done()
            ):
                self.coordinator._pri_task.cancel()

            await self.coordinator.async_release_pri_100(
                "Libération manuelle de l'onduleur à 100 %."
            )

        elif self._action == "reset":
            await self.coordinator.async_reset_cycle()

        elif self._action == "machines":
            await self.coordinator.async_reconcile_machines()

        elif self._action == "machine_user_on" and self._machine_id:
            await self.coordinator.async_user_start_machine(self._machine_id)

        elif self._action == "machine_user_off" and self._machine_id:
            await self.coordinator.async_user_stop_machine(self._machine_id)

        elif self._action == "boiler_user_on":
            await self.coordinator.async_user_boiler_override("FORCE_ON")

        elif self._action == "boiler_user_off":
            await self.coordinator.async_user_boiler_override("FORCE_OFF")

        elif self._action == "boiler_user_auto":
            await self.coordinator.async_user_boiler_override("AUTO")

        elif self._action == "dashboard":
            await async_regenerate_dashboard(self.hass, self.coordinator.entry, self.coordinator.config)

        self.coordinator.async_set_updated_data(
            self.coordinator._build_data()
        )
