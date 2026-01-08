# Fases de Desarrollo - Sistema Domótico Zephyr

Este documento desglosa el desarrollo del proyecto en fases incrementales. Cada fase agrega funcionalidad manteniendo lo anterior operativo.

---

## 📋 Fase 0: Preparación y Aprendizaje con QEMU

**Objetivo**: Dominar Zephyr RTOS sin necesidad de hardware físico, desarrollando las bases del firmware del nodo principal

**Duración estimada**: 2-3 semanas

---

### 1. Instalación del Entorno

#### Checklist de Instalación
- [ ] Instalar QEMU (incluido con SDK o instalación manual)
- [ ] Configurar variables de entorno
- [ ] Verificar instalación:
  ```bash
  west --version
  qemu-system-arm --version
  ```

#### Crear Workspace de Zephyr
- [ ] Crear estructura de directorios para tu proyecto

**Resultado esperado**: Entorno funcional listo para compilar

---

### 2. Primeros Pasos con QEMU

**Objetivo**: Familiarizarse con el flujo de compilación y ejecución

#### Validar Instalación
- [ ] Compilar y ejecutar "Hello World":
  ```bash
  cd samples/hello_world
  west build -p auto -b qemu_cortex_m3
  west build -t run
  ```
- [ ] Verificar output: "Hello World! qemu_cortex_m3"

#### Explorar Samples Oficiales
- [ ] `samples/basic/blinky` - GPIO y timers
- [ ] `samples/basic/button` - Interrupciones
- [ ] `samples/basic/threads` - Multithreading
- [ ] `samples/subsys/shell` - Interfaz de comandos
- [ ] `samples/subsys/logging` - Sistema de logs

**Objetivo**: Entender la estructura de un proyecto Zephyr

---

### 3. Aprendizaje de Conceptos Core

**Progresión**: Básico → Intermedio → Avanzado

#### Nivel 1: Fundamentos (Semana 1)
- [ ] **Threads**: Crear y sincronizar múltiples threads
  - `k_thread_create()`, prioridades, sleeping
- [ ] **Timers**: Temporizadores periódicos y one-shot
  - `k_timer_init()`, callbacks
- [ ] **Work Queues**: Diferir trabajo a otro contexto
  - `k_work_submit()`, delayed work
- [ ] **Logging**: Sistema de logs por nivel
  - `LOG_INF()`, `LOG_ERR()`, filtros

**Ejercicio 1**: App que imprime timestamp cada 2 segundos usando timer

#### Nivel 2: Comunicación (Semana 2)
- [ ] **Message Queues**: Paso de mensajes entre threads
- [ ] **Semáforos y Mutexes**: Sincronización
- [ ] **Ring Buffers**: Buffer circular para datos
- [ ] **Shell**: Comandos interactivos por UART

**Ejercicio 2**: Sistema productor-consumidor con message queue

#### Nivel 3: Persistencia y Estado (Semana 2-3)
- [ ] **NVS (Non-Volatile Storage)**: Guardar datos en flash simulada
- [ ] **Device Tree**: Configuración de hardware
- [ ] **Kconfig**: Opciones de compilación
- [ ] **Settings**: API de alto nivel para configuración

**Ejercicio 3**: Contador que persiste entre reinicios usando NVS

---

### 4. Proyecto Práctico: Simulador del Nodo Principal

**Objetivo**: Crear una aplicación que simule la arquitectura final

#### Arquitectura del Simulador
```
src/
├── main.c              # Inicialización y threads principales
├── sensor_sim.c/h      # Simula sensores (genera datos aleatorios)
├── actuator_sim.c/h    # Simula actuadores (LED virtual)
├── ui_sim.c/h          # Simula pantalla (output a consola)
├── input_sim.c/h       # Simula botones (comandos UART/shell)
├── state_manager.c/h   # Estado global del sistema
└── protocol.c/h        # Protocolo de mensajes (para Fase 2)
```

#### Funcionalidad del Simulador
- [ ] **Thread 1 - Sensores**: Genera temperatura/humedad cada 5s
- [ ] **Thread 2 - Actuadores**: Responde a comandos on/off
- [ ] **Thread 3 - UI**: Actualiza "display" cada 1s con estado
- [ ] **Thread 4 - Input**: Procesa comandos shell
- [ ] **State Manager**: Centraliza estado del sistema

