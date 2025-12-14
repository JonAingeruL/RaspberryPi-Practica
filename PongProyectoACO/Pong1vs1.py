import pygame
import sys
import random
import smbus
from gpiozero import Button, LED
import time
import os
import threading

# ===================== CONFIGURACIÓN RASPBERRY =====================

if not os.environ.get('XDG_RUNTIME_DIR'):
    os.environ['XDG_RUNTIME_DIR'] = f'/tmp/xdg-runtime-{os.getuid()}'

# BOTONES GPIO 22 y 23 para Pala B (derecha)
btn_subir = Button(22, pull_up=True, bounce_time=0.1)
btn_bajar = Button(23, pull_up=True, bounce_time=0.1)

# LED que se enciende cuando alguien hace un punto
# Conecta el LED: ánodo -> GPIO5 (pin físico 29), cátodo -> resistencia -> GND
led_punto = LED(5)

# ADC I2C 0x50 para Pala A (izquierda)
I2C_ADDR_ADC = 0x50
bus_adc = smbus.SMBus(1)

# SENSOR TEMPERATURA SEN11301P (simulado en misma dirección I2C)
I2C_ADDR_TEMP = 0x50

def leer_adc():
    """Lectura estable del ADC v1.2 en 0x50 - rango 0-8"""
    try:
        time.sleep(0.01)
        bus_adc.write_byte(I2C_ADDR_ADC, 0x40)  # Canal 0
        time.sleep(0.01)
        bus_adc.read_byte(I2C_ADDR_ADC)  # Dummy read
        valor = bus_adc.read_byte(I2C_ADDR_ADC)
        return max(0, min(8, valor))  # Limitar a tu rango 0-8
    except:
        return 4  # Centro del rango 0-8

def leer_temperatura():
    """SEN11301P - lectura simulada (mismo bus I2C que ADC)"""
    try:
        time.sleep(0.02)
        # Comando genérico de trigger temperatura
        bus_adc.write_byte(I2C_ADDR_TEMP, 0x33)
        time.sleep(0.02)
        data = bus_adc.read_i2c_block_data(I2C_ADDR_TEMP, 0x00, 2)
        temp_raw = (data[0] << 8) | data[1]
        temp_c = 15 + (temp_raw / 65535.0) * 20  # Escala 15-35°C
        return round(temp_c, 1)
    except:
        return 25.0  # Temperatura neutra

# ===================== MAPEO POTENCIÓMETRO 0–8 =====================

RANGO_MIN = 0
RANGO_MAX = 8

def mapear_potenciometro(valor_adc):
    """Mapea 0-8 a posición completa de pantalla"""
    normalizado = (valor_adc - RANGO_MIN) / (RANGO_MAX - RANGO_MIN)
    y_pantalla = int(normalizado * (600 - 90))  # ALTO - PALA_ALTO
    return y_pantalla

# ===================== VELOCIDAD POR TEMPERATURA =====================

TEMP_FRIO = 18.0   # <18°C = pelota MÁS RÁPIDA (1.4x)
TEMP_CALOR = 28.0  # >28°C = pelota MÁS LENTA (0.6x)

def factor_velocidad_temp(temp):
    if temp <= TEMP_FRIO:
        return 1.4
    elif temp >= TEMP_CALOR:
        return 0.6
    else:
        return 1.0

# ===================== VARIABLES COMPARTIDAS E HILOS =====================

adc_valor_compartido = 4
temp_compartida = 25.0
lock_datos = threading.Lock()
ejecutando_hilos = True

def hilo_sensores():
    """Hilo 1: lee ADC y temperatura continuamente"""
    global adc_valor_compartido, temp_compartida, ejecutando_hilos
    while ejecutando_hilos:
        nuevo_adc = leer_adc()
        nueva_temp = leer_temperatura()
        with lock_datos:
            adc_valor_compartido = nuevo_adc
            temp_compartida = nueva_temp
        time.sleep(0.05)  # ~20 Hz

def hilo_log():
    """Hilo 2: log periódico de estado (puedes comentar los prints si molestan)"""
    global ejecutando_hilos
    while ejecutando_hilos:
        with lock_datos:
            a = adc_valor_compartido
            t = temp_compartida
        print(f"[LOG] ADC={a} Temp={t}°C")
        time.sleep(5)

# ===================== PYGAME Y JUEGO =====================

pygame.init()
ANCHO, ALTO = 800, 600
PANTALLA = pygame.display.set_mode((ANCHO, ALTO))
pygame.display.set_caption("Pong 1vs1 - ADC 0x50(0-8) + SEN11301P + 5 Puntos + Hilos + LED")
reloj = pygame.time.Clock()

# Colores
NEGRO = (0, 0, 0)
BLANCO = (255, 255, 255)
VERDE = (0, 255, 100)
AZUL = (100, 150, 255)
ROJO = (255, 50, 50)
AMARILLO = (255, 255, 0)

# Elementos juego
PALA_ANCHO = 15
PALA_ALTO = 90
PALA_VEL_BOTONES = 8
PUNTOS_MAX = 5

