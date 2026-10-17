"""
Control global aproximado del consumo TPM de Groq.

Comparte el presupuesto entre todos los agentes que utilicen
el mismo modelo/API key dentro del proceso.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from threading import Lock


logger = logging.getLogger(__name__)


class GroqTokenBudget:
    """
    Controla aproximadamente los tokens solicitados durante una
    ventana móvil de 60 segundos.

    Importante:
    - Cuenta tokens estimados antes de cada petición.
    - Espera si la nueva petición superaría el presupuesto.
    - Es compartido entre NutritionAgent y DietistAgent.
    """

    WINDOW_SECONDS = 60

    def __init__(self, budget: int = 6000):
        self.budget = budget
        self._usage_window = deque()
        self._lock = Lock()

    def _limpiar_expirados(self, ahora: float) -> None:
        """Elimina consumos que ya están fuera de la ventana de 60 s."""
        while self._usage_window:
            timestamp, _ = self._usage_window[0]

            if ahora - timestamp < self.WINDOW_SECONDS:
                break

            self._usage_window.popleft()

    def _tokens_usados(self, ahora: float) -> int:
        self._limpiar_expirados(ahora)

        return sum(
            tokens
            for _, tokens in self._usage_window
        )

    def esperar_disponibilidad(self, tokens_estimados: int) -> None:
        """
        Espera hasta que haya espacio suficiente para realizar
        una nueva petición.

        El contador se reserva dentro del mismo lock para evitar
        que dos agentes hagan la petición simultáneamente.
        """

        if tokens_estimados <= 0:
            return

        while True:
            with self._lock:
                ahora = time.monotonic()

                usados = self._tokens_usados(ahora)

                if usados + tokens_estimados <= self.budget:
                    self._usage_window.append(
                        (ahora, tokens_estimados)
                    )

                    logger.info(
                        "Groq TPM: reservados≈%d | "
                        "usados ventana≈%d/%d",
                        tokens_estimados,
                        usados + tokens_estimados,
                        self.budget,
                    )

                    return

                if not self._usage_window:
                    # Protección ante cualquier inconsistencia.
                    self._usage_window.append(
                        (ahora, tokens_estimados)
                    )
                    return

                timestamp_mas_antiguo = self._usage_window[0][0]

                espera = max(
                    1.0,
                    self.WINDOW_SECONDS
                    - (ahora - timestamp_mas_antiguo)
                    + 0.5,
                )

                logger.warning(
                    "Groq TPM: límite local alcanzado. "
                    "Usados≈%d/%d | nueva petición≈%d | "
                    "esperando %.1fs",
                    usados,
                    self.budget,
                    tokens_estimados,
                    espera,
                )

            time.sleep(espera)


# Una única instancia compartida por toda la aplicación.
groq_token_budget = GroqTokenBudget(
    budget=6000
)