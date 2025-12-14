import pygame
import sys
import random
from gpiozero import Button
import smbus
import time
import os

# ---------- BOTONES JUGADOR B (PALA DERECHA) ----------
btnB_subir = Button(24, pull_up=True, bounce_time=0.05)
btnB_bajar = Button(25, pull_up=True, bounce_time=0.05)

# ---------- ADC I2C 0x50 ULTRA ROBUSTO ----------
I2C_ADDR = 0x50
bus = None

def inicializar_i2c():
    global bus
    try:
        bus = smbus.SMBus(1)
        time.sleep(0.5)  # Espera inicial crítica
        return True
    except:
        return False

def leer_adc(channel=0):
    """Lectura ANTI-ERROR para ADC 0x50"""
    if bus is None:
        return 128
    
    for intento in range(10):
        try:
            # Pausa larga para estabilizar
            time.sleep(0.01)
            
            # Comando CORRECTO para PCF8591 típico
            comando = 0x40 | (channel & 0x03)
            bus.write_byte(I2C_ADDR, comando)
            
            time.sleep(0.01)
            bus.read_byte(I2C_ADDR)  # Dummy
            time.sleep(0.005)
            
            valor = bus.read_byte(I2C_ADDR)
            if 0 <= valor <= 255:
                return valor
                
        except:
            time.sleep(0.02)
            continue
    
    return 128  # Centro seguro

# ---------- PYGAME ----------
if not os.environ.get('XDG_RUNTIME_DIR'):
    os.environ['XDG_RUNTIME_DIR'] = f'/tmp/xdg-runtime-{os.getuid()}'

pygame.init()
ANCHO, ALTO = 800, 600
PANTALLA = pygame.display.set_mode((ANCHO, ALTO))
pygame.display.set_caption("Pong - Potenciometro vs Botones")

BLANCO = (255, 255, 255)
NEGRO = (0, 0, 0)
AZUL = (100, 150, 255)
VERDE = (50, 255, 100)

PALA_ANCHO = 12
PALA_ALTO = 90
PALA_VEL_BOTONES = 8

pala_a = pygame.Rect(40, (ALTO - PALA_ALTO)//2, PALA_ANCHO, PALA_ALTO)
pala_b = pygame.Rect(ANCHO-52, (ALTO - PALA_ALTO)//2, PALA_ANCHO, PALA_ALTO)

pelota = pygame.Rect(ANCHO//2-6, ALTO//2-6, 12, 12)
pelota_dx, pelota_dy = 6, 4

puntuacion_a = puntuacion_b = 0

fuente_grande = pygame.font.Font(None, 80)
fuente_info = pygame.font.Font(None, 28)

# VARIABLES CONTROL SENSIBILIDAD
valor_adc_actual = 128
y_objetivo_a = ALTO // 2
VALOR_MIN = 20
VALOR_MAX = 235
ZONA_MUERTA = 10

def mapear_potenciometro(valor):
    """Mapeo con zona muerta y límites para evitar sensibilidad excesiva"""
    # Zona muerta en extremos
    if valor < VALOR_MIN:
        valor = VALOR_MIN
    elif valor > VALOR_MAX:
        valor = VALOR_MAX
    
    # Mapear rango útil a pantalla
    rango_util = VALOR_MAX - VALOR_MIN
    posicion_norm = (valor - VALOR_MIN) / rango_util
    return int(posicion_norm * (ALTO - PALA_ALTO))

def reiniciar_pelota(dir_saque):
    global pelota_dx, pelota_dy
    pelota.center = (ANCHO//2, ALTO//2)
    pelota_dx = 6 * dir_saque
    pelota_dy = 4 * random.choice([-1, 1])

def juego_pong():
    global valor_adc_actual, y_objetivo_a, puntuacion_a, puntuacion_b
    
    # Inicializar I2C
    if not inicializar_i2c():
        print("ADVERTENCIA: I2C no disponible, usando valor fijo")
    
    reloj = pygame.time.Clock()
    reiniciar_pelota(1)
    
    while True:
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        # ---------------- JUGADOR A: POTENCIOMETRO (VERDE) ----------------
        valor_adc = leer_adc(0)
        valor_adc_actual = valor_adc
        
        # MAPEO MEJORADO con zona muerta y sin teletransportes
        y_objetivo_a = mapear_potenciometro(valor_adc)
        
        # Movimiento MUY SUAVE (reduce sensibilidad)
        diferencia = y_objetivo_a - pala_a.y
        pala_a.y += diferencia * 0.15  # 15% suavizado (muy lento)
        pala_a.y = max(0, min(ALTO - PALA_ALTO, pala_a.y))

        # ---------------- JUGADOR B: BOTONES (BLANCO) ----------------
        if btnB_subir.is_pressed:
            pala_b.y -= PALA_VEL_BOTONES
        if btnB_bajar.is_pressed:
            pala_b.y += PALA_VEL_BOTONES
        pala_b.y = max(0, min(ALTO - PALA_ALTO, pala_b.y))

        # ---------------- PELOTA ----------------
        pelota.x += int(pelota_dx)
        pelota.y += int(pelota_dy)

        if pelota.top <= 0 or pelota.bottom >= ALTO:
            pelota_dy *= -1

        if pelota.colliderect(pala_a) and pelota_dx < 0:
            pelota_dx *= -1.015
            pelota.left = pala_a.right

        if pelota.colliderect(pala_b) and pelota_dx > 0:
            pelota_dx *= -1.015
            pelota.right = pala_b.left

        if pelota.left <= 0:
            puntuacion_b += 1
            reiniciar_pelota(1)
        if pelota.right >= ANCHO:
            puntuacion_a += 1
            reiniciar_pelota(-1)

        # ---------------- DIBUJADO ----------------
        PANTALLA.fill(NEGRO)
        
        pygame.draw.rect(PANTALLA, VERDE, pala_a)
        pygame.draw.rect(PANTALLA, BLANCO, pala_b)
        pygame.draw.ellipse(PANTALLA, AZUL, pelota)
        pygame.draw.aaline(PANTALLA, BLANCO, (ANCHO//2, 0), (ANCHO//2, ALTO))

        # Puntuación
        txt_a = fuente_grande.render(str(puntuacion_a), True, VERDE)
        txt_b = fuente_grande.render(str(puntuacion_b), True, BLANCO)
        PANTALLA.blit(txt_a, (ANCHO//4-30, 20))
        PANTALLA.blit(txt_b, (ANCHO*3//4-30, 20))

        # DEBUG (muy informativo)
        info_adc = f"ADC: {valor_adc_actual}"
        info_pos = f"Y: {int(pala_a.y)}"
        info_btn = f"B↑:{btnB_subir.is_pressed} B↓:{btnB_bajar.is_pressed}"
        
        txt_adc = fuente_info.render(info_adc, True, VERDE)
        txt_pos = fuente_info.render(info_pos, True, VERDE)
        txt_btn = fuente_info.render(info_btn, True, BLANCO)
        
        PANTALLA.blit(txt_adc, (10, 10))
        PANTALLA.blit(txt_pos, (10, 35))
        PANTALLA.blit(txt_btn, (10, ALTO-30))

        pygame.display.flip()
        reloj.tick(60)

if __name__ == "__main__":
    try:
        juego_pong()
    except KeyboardInterrupt:
        print("\nJuego terminado")
    finally:
        pygame.quit()
        sys.exit()