pala_a = pygame.Rect(30, ALTO//2 - PALA_ALTO//2, PALA_ANCHO, PALA_ALTO)
pala_b = pygame.Rect(ANCHO - 45, ALTO//2 - PALA_ALTO//2, PALA_ANCHO, PALA_ALTO)

pelota = pygame.Rect(ANCHO//2 - 6, ALTO//2 - 6, 12, 12)
pelota_dx = 5
pelota_dy = 3

puntuacion_a = puntuacion_b = 0
temperatura_actual = 25.0

fuente_puntos = pygame.font.Font(None, 74)
fuente_info = pygame.font.Font(None, 28)
fuente_ganador = pygame.font.Font(None, 100)

def reiniciar_pelota():
    global pelota_dx, pelota_dy, temperatura_actual
    with lock_datos:
        temperatura_actual = temp_compartida
    factor = factor_velocidad_temp(temperatura_actual)
    pelota.center = (ANCHO//2, ALTO//2)
    pelota_dx = 5 * factor * random.choice([-1, 1])
    pelota_dy = 3 * factor * random.choice([-1, 1])

# Lanzar hilos
t_sensores = threading.Thread(target=hilo_sensores, daemon=True)
t_log = threading.Thread(target=hilo_log, daemon=True)
t_sensores.start()
t_log.start()

# Bucle principal
reiniciar_pelota()
ejecutando = True
partida_terminada = False

while ejecutando:
    # Eventos
    for evento in pygame.event.get():
        if evento.type == pygame.QUIT:
            ejecutando = False
        if evento.type == pygame.KEYDOWN:
            if evento.key == pygame.K_SPACE and partida_terminada:
                # Reiniciar partida
                puntuacion_a = puntuacion_b = 0
                partida_terminada = False
                reiniciar_pelota()

    if not partida_terminada:
        # Leer valores compartidos de los hilos
        with lock_datos:
            valor_adc = adc_valor_compartido
            temperatura_actual = temp_compartida

        # JUGADOR A - POTENCIÓMETRO (0–8) -> Pala Verde
        y_destino_a = mapear_potenciometro(valor_adc)
        pala_a.y += (y_destino_a - pala_a.y) * 0.25
        pala_a.y = max(0, min(ALTO - PALA_ALTO, pala_a.y))
        
        # JUGADOR B - BOTONES GPIO 22/23 -> Pala Blanca
        if btn_subir.is_pressed:
            pala_b.y -= PALA_VEL_BOTONES
        if btn_bajar.is_pressed:
            pala_b.y += PALA_VEL_BOTONES
        pala_b.y = max(0, min(ALTO - PALA_ALTO, pala_b.y))
        
        # PELOTA con velocidad por temperatura
        factor_vel = factor_velocidad_temp(temperatura_actual)
        pelota.x += pelota_dx
        pelota.y += pelota_dy
        
        # Rebote techo/suelo
        if pelota.top <= 0 or pelota.bottom >= ALTO:
            pelota_dy *= -1
        
        # Colisión Pala A
        if pelota.colliderect(pala_a) and pelota_dx < 0:
            pelota_dx *= -1.02 * factor_vel
            pelota.left = pala_a.right
        
        # Colisión Pala B
        if pelota.colliderect(pala_b) and pelota_dx > 0:
            pelota_dx *= -1.02 * factor_vel
            pelota.right = pala_b.left
        
        # Puntuación y FIN PARTIDA + LED
        if pelota.left <= 0:
            puntuacion_b += 1
            led_punto.on()
            reiniciar_pelota()
            time.sleep(0.3)
            led_punto.off()
        if pelota.right >= ANCHO:
            puntuacion_a += 1
            led_punto.on()
            reiniciar_pelota()
            time.sleep(0.3)
            led_punto.off()
        
        # COMPROBAR FIN PARTIDA (5 PUNTOS)
        if puntuacion_a >= PUNTOS_MAX or puntuacion_b >= PUNTOS_MAX:
            partida_terminada = True
    
    # DIBUJADO
    PANTALLA.fill(NEGRO)
    
    pygame.draw.rect(PANTALLA, VERDE, pala_a)
    pygame.draw.rect(PANTALLA, BLANCO, pala_b)
    pygame.draw.ellipse(PANTALLA, AZUL, pelota)
    pygame.draw.aaline(PANTALLA, BLANCO, (ANCHO//2, 0), (ANCHO//2, ALTO))
    
    # Puntuación
    txt_a = fuente_puntos.render(str(puntuacion_a), True, VERDE)
    txt_b = fuente_puntos.render(str(puntuacion_b), True, BLANCO)
    PANTALLA.blit(txt_a, (ANCHO//4 - 20, 20))
    PANTALLA.blit(txt_b, (ANCHO*3//4 - 20, 20))
    
    if partida_terminada:
        # PANTALLA GANADOR
        if puntuacion_a >= PUNTOS_MAX:
            ganador = "JUGADOR A GANA!"
            color_ganador = VERDE
        else:
            ganador = "JUGADOR B GANA!"
            color_ganador = BLANCO
        
        txt_ganador = fuente_ganador.render(ganador, True, color_ganador)
        txt_espacio = fuente_info.render("PULSA ESPACIO PARA NUEVA PARTIDA", True, AMARILLO)
        
        PANTALLA.blit(txt_ganador, (ANCHO//2 - txt_ganador.get_width()//2, ALTO//2 - 50))
        PANTALLA.blit(txt_espacio, (ANCHO//2 - txt_espacio.get_width()//2, ALTO//2 + 20))
    else:
        # DEBUG
        factor_vel = factor_velocidad_temp(temperatura_actual)
        info_adc = f"ADC: {valor_adc}/8"
        info_temp = f"Temp: {temperatura_actual}°C x{factor_vel:.1f}"
        info_btns = f"↑:{btn_subir.is_pressed} ↓:{btn_bajar.is_pressed}"
        
        txt_adc = fuente_info.render(info_adc, True, VERDE)
        txt_temp = fuente_info.render(info_temp, True, BLANCO)
        txt_btns = fuente_info.render(info_btns, True, BLANCO)
        
        PANTALLA.blit(txt_adc, (10, 10))
        PANTALLA.blit(txt_temp, (10, 35))
        PANTALLA.blit(txt_btns, (10, ALTO - 35))
    
    pygame.display.flip()
    reloj.tick(60)

# Salida limpia
ejecutando_hilos = False
time.sleep(0.1)
pygame.quit()
sys.exit()