#### Features a Implementar
- [ ] Comandos shell:
  - `status` - Muestra estado completo
  - `sensor` - Lee sensores
  - `actuator <id> <on|off>` - Controla actuador
  - `config set <key> <value>` - Cambia configuración
- [ ] Persistencia de configuración en NVS
- [ ] Logging estructurado en todos los módulos
- [ ] Watchdog para detectar threads colgados

**Hito**: Simulador funcional con 4 threads comunicándose

---

### 5. Diseño para Hardware Real

**Objetivo**: Preparar código portable a hardware físico

#### Principios de Abstracción
```c
// ✅ BUENO: Interfaz abstracta
typedef struct {
    int (*read)(float *value);
    int (*init)(void);
} sensor_api_t;

// ❌ MALO: Acoplado a hardware específico
int dht22_read_temp(float *temp);
```

#### Checklist de Portabilidad
- [ ] Separar interfaz de implementación
- [ ] Usar Device Tree para configuración de pines
- [ ] Usar Kconfig para features opcionales:
  ```kconfig
  config USE_REAL_HARDWARE
      bool "Use real sensors/actuators"
      default n
  ```
- [ ] Compilación condicional:
  ```c
  #ifdef CONFIG_USE_REAL_HARDWARE
      sensor_api = &dht22_sensor;
  #else
      sensor_api = &simulated_sensor;
  #endif
  ```

---

### 6. Análisis y Preparación para Hardware

**Objetivo**: Determinar requisitos de hardware reales

#### Mediciones en QEMU
- [ ] Uso de RAM: `west build -t ram_report`
- [ ] Uso de Flash: `west build -t rom_report`
- [ ] Número de threads simultáneos
- [ ] Tamaño de stacks necesarios
- [ ] Periféricos utilizados (UART, GPIO, SPI, I2C)

#### Selección de Hardware
Basándote en lo aprendido, evalúa:

**Opción 1: Nordic nRF52840-DK** (~$40)
- ✅ BLE nativo (crucial para Fase 2)
- ✅ ARM Cortex-M4, 256KB RAM, 1MB Flash
- ✅ Excelente soporte en Zephyr
- ❌ Más caro

**Opción 2: STM32 Nucleo (ej: F411RE)** (~$15)
- ✅ Económico
- ✅ ARM Cortex-M4, 128KB RAM, 512KB Flash
- ✅ Muchos pines disponibles
- ❌ BLE requiere módulo externo

**Opción 3: ESP32-DevKitC** (~$8)
- ✅ WiFi + BLE incluido
- ✅ Muy económico
- ⚠️ Soporte Zephyr en mejora continua
- ❌ Dual-core puede complicar debugging

**Opción 4: Raspberry Pi Pico** (~$4)
- ✅ Muy económico
- ✅ Dual-core ARM Cortex-M0+
- ✅ Buen soporte Zephyr
- ❌ Radio externo necesario

#### Documentar Decisión
- [ ] Crear `HARDWARE_REQUIREMENTS.md` con:
  - RAM mínima necesaria
  - Flash mínimo necesario
  - Periféricos requeridos
  - Justificación de la placa elegida

---

### 7. Limitaciones de QEMU

**Importante**: QEMU es excelente para aprender, pero tiene límites

| Aspecto | QEMU | Hardware Real |
|---------|------|---------------|
| CPU/RAM/Timers | ✅ Preciso | ✅ Real |
| GPIO básico | ✅ Simulado | ✅ Real |
| UART/consola | ✅ Funcional | ✅ Real |
| BLE/WiFi/LoRa | ❌ No existe | ✅ Real |
| Sensores I2C/SPI | ⚠️ Mockup | ✅ Real |
| Displays | ❌ No visual | ✅ Real |
| Consumo energético | ❌ No medible | ✅ Medible |
| Timing preciso | ⚠️ Aproximado | ✅ Exacto |

**Estrategia**: Desarrolla lógica en QEMU, valida hardware en Fase 1

---

### 8. Recursos y Documentación

