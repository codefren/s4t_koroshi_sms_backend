"""
Replenishment Cron Service (DEPRECADO)

Este servicio ha sido desactivado. Ya no se crean solicitudes con estado
WAITING_STOCK ni con prioridad NORMAL.

Las solicitudes de reposición ahora se crean únicamente:
- Desde el cron de reserva de stock (stock_reservation_cron_service) con prioridad HIGH
- Desde la PDA (operator_websocket) con prioridad URGENT

Ambos flujos solo crean solicitudes con estado READY cuando hay stock
confirmado en el almacén de reposición (REPO).

Este archivo se mantiene como referencia. No se ejecuta desde main.py.
"""
