import turtle
import random
import time
import threading   # <---IMPORTANTE

# ==========================
# ⚙️ CONFIGURACIÓN INICIAL
# ==========================
VELOCIDAD_BASE = 0.15
VELOCIDAD_PALA = 25

# ==========================
# SENSOR DE TEMPERATURA
# ==========================
SIM_TEMP = random.uniform(15, 30)
def leer_temperatura():
    return SIM_TEMP

def velocidad_desde_temperatura(temp):
    temp_min = 10
    temp_max = 35
    vel_min = 0.10
    vel_max = 0.40
    temp = max(temp_min, min(temp, temp_max))
    return vel_min + (vel_max - vel_min) * ((temp - temp_min) / (temp_max - temp_min))

# ==========================
# CONFIGURACIÓN ADC (I2C)
# ==========================
try:
    import board
    import busio
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn

    i2c = busio.I2C(board.SCL, board.SDA)
    ads = ADS.ADS1115(i2c)

    canal_izq = AnalogIn(ads, ADS.P0)
    canal_der = AnalogIn(ads, ADS.P1)

    USAR_ADC = True
except:
    print("Modo simulación palancas")
    USAR_ADC = False

def mapear_a_posicion(valor_adc):
    return -250 + (valor_adc / 65535) * 500

# ==========================
# VENTANA
# ==========================
ventana = turtle.Screen()
ventana.title("Pong con palancas")
ventana.bgcolor("black")
ventana.setup(width=800, height=600)
ventana.tracer(0)

# ==========================
# PALAS
# ==========================
pala_izq = turtle.Turtle()
pala_izq.speed(0)
pala_izq.shape("square")
pala_izq.color("white")
pala_izq.shapesize(stretch_wid=5, stretch_len=1)
pala_izq.penup()
pala_izq.goto(-350, 0)

pala_der = turtle.Turtle()
pala_der.speed(0)
pala_der.shape("square")
pala_der.color("white")
pala_der.shapesize(stretch_wid=5, stretch_len=1)
pala_der.penup()
pala_der.goto(350, 0)

# ==========================
# PELOTA
# ==========================
temp_inicial = leer_temperatura()
vel_inicial = velocidad_desde_temperatura(temp_inicial)

pelota = turtle.Turtle()
pelota.speed(0)
pelota.shape("circle")
pelota.color("white")
pelota.penup()
pelota.goto(0, 0)

# VARIABLE COMPARTIDA POR HILOS
pelota.dx = vel_inicial
pelota.dy = vel_inicial

print(f"Temperatura inicial: {temp_inicial:.1f}°C -> Velocidad: {vel_inicial:.2f}")

# ==========================
# MARCADOR
# ==========================
score_izq = 0
score_der = 0

marcador = turtle.Turtle()
marcador.speed(0)
marcador.color("white")
marcador.penup()
marcador.hideturtle()
marcador.goto(0, 260)
marcador.write("Jugador A: 0  Jugador B: 0", align="center", font=("Courier", 24, "normal"))

# ==========================
# --- 🧵 HILOS ---
# ==========================

# 🔥 1) HILO PARA ACTUALIZAR VELOCIDAD SEGÚN LA TEMPERATURA
def hilo_temperatura():
    global pelota
    while True:
        temp = leer_temperatura()
        vel = velocidad_desde_temperatura(temp)
        pelota.dx = vel if pelota.dx > 0 else -vel
        pelota.dy = vel if pelota.dy > 0 else -vel
        time.sleep(2)  # cada 2 segundos actualiza

# 🎮 2) HILO PARA LEER ADC (palancas)
def hilo_lectura_adc():
    global pala_izq, pala_der
    while True:
        if USAR_ADC:
            pala_izq.sety(mapear_a_posicion(canal_izq.value))
            pala_der.sety(mapear_a_posicion(canal_der.value))
        time.sleep(0.02)  # 50 Hz

# ==========================
# 🧵 INICIAR LOS HILOS
# ==========================
threading.Thread(target=hilo_temperatura, daemon=True).start()
threading.Thread(target=hilo_lectura_adc, daemon=True).start()

# ==========================
# BUCLE DE JUEGO
# ==========================
while True:
    ventana.update()

    # MOVER PELOTA
    pelota.setx(pelota.xcor() + pelota.dx)
    pelota.sety(pelota.ycor() + pelota.dy)

    # Colisiones verticales
    if pelota.ycor() > 290:
        pelota.sety(290)
        pelota.dy *= -1

    if pelota.ycor() < -290:
        pelota.sety(-290)
        pelota.dy *= -1

    # Salida por los lados
    if pelota.xcor() > 390:
        pelota.goto(0, 0)
        pelota.dx *= -1
        score_izq += 1
        marcador.clear()
        marcador.write(f"Jugador A: {score_izq}  Jugador B: {score_der}", align="center", font=("Courier", 24, "normal"))

    if pelota.xcor() < -390:
        pelota.goto(0, 0)
        pelota.dx *= -1
        score_der += 1
        marcador.clear()
        marcador.write(f"Jugador A: {score_izq}  Jugador B: {score_der}", align="center", font=("Courier", 24, "normal"))

    # Colisiones con palas
    if (340 < pelota.xcor() < 350) and (pala_der.ycor() - 50 < pelota.ycor() < pala_der.ycor() + 50):
        pelota.setx(340)
        pelota.dx *= -1.03

    if (-350 < pelota.xcor() < -340) and (pala_izq.ycor() - 50 < pelota.ycor() < pala_izq.ycor() + 50):
        pelota.setx(-340)
        pelota.dx *= -1.03
