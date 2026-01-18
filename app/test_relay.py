import minimalmodbus
import time

PORT = "COM8"
SLAVE_ID = 1
BAUDRATE = 9600

instr = minimalmodbus.Instrument(PORT, SLAVE_ID)
instr.serial.baudrate = BAUDRATE
instr.serial.bytesize = 8
instr.serial.parity   = minimalmodbus.serial.PARITY_NONE
instr.serial.stopbits = 1
instr.serial.timeout  = 0.5
instr.mode = minimalmodbus.MODE_RTU
instr.clear_buffers_before_each_transaction = True

# --- команды ---
RELAY_ON  = 0x0100
RELAY_OFF = 0x0200


def relay_on(channel: int):
    """
    channel: 1..16
    """
    if not 1 <= channel <= 16:
        raise ValueError("Channel must be 1..16")

    instr.write_register(channel, RELAY_ON, functioncode=6)
    time.sleep(0.05)


def relay_off(channel: int):
    """
    channel: 1..16
    """
    if not 1 <= channel <= 16:
        raise ValueError("Channel must be 1..16")

    instr.write_register(channel, RELAY_OFF, functioncode=6)
    time.sleep(0.05)


def relay_set(channel: int, state: bool):
    """
    state=True  -> ON
    state=False -> OFF
    """
    relay_on(channel) if state else relay_off(channel)


# ---------------------
# Тест
# ---------------------
if __name__ == "__main__":
    relay_on(1)
    time.sleep(1)
    relay_off(1)

    relay_set(2, True)
    time.sleep(1)
    relay_set(2, False)