#### Documentación Oficial
- [Zephyr Getting Started](https://docs.zephyrproject.org/latest/develop/getting_started/index.html)
- [Kernel Services](https://docs.zephyrproject.org/latest/kernel/services/index.html)
- [QEMU Boards](https://docs.zephyrproject.org/latest/boards/qemu/index.html)

#### Boards QEMU Recomendados
- `qemu_cortex_m3` - El más estándar, buen balance
- `qemu_cortex_m0` - Simula MCU con menos recursos
- `native_posix` - Debugging más fácil (ejecuta como proceso Linux)

#### Comandos Útiles
```bash
# Compilar
west build -p auto -b qemu_cortex_m3 .

# Ejecutar
west build -t run

# Configuración (menuconfig)
west build -t menuconfig

# Limpiar
west build -t pristine

# Reportes de uso
west build -t ram_report
west build -t rom_report

# Debugging con GDB
west build -t debugserver  # En terminal 1
gdb build/zephyr/zephyr.elf  # En terminal 2
```

---

### 9. Criterios de Validación

**Has completado Fase 0 exitosamente si**:

✅ **Conocimientos**:
- Entiendes threads, timers, y message queues
- Sabes usar Device Tree y Kconfig
- Comprendes el modelo de memoria de Zephyr

✅ **Código**:
- Tu simulador funciona con 4+ threads sin crashes
- El código está modularizado y documentado
- Usas abstracciones que facilitan el port a hardware

✅ **Preparación**:
- Documentaste requisitos de hardware
- Ya seleccionaste la placa para Fase 1
- Entiendes qué falta implementar con hardware real

---

### 10. Transición a Fase 1

**Lo que llevas de Fase 0**:
- ✅ Lógica de negocio (state machine, threads)
- ✅ Interfaces abstractas listas para conectar
- ✅ Código compilable y probado
- ✅ Experiencia con APIs de Zephyr

**Lo que harás en Fase 1**:
- Comprar hardware y conectarlo
- Reemplazar simuladores con drivers reales
- Integrar pantalla física
- Configurar botones físicos
- Validar consumos y timings reales

**No esperes hasta Fase 1**:
- ❌ Comunicación inalámbrica (es Fase 2)
- ❌ Gateway o cloud (son Fase 3+)

---

**Estado**: ⏳ En progreso  
**Siguiente**: Fase 1 - Hardware Real

---

## 🎯 Fase 1: Nodo Principal con Hardware Real

**Objetivo**: Nodo principal funcional con interfaz local (pantalla + botones)

**Pre-requisito**: Haber completado Fase 0 y tener hardware seleccionado

### Decisiones a Tomar
- [ ] Seleccionar MCU/placa (ya decidido en Fase 0)
- [ ] Tipo de pantalla (e-paper, OLED, LCD, TFT)
- [ ] Número y tipo de botones (físicos, táctiles, encoder rotatorio)
- [ ] Fuente de alimentación (USB, batería, fuente externa)
- [ ] Qué datos mostrar en pantalla inicialmente
- [ ] Layout de interfaz de usuario

### Checklist

#### Migración desde QEMU
- [ ] Portar código existente de QEMU a placa real
- [ ] Ajustar prj.conf para placa específica
- [ ] Crear overlay de Device Tree si es necesario
- [ ] Compilar con `west build -b <tu_placa>` sin errores
- [ ] Flashear y verificar que la lógica base funciona igual

#### Hardware - Display
- [ ] Conectar pantalla (anotar pines: SPI/I2C/parallel)
- [ ] Configurar Device Tree para la pantalla
- [ ] Integrar driver de pantalla en Zephyr
  - Si existe driver: configurar en prj.conf
  - Si no existe: escribir driver básico o usar biblioteca externa
- [ ] Implementar capa de abstracción de UI
- [ ] Probar escritura básica (texto, rectángulos)
- [ ] Optimizar refresh rate (crítico en e-paper)

#### Hardware - Botones
- [ ] Conectar botones físicos (pull-up/pull-down)
- [ ] Configurar GPIOs en Device Tree
- [ ] Implementar interrupciones para botones
- [ ] Implementar debouncing (hardware o software)
- [ ] Probar respuesta a presiones

#### Lógica de UI
- [ ] Reemplazar "ui_sim.c" con código real de pantalla
- [ ] Implementar navegación de menús
- [ ] Mostrar datos de sensores simulados (aún no reales)
- [ ] Implementar control de actuadores simulados con botones
- [ ] Agregar indicadores visuales (conexión, estado, errores)

#### Persistencia
- [ ] Configurar NVS (Non-Volatile Storage) en flash
- [ ] Guardar configuración del sistema
- [ ] Guardar estados de actuadores
- [ ] Probar que datos persisten tras reinicio

#### Power Management (opcional para Fase 1)
- [ ] Configurar sleep mode cuando inactivo
- [ ] Wake-up por botones
- [ ] Medir consumo con multímetro

### Preguntas para Responder
- ¿Cuánta información quieres mostrar simultáneamente en pantalla?
- ¿Necesitas gráficos o solo texto/íconos?
- ¿La pantalla estará siempre encendida o se apagará para ahorrar energía?
- ¿Cómo navegarás por los menús? (menú jerárquico, lista plana, tabs)
- ¿Qué estados quieres persistir al reiniciar el dispositivo?
- ¿Los botones tendrán funciones fijas o contextuales?

### Consideraciones Futuras
- Define un formato interno para representar "dispositivos" (ID, tipo, estado, última actualización)
- Diseña la UI pensando en que más adelante mostrarás datos reales de sensores
- La estructura de datos debe ser fácilmente serializable para enviar al gateway
- Considera añadir un modo "debug" en pantalla para facilitar desarrollo futuro
- Si eliges e-paper, ten en cuenta refresh lento (3-15 segundos según modelo)

### Comparación QEMU vs Hardware Real

| Aspecto | QEMU | Hardware Real |
|---------|------|---------------|
| Compilación | Rápida | Rápida |
| Deploy | Instantáneo | Flashear (5-30s) |
| Debug | gdb fácil | gdb o RTT |
| GPIO | Simulado | Real |
| Timing | Ideal | Real (puede variar) |
| Display | No existe | Real |
| Consumo | N/A | Medible |

### Hitos de Validación
✅ Código de Fase 0 funciona en hardware real  
✅ Pantalla muestra información legible  
✅ Botones responden correctamente  
✅ Puedes navegar por menús y cambiar estados  
✅ Estados persisten tras reinicio/power cycle  
✅ Código es modular y fácil de extender  
✅ Consumo energético es aceptable  

---

## 📊 Hitos Globales del Proyecto

| Fase | Duración Estimada | Complejidad | Dependencias |
|------|-------------------|-------------|--------------|
| 0. QEMU y Aprendizaje | 2-3 semanas | Baja | Ninguna |
| 1. Nodo Principal (HW) | 3-4 semanas | Media | Fase 0 |
| 2. Comunicaciones | 4-6 semanas | Alta | Fase 1 |
| 3. Gateway | 2-3 semanas | Media | Fase 2 |
| 4. Cloud | 2-3 semanas | Media | Fase 3 |
| 5. App Móvil | 3-4 semanas | Media | Fase 4 |
| 6. Refinamiento | Continuo | Variable | Todas |


---

## 🎯 Criterios de Éxito por Fase

### Fase 0 Exitosa Si:
- Dominas conceptos básicos de Zephyr (threads, timers, queues)
- Tu aplicación de prueba corre sin crashes en QEMU
- Tienes código modular listo para portar a hardware
- Ya decidiste qué placa comprar

### Fase 1 Exitosa Si:
- Código de QEMU funciona en hardware con cambios mínimos
- Puedes controlar mockups con botones físicos sin crashes
- UI es entendible y responsiva en pantalla real
- Código está organizado y documentado


## 🎯 Fase 1: Nodo Principal Standalone

**Objetivo**: Nodo principal funcional sin comunicaciones, solo con interfaz local

### Decisiones a Tomar
- [ ] Tipo de pantalla (e-paper, OLED, LCD, TFT)
- [ ] Número y tipo de botones (físicos, táctiles, encoder rotatorio)
- [ ] Fuente de alimentación (USB, batería, fuente externa)
- [ ] Qué datos mostrar en pantalla inicialmente
- [ ] Layout de interfaz de usuario

### Checklist
- [ ] Integrar driver de pantalla en Zephyr
- [ ] Implementar capa de UI básica (texto, íconos simples)
- [ ] Configurar GPIOs para botones
- [ ] Implementar debouncing de botones
- [ ] Crear máquina de estados para navegación de menús
- [ ] Implementar estructura de datos para "estado del sistema"
- [ ] Mockup de sensores/actuadores (valores hardcodeados)
- [ ] Mostrar datos mockeados en pantalla
- [ ] Controlar mockups con botones (toggle on/off, cambiar valores)
- [ ] Implementar persistencia básica (NVS) para configuración

### Preguntas para Responder
- ¿Cuánta información quieres mostrar simultáneamente en pantalla?
- ¿Necesitas gráficos o solo texto/íconos?
- ¿La pantalla estará siempre encendida o se apagará para ahorrar energía?
- ¿Cómo navegarás por los menús? (menú jerárquico, lista plana, tabs)
- ¿Qué estados quieres persistir al reiniciar el dispositivo?

### Consideraciones Futuras
- Define un formato interno para representar "dispositivos" (ID, tipo, estado, última actualización)
- Diseña la UI pensando en que más adelante mostrarás datos reales de sensores
- La estructura de datos debe ser fácilmente serializable para enviar al gateway
- Considera añadir un modo "debug" en pantalla para facilitar desarrollo futuro

### Hitos de Validación
✅ Pantalla muestra información legible  
✅ Botones responden correctamente  
✅ Puedes navegar por menús y cambiar estados  
✅ Estados persisten tras reinicio  
✅ Código es modular y fácil de extender  

---

## 📡 Fase 2: Comunicación Local - Nodos Secundarios

**Objetivo**: Establecer comunicación entre nodo principal y secundarios

### Decisiones a Tomar
- [ ] Protocolo de comunicación (BLE, Sub-GHz, Zigbee, Thread, LoRa)
- [ ] Topología de red (estrella, mesh, híbrida)
- [ ] Formato de mensajes (JSON, Protobuf, CBOR, binario custom)
- [ ] Hardware para nodos secundarios (mismo MCU o más simple/barato)
- [ ] Estrategia de direccionamiento (IDs estáticos, MAC addresses, discovery dinámico)

### Checklist

#### Nodo Principal
- [ ] Integrar stack de comunicación elegido (BLE host, LoRa radio, etc.)
- [ ] Implementar scanner/listener para nodos secundarios
- [ ] Crear protocolo de mensajes (define estructura de datos)
- [ ] Implementar recepción de datos de sensores
- [ ] Implementar envío de comandos a actuadores
- [ ] Actualizar UI para mostrar datos reales (reemplazar mocks)
- [ ] Manejar timeouts y desconexiones de nodos
- [ ] Logging de eventos de comunicación

#### Nodos Secundarios
- [ ] Crear proyecto base para nodo secundario (puede ser otro prj.conf)
- [ ] Implementar stack de comunicación (como peripheral/endpoint)
- [ ] Implementar lectura de sensor real (temperatura DHT22, BME280, etc.)
- [ ] O implementar control de actuador (LED, relay)
- [ ] Enviar datos periódicamente al nodo principal
- [ ] Implementar sleep modes para bajo consumo
- [ ] Responder a comandos desde nodo principal

### Preguntas para Responder
- ¿Qué rango de comunicación necesitas? (5m, 50m, 500m)
- ¿Cuántos nodos secundarios planeas soportar inicialmente? (5, 10, 50)
- ¿Los nodos secundarios serán de batería o alimentados?
- ¿Qué tan crítica es la latencia? (inmediato vs. minutos)
- ¿Necesitas comunicación bidireccional o solo sensores → principal?
- ¿Cómo identificarás cada nodo? (nombre, ID numérico, ubicación)
- ¿Implementarás encriptación desde el inicio o después?

### Consideraciones Futuras
- Si eliges BLE, considera BLE Mesh para escalar a +10 nodos
- Si eliges Sub-GHz, piensa en regulaciones por región (433/868/915 MHz)
- Diseña protocolo extensible (agregar nuevos tipos de mensajes sin romper compatibilidad)
- Implementa versionado en mensajes para actualizar firmware en el futuro
- Deja espacio para agregar autenticación/encriptación después
- Considera logs/telemetría para depurar problemas de comunicación

### Hitos de Validación
✅ Nodo principal detecta al menos un nodo secundario  
✅ Datos de sensor real se muestran en pantalla del principal  
✅ Comandos desde principal controlan actuador remoto  
✅ Comunicación funciona a distancia esperada  
✅ Sistema se recupera si un nodo se desconecta  
✅ Consumo de batería en nodos secundarios es aceptable  

---

## 💻 Fase 3: Gateway Local (Computador)

**Objetivo**: Agregar persistencia, histórico y preparar integración con cloud

### Decisiones a Tomar
- [ ] Plataforma del gateway (Raspberry Pi, PC Linux, Docker container)
- [ ] Lenguaje para el gateway (Python, Rust, Go, Node.js)
- [ ] Base de datos para histórico (SQLite, PostgreSQL, InfluxDB, TimescaleDB)
- [ ] Interfaz nodo principal ↔ gateway (USB CDC, BLE GATT, TCP/IP si hay Ethernet)
- [ ] API del gateway (REST, GraphQL, gRPC)

### Checklist

#### Comunicación Nodo ↔ Gateway
- [ ] En nodo principal: implementar interfaz serial o BLE GATT server
- [ ] En gateway: implementar cliente que lee del nodo principal
- [ ] Definir protocolo de mensajes (puede reutilizar el interno)
- [ ] Probar recepción continua de datos en gateway

#### Almacenamiento
- [ ] Configurar base de datos
- [ ] Diseñar esquema de tablas (devices, readings, events, commands)
- [ ] Implementar inserción de lecturas de sensores
- [ ] Implementar inserción de eventos (cambios de estado)
- [ ] Implementar queries básicas (últimas N lecturas, rango de fechas)

#### API Local
- [ ] Crear API REST básica (GET /devices, GET /readings, POST /command)
- [ ] Implementar autenticación (JWT, API key, o nada si es solo local)
- [ ] Endpoints para obtener datos históricos
- [ ] Endpoints para enviar comandos al nodo principal
- [ ] WebSocket para streaming de datos en tiempo real (opcional)

#### Sincronización
- [ ] Manejar escenario: gateway offline, luego vuelve online
- [ ] Buffer en nodo principal o simplemente se pierden datos del período offline
- [ ] Timestamp en todos los eventos

### Preguntas para Responder
- ¿Cuánto histórico quieres mantener? (días, meses, años)
- ¿El gateway estará siempre encendido o puede apagarse?
- ¿Necesitas interfaz web local para ver datos sin app móvil?
- ¿El nodo principal buferea datos si el gateway está offline?
- ¿Implementarás control desde el gateway o solo lectura?
- ¿El gateway corre en la misma red que tu PC o es un dispositivo dedicado?

### Consideraciones Futuras
- Diseña API pensando en que el cloud usará endpoints similares
- Implementa rate limiting básico para no saturar el nodo principal
- Considera agregar alertas locales (enviar email/push si sensor fuera de rango)
- Piensa en backups de la base de datos
- Si planeas OTA updates, el gateway puede ser el servidor de archivos

### Hitos de Validación
✅ Gateway recibe datos del nodo principal continuamente  
✅ Datos se almacenan correctamente en base de datos  
✅ API responde con histórico de datos  
✅ Puedes enviar comando desde API hacia nodo principal  
✅ Sistema tolera reconexiones del gateway  

---

## ☁️ Fase 4: Backend en la Nube (Cloudflare)

**Objetivo**: Acceso remoto al sistema desde cualquier lugar

### Decisiones a Tomar
- [ ] Arquitectura en Cloudflare (Workers, Pages + Functions, Durable Objects)
- [ ] Autenticación (Auth0, Firebase Auth, JWT custom, Cloudflare Access)
- [ ] Base de datos en cloud (D1, Postgres en Supabase/Neon, MongoDB Atlas)
- [ ] Protocolo gateway ↔ cloud (REST polling, WebSocket, MQTT)
- [ ] Manejo de multi-usuario (1 usuario o varios con permisos)

### Checklist

#### Infraestructura Cloud
- [ ] Crear cuenta y proyecto en Cloudflare
- [ ] Configurar Workers o Pages
- [ ] Configurar base de datos (puede replicar del gateway o independiente)
- [ ] Configurar dominio y certificados SSL
- [ ] Implementar autenticación de usuarios

#### Comunicación Gateway ↔ Cloud
- [ ] En gateway: cliente para enviar datos a cloud
- [ ] En cloud: endpoint para recibir datos del gateway
- [ ] Implementar heartbeat/keep-alive
- [ ] Manejar reconexiones automáticas
- [ ] Considerar compresión de datos si el upload es grande

#### API Cloud
- [ ] Replicar endpoints críticos de API local
- [ ] GET /devices - lista de dispositivos
- [ ] GET /readings/:deviceId - histórico de sensor
- [ ] POST /command - enviar comando (cloud → gateway → nodo)
- [ ] WebSocket para updates en tiempo real a app móvil

#### Seguridad
- [ ] HTTPS obligatorio
- [ ] Autenticación en todos los endpoints
- [ ] Autorización (solo el propietario ve sus dispositivos)
- [ ] Rate limiting para prevenir abuso
- [ ] Validación de inputs

### Preguntas para Responder
- ¿Datos históricos se sincronizan automáticamente o bajo demanda?
- ¿El cloud guarda TODO el histórico o solo reciente?
- ¿Múltiples usuarios pueden controlar el mismo sistema?
- ¿Latencia de comandos remotos es crítica o puede tardar segundos?
- ¿Qué pasa si el gateway pierde conexión a internet días?
- ¿Implementarás notificaciones push desde el cloud?

### Consideraciones Futuras
- Cloudflare Workers tiene límites de CPU time - diseña para ser eficiente
- Usa Cloudflare Durable Objects si necesitas conexiones WebSocket persistentes
- Implementa retry logic en caso de fallos temporales de red
- Considera agregar analytics (cuántos comandos, qué sensores más activos)
- Piensa en costos a escala (requests, DB storage, bandwidth)

### Hitos de Validación
✅ Gateway se conecta al cloud y envía datos  
✅ Puedes autenticarte desde navegador/API client  
✅ API cloud responde con datos de tus dispositivos  
✅ Comando enviado desde cloud llega al nodo principal  
✅ WebSocket entrega updates en tiempo real  
✅ Sistema se recupera si cloud está offline temporalmente  

---

## 📱 Fase 5: Aplicación Móvil

**Objetivo**: Interfaz de usuario móvil para control remoto

### Decisiones a Tomar
- [ ] Framework (React Native, Flutter, nativo iOS/Android, PWA)
- [ ] Plataformas objetivo (solo Android, solo iOS, ambos)
- [ ] Estilo de UI (Material Design, iOS HIG, custom)
- [ ] Manejo de estado (Redux, MobX, Provider, Zustand)
- [ ] Autenticación local (biometría, PIN, solo password)

### Checklist

#### Setup Proyecto
- [ ] Crear proyecto de app móvil
- [ ] Configurar dependencias (HTTP client, WebSocket, navigation)
- [ ] Configurar build para testing (emulador/dispositivo físico)

#### Autenticación
- [ ] Pantalla de login
- [ ] Almacenar token de forma segura (Keychain, Keystore)
- [ ] Auto-login si token válido
- [ ] Logout y refresh token

#### Pantallas Principales
- [ ] Dashboard: vista general de todos los dispositivos
- [ ] Detalle de dispositivo: histórico, controles
- [ ] Lista de dispositivos por habitación/tipo
- [ ] Configuración de cuenta y sistema
- [ ] Notificaciones (si implementadas)

#### Comunicación con Cloud
- [ ] HTTP client para API REST
- [ ] WebSocket client para updates en tiempo real
- [ ] Manejo de errores de red
- [ ] Indicador de conexión/desconexión
- [ ] Pull-to-refresh en listas

#### UX/UI
- [ ] Loading states en todas las operaciones
- [ ] Mensajes de error claros
- [ ] Feedback visual en acciones (toggle switch, cambio de estado)
- [ ] Modo offline (mostrar último estado conocido)
- [ ] Animaciones suaves

### Preguntas para Responder
- ¿Necesitas soporte offline (ver último estado sin internet)?
- ¿La app puede controlar directamente el nodo principal vía BLE cuando estás cerca?
- ¿Implementarás notificaciones push? (Firebase, OneSignal)
- ¿Gráficos de histórico de sensores o solo valores actuales?
- ¿Multi-idioma desde el inicio?
- ¿Necesitas onboarding para nuevos usuarios?

### Consideraciones Futuras
- Diseña para agregar widgets/shortcuts nativos después
- Piensa en accesibilidad (tamaños de fuente, contraste)
- Considera modo oscuro
- Deja espacio para agregar automatizaciones/escenas
- Implementa analytics básico (crashlytics, eventos de uso)

### Hitos de Validación
✅ Login funciona y token se persiste  
✅ Dashboard muestra todos los dispositivos  
✅ Puedes controlar un actuador desde la app  
✅ Updates en tiempo real se reflejan sin refresh manual  
✅ App funciona en Android e iOS (si aplica)  
✅ UX es fluida y sin bugs críticos  

---

## 🔧 Fase 6: Refinamiento e Integración

**Objetivo**: Pulir, optimizar y agregar features avanzados

### Áreas de Mejora

#### Firmware (Nodos)
- [ ] Optimizar consumo energético (deep sleep, wake-on-radio)
- [ ] Implementar OTA updates
- [ ] Mejorar manejo de errores y watchdogs
- [ ] Agregar más tipos de sensores/actuadores
- [ ] Implementar encriptación en comunicaciones
- [ ] Logs estructurados y telemetría

#### Gateway
- [ ] Auto-discovery de nodos nuevos
- [ ] Dashboard web local (opcional)
- [ ] Reglas y automatizaciones locales
- [ ] Backup automático de base de datos
- [ ] Monitoreo de salud del sistema
- [ ] Configuración vía archivo (YAML/JSON)

#### Cloud
- [ ] Escalabilidad (sharding, caching)
- [ ] Monitoreo y alertas de infraestructura
- [ ] Panel de administración web
- [ ] Logs centralizados
- [ ] Analytics de uso
- [ ] Multi-tenancy si aplica

#### App Móvil
- [ ] Gráficos de histórico (líneas, barras)
- [ ] Automatizaciones/escenas (ej: "Modo noche")
- [ ] Notificaciones inteligentes
- [ ] Compartir acceso con otros usuarios
- [ ] Widgets de inicio
- [ ] Shortcuts de Siri/Google Assistant

#### Seguridad
- [ ] Auditoría de seguridad completa
- [ ] Penetration testing básico
- [ ] Implementar 2FA (opcional)
- [ ] Revisión de permisos y roles
- [ ] Encriptación end-to-end (si crítico)

#### Testing
- [ ] Unit tests en componentes críticos
- [ ] Integration tests en APIs
- [ ] Tests de carga en cloud
- [ ] Tests de batería en nodos
- [ ] Tests de alcance de radio

### Preguntas para Responder
- ¿Qué métricas quieres monitorear a largo plazo?
- ¿Planeas vender/distribuir o es solo personal?
- ¿Certificaciones necesarias? (CE, FCC si es producto comercial)
- ¿Documentación para usuarios finales?
- ¿Open source o closed source?

### Hitos de Validación
✅ Sistema completo funciona de extremo a extremo  
✅ Uptime >95% en condiciones normales  
✅ Batería de nodos dura semanas/meses  
✅ Latencia de comandos <2 segundos  
✅ Sin bugs críticos conocidos  
✅ Documentación completa  

---

## 📊 Hitos Globales del Proyecto

| Fase | Duración Estimada | Complejidad | Dependencias |
|------|-------------------|-------------|--------------|
| 0. Preparación | 1-2 semanas | Baja | Ninguna |
| 1. Nodo Principal | 3-4 semanas | Media | Fase 0 |
| 2. Comunicaciones | 4-6 semanas | Alta | Fase 1 |
| 3. Gateway | 2-3 semanas | Media | Fase 2 |
| 4. Cloud | 2-3 semanas | Media | Fase 3 |
| 5. App Móvil | 3-4 semanas | Media | Fase 4 |
| 6. Refinamiento | Continuo | Variable | Todas |

**Tiempo total estimado MVP funcional**: 15-22 semanas (3.5-5 meses)

---

## 🎯 Criterios de Éxito por Fase

### Fase 1 Exitosa Si:
- Puedes controlar mockups con botones sin crashes
- UI es entendible y responsiva
- Código está organizado y documentado

### Fase 2 Exitosa Si:
- Al menos 3 nodos secundarios funcionan simultáneamente
- Pérdida de paquetes <5%
- Alcance cumple expectativas

### Fase 3 Exitosa Si:
- Gateway funciona 24/7 sin intervención
- API responde en <500ms localmente
- Base de datos crece de forma predecible

### Fase 4 Exitosa Si:
- Acceso remoto funciona desde cualquier red
- Latencia aceptable (<5s para comandos)
- Sin costos inesperados de cloud

### Fase 5 Exitosa Si:
- App es usable por personas no técnicas
- No hay crashes en uso normal
- Feedback de usuarios es positivo

---

## 📝 Notas Importantes

1. **No hay prisa**: Cada fase se valida completamente antes de seguir
2. **Prototipa rápido**: Usa herramientas provisionales si acelera el aprendizaje
3. **Documenta decisiones**: Crea un DECISIONS.md con el "por qué" de cada elección técnica
4. **Versiona todo**: Git para código, fotos para hardware, backups de bases de datos
5. **Celebra hitos**: Cada fase completada es un logro real

---

**Última actualización**: Enero 2025  
**Estado actual**: Fase 0 - Preparación
